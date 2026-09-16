# Sweet Power Display

**Sweet POWER v1.0.0** ("Sweet POWER 1.0") -- architecture frozen. This
repository also publishes the `display_protocol_uart` ESPHome external
component used by the rest of the Sweet Power project. Stage 42G removed
ESP-NOW from the project; the `display_protocol_espnow` component (unused
by production, which has always used `display_protocol_uart`) was removed
along with it.

ESPHome firmware for the Waveshare ESP32-S3-Touch-LCD-7 Sweet POWER dashboard.

This project was generated from `C:\Projects\ESP\ESP-DEV-TOOLKIT` and then
updated with the working ESPHome hardware configuration:

- ESP32-S3 `esp32-s3-devkitc-1`;
- ESP-IDF framework;
- 16 MB flash;
- octal PSRAM at 80 MHz;
- I2C on GPIO8/GPIO9 at 400 kHz;
- CH422G IO expander;
- `mipi_rgb` model `ESP32-S3-TOUCH-LCD-7-800X480`.

LuxPower data comes from the published external component:

```yaml
https://github.com/lito1024/ESP-LUXPOWER
ref: v0.2.0
```

## Setup

Copy the example secrets file:

```powershell
Copy-Item secrets.example.yaml secrets.yaml
```

Fill in:

- Wi-Fi SSID;
- Wi-Fi password;
- LuxPower host;
- LuxPower TCP port;
- LuxPower dongle serial;
- LuxPower inverter serial.

`secrets.yaml` is ignored by Git.

## Validate

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome config sweet-power-display-offline-uart.yaml
```

## Compile

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome compile sweet-power-display-offline-uart.yaml
```

## Flash Later

USB:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome run sweet-power-display-offline-uart.yaml --device COM4
```

OTA:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome upload sweet-power-display-offline-uart.yaml --device sweet-power-display.local
```

No inverter writes are configured.

## Using `display_protocol_uart` In Another ESPHome Project

The UART telemetry receiver component is installable from this repository
via a pinned GitHub tag, with no `symlink://` or local filesystem paths:

```yaml
esphome:
  # ESP-TELEMETRY is a plain library dependency, not an ESPHome external
  # component -- declare it explicitly (display_protocol_uart does not
  # auto-declare it, so this repo's own local dev builds can keep using a
  # fast symlink:// dependency without conflicting with your pinned tag).
  libraries:
    - ESP-TELEMETRY=https://github.com/lito1024/ESP-TELEMETRY.git#v1.0.0

external_components:
  - source:
      type: git
      url: https://github.com/lito1024/sweet-power-display
      ref: v1.0.0
    components:
      - display_protocol_uart
    refresh: 0s
```

See `examples/external_component_usage.yaml` for a complete, minimal,
compilable configuration (UART + sensors only, no display/LVGL). Every
production catalog entity is available as `inverter1_<key>` /
`inverter2_<key>` sensor config keys; see `ENTITY_MODEL.md` in
`SweetPower-Project-Docs` for the full list.

## Runtime Behavior

The offline display keeps last valid inverter values during short telemetry
gaps and blanks them only when an inverter path reaches `Off`. See
`docs/DisplayRuntimeSemantics.md` for the `On`/`Wait`/`Off` timing and value
retention rules.
