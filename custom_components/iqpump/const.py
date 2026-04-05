"""Constants for the Jandy iQPUMP01 integration."""

DOMAIN = "iqpump"
NAME = "Jandy iQPUMP01"

# Shared API key — hard-coded in all iAqualink clients, not a personal credential
ZODIAC_API_KEY = "EOOEMOW4YR6QNB07"

ZODIAC_LOGIN_URL = "https://prod.zodiac-io.com/users/v1/login"
ZODIAC_SHADOW_URL_V1 = "https://prod.zodiac-io.com/devices/v1/{serial}/shadow"
ZODIAC_SHADOW_URL_V2 = "https://prod.zodiac-io.com/devices/v2/{serial}/shadow"
IAQUALINK_DEVICES_URL = "https://r-api.iaqualink.net/devices.json"

SUPPORTED_DEVICE_TYPE = "i2d"

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SERIAL = "serial_number"
CONF_DEVICE_NAME = "device_name"
CONF_ID_TOKEN = "id_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_AUTH_TOKEN = "authentication_token"
CONF_USER_ID = "user_id"

# Polling
DEFAULT_SCAN_INTERVAL = 30  # seconds
TOKEN_REFRESH_BUFFER = 300  # refresh if <5 min remaining

# RPM limits (Jandy VS pump spec)
PUMP_RPM_MIN = 600
PUMP_RPM_MAX = 3450
PUMP_SPEED_MIN = 1
PUMP_SPEED_MAX = 8

# Shadow field names (verified against i2d shadow; may be adjusted after live capture)
SHADOW_PUMP_STATE = "state"
SHADOW_PUMP_RPM = "rpm"
SHADOW_PUMP_WATTS = "watts"
SHADOW_PUMP_SPEED = "speed"
