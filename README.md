# Sweet Power Display

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
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome config sweet-power-display.yaml
```

## Compile

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome compile sweet-power-display.yaml
```

## Flash Later

USB:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome run sweet-power-display.yaml --device COM4
```

OTA:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome upload sweet-power-display.yaml --device sweet-power-display.local
```

No inverter writes are configured.
