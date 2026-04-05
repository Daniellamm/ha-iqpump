# Jandy iQPUMP01 — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Daniellamm/ha-iqpump.svg)](https://github.com/Daniellamm/ha-iqpump/releases)
[![Validate](https://github.com/Daniellamm/ha-iqpump/actions/workflows/validate.yml/badge.svg)](https://github.com/Daniellamm/ha-iqpump/actions/workflows/validate.yml)

A Home Assistant custom integration for the **Jandy iQPUMP01** Wi-Fi interface module (`i2d` device type). The built-in `iaqualink` core integration does not support this device type — this integration fills that gap.

## Features

| Entity | Type | Description |
|---|---|---|
| Pump Power | Switch | Turn the pump on or off |
| Pump RPM | Sensor | Current motor speed in RPM |
| Power Draw | Sensor | Real-time power consumption in watts |
| Speed Preset | Sensor | Active speed preset (1–8) |
| Target RPM | Number (slider) | Set desired RPM (600–3450, 50 RPM steps) |

The integration polls the Zodiac cloud every 30 seconds and handles token refresh automatically — no manual re-authentication needed.

## Requirements

- Home Assistant 2024.1.0 or later
- A Jandy iQPUMP01 registered and working in the **iAqualink** mobile app
- Your iAqualink account credentials (email + password)

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant.
2. Click **Integrations → ⋮ → Custom repositories**.
3. Add `https://github.com/Daniellamm/ha-iqpump` with category **Integration**.
4. Search for **Jandy iQPUMP01** and click **Download**.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/iqpump/` folder to your HA `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **iQPUMP** and select it.
3. Enter your iAqualink email and password.
4. The integration discovers your pump automatically. If you have multiple iQPUMP01 devices you will be prompted to pick one.

## Debug Logging

Add the following to `configuration.yaml` to enable verbose logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.iqpump: debug
```

## Known Limitations & Field Name Verification

The shadow API field names (`rpm`, `watts`, `speed`, `state`) are inferred from the specification and similar Zodiac device types. If any sensor shows `unavailable` after setup, enable debug logging and open an issue — paste the **full shadow response** from the log so the field mapping can be corrected.

## Contributing

PRs are welcome. Please open an issue first to discuss any significant change.

## License

MIT License — see [LICENSE](LICENSE).

## Credits

Reverse-engineering references:
- [tekkamanendless/iaqualink](https://github.com/tekkamanendless/iaqualink) — Go client, best existing API docs
- [flz/iaqualink-py](https://github.com/flz/iaqualink-py) — Python library used by the HA core integration
- [galletn/iaqualink](https://github.com/galletn/iaqualink) — Custom HA component for i2d robot type
- [HA core issue #134356](https://github.com/home-assistant/core/issues/134356) — Open bug tracking i2d support
