"""Zodiac / iAqualink API client for the iQPUMP01 (i2d) integration."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import aiohttp

from .const import (
    CONF_AUTH_TOKEN,
    CONF_ID_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    IAQUALINK_DEVICES_URL,
    SUPPORTED_DEVICE_TYPE,
    TOKEN_REFRESH_BUFFER,
    ZODIAC_API_KEY,
    ZODIAC_LOGIN_URL,
    ZODIAC_SHADOW_URL_V1,
    ZODIAC_SHADOW_URL_V2,
)

_LOGGER = logging.getLogger(__name__)

# AWS region inferred from the Cognito pool in the login response
_AWS_REGION = "us-east-1"
# prod.zodiac-io.com sits behind API Gateway
_AWS_SERVICE = "execute-api"


# ---------------------------------------------------------------------------
# AWS Signature Version 4 helpers (pure stdlib, no boto3 required)
# ---------------------------------------------------------------------------

def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _derive_signing_key(secret: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _hmac_sha256(("AWS4" + secret).encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "aws4_request")
    return k_signing


def _sigv4_headers(
    method: str,
    url: str,
    payload: bytes,
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str = _AWS_REGION,
    service: str = _AWS_SERVICE,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return a dict of headers (including Authorization) for an AWS SigV4 request."""
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    query_string = parsed.query or ""

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    # Build the canonical header set (must be sorted, lowercase)
    headers_to_sign: dict[str, str] = {
        "host": host,
        "x-amz-date": amz_date,
        "x-amz-security-token": session_token,
    }
    if extra_headers:
        headers_to_sign.update({k.lower(): v for k, v in extra_headers.items()})

    signed_headers_list = sorted(headers_to_sign.keys())
    canonical_headers = "".join(f"{k}:{headers_to_sign[k]}\n" for k in signed_headers_list)
    signed_headers = ";".join(signed_headers_list)

    payload_hash = hashlib.sha256(payload).hexdigest()

    canonical_request = "\n".join([
        method.upper(),
        path,
        query_string,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    signing_key = _derive_signing_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    return {
        "Authorization": authorization,
        "x-amz-date": amz_date,
        "x-amz-security-token": session_token,
        "host": host,
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
    1. POST /users/v1/login  →  IdToken (JWT) + AWS STS credentials
    2. Shadow reads/writes use AWS Signature v4 with the STS credentials.
       This works for both device owners and shared users.
    3. Device list uses the legacy iAqualink API with authentication_token.
    4. The IdToken expires in ~1 hour; refresh via the RefreshToken path.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._auth_token: str | None = None
        self._user_id: str | None = None
        # AWS STS credentials — used for SigV4 signing of shadow endpoints
        self._aws_access_key: str | None = None
        self._aws_secret_key: str | None = None
        self._aws_session_token: str | None = None
        self._aws_identity_id: str | None = None

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

    def load_tokens(self, token_data: dict[str, str]) -> None:
        """Restore previously persisted tokens from a config entry."""
        self._id_token = token_data.get(CONF_ID_TOKEN)
        self._refresh_token = token_data.get(CONF_REFRESH_TOKEN)
        self._auth_token = token_data.get(CONF_AUTH_TOKEN)
        self._user_id = token_data.get(CONF_USER_ID)
        self._aws_access_key = token_data.get("aws_access_key")
        self._aws_secret_key = token_data.get("aws_secret_key")
        self._aws_session_token = token_data.get("aws_session_token")
        self._aws_identity_id = token_data.get("aws_identity_id")

    def dump_tokens(self) -> dict[str, str]:
        """Return current tokens for persistence in the config entry."""
        return {
            CONF_ID_TOKEN: self._id_token or "",
            CONF_REFRESH_TOKEN: self._refresh_token or "",
            CONF_AUTH_TOKEN: self._auth_token or "",
            CONF_USER_ID: self._user_id or "",
            "aws_access_key": self._aws_access_key or "",
            "aws_secret_key": self._aws_secret_key or "",
            "aws_session_token": self._aws_session_token or "",
            "aws_identity_id": self._aws_identity_id or "",
        }

    @property
    def _has_aws_creds(self) -> bool:
        return bool(self._aws_access_key and self._aws_secret_key and self._aws_session_token)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> dict[str, str]:
        """Full login with email + password. Returns token dict."""
        payload = {
            "api_key": ZODIAC_API_KEY,
            "email": email,
            "password": password,
        }
        return await self._do_login(payload, preserve_refresh_token=False)

    async def refresh(self) -> dict[str, str]:
        """Re-authenticate using the stored refresh token (no password needed).

        Note: a full re-login is performed so we also get fresh AWS STS
        credentials (which expire independently of the JWT).
        """
        if not self._refresh_token:
            raise IQPumpAuthError("No refresh token available — full re-login required")
        payload = {
            "api_key": ZODIAC_API_KEY,
            "email": "",
            "refresh_token": self._refresh_token,
        }
        return await self._do_login(payload, preserve_refresh_token=True)

    async def _do_login(self, payload: dict, *, preserve_refresh_token: bool) -> dict[str, str]:
        try:
            async with self._session.post(
                ZODIAC_LOGIN_URL,
                json=payload,
                raise_for_status=False,
            ) as resp:
                if resp.status == 401:
                    raise IQPumpAuthError("Invalid credentials")
                if resp.status != 200:
                    text = await resp.text()
                    raise IQPumpApiError(f"Login failed: HTTP {resp.status} — {text}")
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise IQPumpApiError(f"Network error during login: {err}") from err

        oauth = data.get("userPoolOAuth", {})
        self._id_token = oauth["IdToken"]
        if not preserve_refresh_token:
            self._refresh_token = oauth.get("RefreshToken")
        self._auth_token = data.get("authentication_token", "")
        self._user_id = str(data.get("id", ""))

        # AWS STS credentials — returned by Zodiac login, needed for SigV4
        creds = data.get("credentials", {})
        self._aws_access_key = creds.get("AccessKeyId")
        self._aws_secret_key = creds.get("SecretKey")
        self._aws_session_token = creds.get("SessionToken")
        self._aws_identity_id = creds.get("IdentityId")

        _LOGGER.debug(
            "Authenticated; user_id=%s aws_identity=%s",
            self._user_id,
            self._aws_identity_id,
        )
        return self.dump_tokens()

    async def ensure_authenticated(self) -> None:
        """Proactively refresh the token if it's near expiry."""
        if not self._id_token or self._token_expires_soon(self._id_token):
            _LOGGER.debug("Token expired or expiring soon — refreshing")
            await self.refresh()

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
    # Shadow (state) read / write — using AWS SigV4
    # ------------------------------------------------------------------

    async def get_shadow(self, serial: str) -> dict[str, Any]:
        """GET the device shadow, signed with AWS SigV4.

        Uses v2 endpoint with SigV4 (works for owners AND shared users).
        Falls back to v1 Bearer auth if AWS credentials are unavailable.
        """
        await self.ensure_authenticated()

        if self._has_aws_creds:
            return await self._get_shadow_sigv4(serial)
        else:
            _LOGGER.warning("No AWS credentials — falling back to Bearer token on v1")
            return await self._get_shadow_bearer(serial)

    async def _get_shadow_sigv4(self, serial: str) -> dict[str, Any]:
        """GET shadow using AWS Signature v4 (v2 endpoint)."""
        url = ZODIAC_SHADOW_URL_V2.format(serial=serial)
        payload = b""
        sig_headers = _sigv4_headers(
            method="GET",
            url=url,
            payload=payload,
            access_key=self._aws_access_key,
            secret_key=self._aws_secret_key,
            session_token=self._aws_session_token,
        )
        try:
            async with self._session.get(url, headers=sig_headers, raise_for_status=False) as resp:
                if resp.status == 200:
                    shadow = await resp.json(content_type=None)
                    _LOGGER.debug("Shadow (SigV4 v2): %s", shadow)
                    return shadow
                text = await resp.text()
                _LOGGER.warning("Shadow SigV4 v2 returned %s: %s", resp.status, text)
                raise IQPumpApiError(f"Shadow (SigV4 v2) failed: HTTP {resp.status} — {text}")
        except aiohttp.ClientError as err:
            raise IQPumpApiError(f"Network error fetching shadow: {err}") from err

    async def _get_shadow_bearer(self, serial: str) -> dict[str, Any]:
        """GET shadow using Bearer token (v1 endpoint — owner only)."""
        url = ZODIAC_SHADOW_URL_V1.format(serial=serial)
        headers = {"Authorization": f"Bearer {self._id_token}"}
        try:
            async with self._session.get(url, headers=headers, raise_for_status=False) as resp:
                if resp.status == 200:
                    shadow = await resp.json(content_type=None)
                    _LOGGER.debug("Shadow (Bearer v1): %s", shadow)
                    return shadow
                text = await resp.text()
                raise IQPumpApiError(f"Shadow (Bearer v1) failed: HTTP {resp.status} — {text}")
        except aiohttp.ClientError as err:
            raise IQPumpApiError(f"Network error fetching shadow: {err}") from err

    async def set_state(self, serial: str, desired: dict[str, Any]) -> dict[str, Any]:
        """PATCH the device shadow with a desired-state payload, signed with SigV4."""
        await self.ensure_authenticated()

        url = ZODIAC_SHADOW_URL_V2.format(serial=serial)
        body = {"state": {"desired": {"equipment": {"pump": desired}}}}
        payload_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")

        if self._has_aws_creds:
            sig_headers = _sigv4_headers(
                method="PATCH",
                url=url,
                payload=payload_bytes,
                access_key=self._aws_access_key,
                secret_key=self._aws_secret_key,
                session_token=self._aws_session_token,
                extra_headers={"content-type": "application/json"},
            )
            sig_headers["Content-Type"] = "application/json"
        else:
            sig_headers = {
                "Authorization": f"Bearer {self._id_token}",
                "Content-Type": "application/json",
            }

        try:
            async with self._session.patch(
                url, headers=sig_headers, data=payload_bytes, raise_for_status=False
            ) as resp:
                if resp.status not in (200, 202):
                    text = await resp.text()
                    raise IQPumpApiError(f"set_state failed: HTTP {resp.status} — {text}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise IQPumpApiError(f"Network error setting state: {err}") from err

    # ------------------------------------------------------------------
    # Convenience state extractor
    # ------------------------------------------------------------------

    @staticmethod
    def extract_pump_state(shadow: dict[str, Any]) -> dict[str, Any]:
        """Pull the pump sub-dict from a shadow response."""
        try:
            reported = shadow["state"]["reported"]
        except (KeyError, TypeError):
            _LOGGER.warning("Shadow missing state.reported: %s", shadow)
            return {}

        equipment = reported.get("equipment", {})
        pump = equipment.get("pump") or equipment.get("Pump") or {}

        if not pump:
            _LOGGER.warning(
                "No 'pump' key in shadow equipment. Full equipment: %s", equipment
            )

        return pump
