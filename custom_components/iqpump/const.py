"""Constants for the Jandy iQPUMP01 integration."""

DOMAIN = "iqpump"
NAME = "Jandy iQPUMP01"

# Shared API key — hard-coded in all iAqualink clients, not a personal credential
ZODIAC_API_KEY = "EOOEMOW4YR6QNB07"

ZODIAC_LOGIN_URL = "https://prod.zodiac-io.com/users/v1/login"
IAQUALINK_DEVICES_URL = "https://r-api.iaqualink.net/devices.json"
IAQUALINK_CONTROL_URL = "https://r-api.iaqualink.net/v2/devices/{serial}/control.json"

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

# Pump opmode values (from APK production_config.json)
OPMODE_SCHEDULE = "0"   # run on programmed schedule
OPMODE_CUSTOM = "1"     # run at customspeedrpm indefinitely
OPMODE_STOP = "2"       # stop pump

# alldata field keys (top-level, after motordata is flattened with "motordata_" prefix)
ALLDATA_RUNSTATE = "runstate"          # "on" / "off"
ALLDATA_OPMODE = "opmode"              # "0" / "1" / "2"
ALLDATA_RPM_TARGET = "rpmtarget"       # target RPM (string int)
ALLDATA_CUSTOM_RPM = "customspeedrpm"  # custom speed RPM (string int)
ALLDATA_MOTOR_RPM = "motordata_speed"  # actual running RPM
ALLDATA_MOTOR_WATTS = "motordata_power"       # actual power draw in watts
ALLDATA_MOTOR_TEMP = "motordata_temperature"  # motor temperature (°C)
