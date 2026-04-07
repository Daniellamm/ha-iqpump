"""Zodiac / iAqualink API client for the iQPUMP01 (i2d) integration."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import aiohttp

from .const import (
    CONF_AUTH_TOKEN,
    CONF_ID_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    IAQUALINK_CONTROL_URL,
    IAQUALINK_DEVICES_URL,
    SUPPORTED_DEVICE_TYPE,
    TOKEN_REFRESH_BUFFER,
    ZODIAC_API_KEY,
    ZODIAC_LOGIN_URL,
)

_LOGGER = logging.getLogger(__name__)

_CONTROL_HEADERS = {
    "api_key": ZODIAC_API_KEY,
    "user-agent": "okhttp/3.14.7",
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------

class IQPumpAuthError(Exception):
    """Raised when authentication fails (bad credentials)."""


class IQPumpApiError(Exception):
    """Raised when a non-auth API call fails."""


class IQPumpNoDeviceError(Exception):
    """Raised when no i2d device is found on the account."""


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class IQPumpApiClient:
    """Async client for the Zodiac/iAqualink cloud API.

    Authentication flow
    -------------------
    1. POST /users/v1/login with email + password → IdToken (JWT, ~1 hr)
    2. All pump calls: POST /v2/devices/{serial}/control.json
       Headers: api_key + Authorization: {IdToken} (no "Bearer" prefix)
       Body:    {user_id, command, [value]}
    3. When the IdToken expires, a full email+password re-login is required.
       The Zodiac API does not support stateless token refresh.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._email: str = ""
        self._password: str = ""
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._auth_token: str | None = None
        self._user_id: str | None = None

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _token_expires_soon(id_token: str, buffer_secs: int = TOKEN_REFRESH_BUFFER) -> bool:
        """Return True if the JWT will expire within *buffer_secs* seconds."""
        try:
            payload = id_token.split(".")[1]
            padding = "=" * (4 - len(payload) % 4)
            claims = json.loads(base64.b64decode(payload + padding))
            return float(claims["exp"]) - time.time() < buffer_secs
        except Exception:  # noqa: BLE001
            return True

    def dump_tokens(self) -> dict[str, str]:
        """Return current tokens for persistence in the config entry."""
        return {
            CONF_ID_TOKEN: self._id_token or "",
            CONF_REFRESH_TOKEN: self._refresh_token or "",
            CONF_AUTH_TOKEN: self._auth_token or "",
            CONF_USER_ID: self._user_id or "",
        }

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> dict[str, str]:
        """Full login with email + password. Stores credentials for re-auth."""
        self._email = email
        self._password = password
        return await self._do_auth({"api_key": ZODIAC_API_KEY, "email": email, "password": password})

    async def refresh(self) -> dict[str, str]:
        """Re-authenticate using refresh_token + email + password."""
        if not self._refresh_token:
            raise IQPumpAuthError("No refresh token — full re-login required")
        return await self._do_auth({
            "api_key": ZODIAC_API_KEY,
            "email": self._email,
            "password": self._password,
            "refresh_token": self._refresh_token,
        })

    async def _do_auth(self, payload: dict) -> dict[str, str]:
        try:
            async with self._session.post(
                ZODIAC_LOGIN_URL,
                json=payload,
                raise_for_status=False,
            ) as resp:
                if resp.status == 401:
                    raise IQPumpAuthError("Invalid email or password")
                if resp.status != 200:
                    text = await resp.text()
                    raise IQPumpApiError(f"Login failed: HTTP {resp.status} — {text}")
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise IQPumpApiError(f"Network error during login: {err}") from err

        oauth = data.get("userPoolOAuth", {})
        self._id_token = oauth["IdToken"]
        self._refresh_token = oauth.get("RefreshToken") or self._refresh_token
        self._auth_token = data.get("authentication_token", "")
        self._user_id = str(data.get("id", ""))
        _LOGGER.debug("Authenticated; user_id=%s", self._user_id)
        return self.dump_tokens()

    async def ensure_authenticated(self) -> None:
        """Refresh the token if missing or near expiry."""
        if not self._id_token or self._token_expires_soon(self._id_token):
            _LOGGER.debug("Token expired or expiring soon — refreshing")
            if self._refresh_token and self._email and self._password:
                await self.refresh()
            elif self._email and self._password:
                await self.login(self._email, self._password)
            else:
                raise IQPumpAuthError("Token expired and no credentials stored — re-login required")

    # ------------------------------------------------------------------
    # Device discovery
    # ------------------------------------------------------------------

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return all i2d devices visible to this account."""
        if not self._auth_token or not self._user_id:
            raise IQPumpApiError("Not authenticated — call login() first")
        params = {
            "api_key": ZODIAC_API_KEY,
            "authentication_token": self._auth_token,
            "user_id": self._user_id,
        }
        try:
            async with self._session.get(
                IAQUALINK_DEVICES_URL,
                params=params,
                raise_for_status=False,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise IQPumpApiError(f"Device list failed: HTTP {resp.status} — {text}")
                devices: list[dict] = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise IQPumpApiError(f"Network error fetching devices: {err}") from err

        i2d_devices = [d for d in devices if d.get("device_type") == SUPPORTED_DEVICE_TYPE]
        _LOGGER.debug(
            "Found %d i2d device(s): %s",
            len(i2d_devices),
            [d.get("serial_number") for d in i2d_devices],
        )
        if not i2d_devices:
            raise IQPumpNoDeviceError(
                f"No {SUPPORTED_DEVICE_TYPE} device found on this account. "
                "Ensure the iQPUMP01 is registered in the iAqualink app."
            )
        return i2d_devices

    # ------------------------------------------------------------------
    # Pump control — POST /v2/devices/{serial}/control.json
    # ------------------------------------------------------------------

    def _control_headers(self) -> dict[str, str]:
        return {**_CONTROL_HEADERS, "Authorization": self._id_token or ""}

    async def _control(self, serial: str, command: str, value: str | None = None) -> dict[str, Any]:
        """Send a command to the pump and return the parsed JSON response."""
        url = IAQUALINK_CONTROL_URL.format(serial=serial)
        body: dict[str, Any] = {"user_id": self._user_id, "command": command}
        if value is not None:
            body["value"] = value

        try:
            async with self._session.post(
                url,
                headers=self._control_headers(),
                json=body,
                raise_for_status=False,
            ) as resp:
                if resp.status == 401:
                    raise IQPumpAuthError("Pump API returned 401 — token expired")
                if resp.status != 200:
                    text = await resp.text()
                    raise IQPumpApiError(f"Pump command failed: HTTP {resp.status} — {text}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise IQPumpApiError(f"Network error sending pump command: {err}") from err

    async def get_alldata(self, serial: str) -> dict[str, Any]:
        """Read full pump state via /alldata/read. Returns flattened alldata dict."""
        await self.ensure_authenticated()
        response = await self._control(serial, "/alldata/read")

        if response.get("status") == "500":
            msg = response.get("error", {}).get("message", "Device offline")
            raise IQPumpApiError(f"Pump reported error: {msg}")

        # Flatten motordata sub-dict to top-level keys with "motordata_" prefix
        alldata = dict(response.get("alldata", {}))
        motor = alldata.pop("motordata", {})
        for k, v in motor.items():
            alldata[f"motordata_{k}"] = v

        _LOGGER.debug("alldata: %s", alldata)
        return alldata

    async def set_opmode(self, serial: str, value: str) -> None:
        """Set pump operating mode: '0'=schedule, '1'=custom speed, '2'=stop."""
        await self.ensure_authenticated()
        await self._control(serial, "/opmode/write", value)

    async def set_custom_rpm(self, serial: str, rpm: int) -> None:
        """Set the custom speed RPM target."""
        await self.ensure_authenticated()
        await self._control(serial, "/customspeedrpm/write", str(rpm))

    # ------------------------------------------------------------------
    # Convenience state extractor
    # ------------------------------------------------------------------

    @staticmethod
    def extract_pump_state(alldata: dict[str, Any]) -> dict[str, Any]:
        """Return the alldata dict as-is (coordinator data is already flattened alldata)."""
        return alldata
