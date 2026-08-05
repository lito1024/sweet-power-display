# Display Jitter Diagnostics

Stage: 19B

## Current Symptom

Real Waveshare ESP32-S3-Touch-LCD-7 runtime result:

- firmware flashes and boots successfully;
- LVGL dashboard is visible;
- LuxPower values are displayed;
- the image occasionally and irregularly twitches/flickers;
- the device does not appear to reboot.

## Current Configuration Baseline

Source file: `sweet-power-display.yaml`

- Display driver: `mipi_rgb`.
- Display model: `ESP32-S3-TOUCH-LCD-7-800X480`.
- Display `auto_clear_enabled`: `false`.
- Display `update_interval`: `never`.
- LVGL `buffer_size` before Stage 19B test: implicit default, generated as `0%`.
- LVGL `full_refresh`: implicit default, generated as `false`.
- LVGL `draw_rounding`: implicit default, generated as `2`.
- LVGL `color_depth`: implicit default, generated as `16`.
- LVGL `byte_order`: implicit default, generated as `big_endian`.
- Logger before Stage 19B test: implicit default `DEBUG`.
- LuxPower polling: input `1s`, holding `30s`.

The generated ESPHome config confirms the predefined model expands to the
Waveshare RGB pins and timings. Stage 19B does not override those pins or
timings.

## Previous Runtime Log Review

No persisted previous USB runtime log was found in this project directory. The
local `.esphome` directory contains build/generated logs and generated source,
but no captured serial runtime log with reboot, watchdog, PSRAM, LVGL, display
DMA, Wi-Fi reconnect, or LuxPower reconnect evidence.

Runtime log categories to check after flashing this build:

- reboot/reset messages;
- watchdog warnings;
- PSRAM allocation failures;
- LVGL warnings;
- display DMA/underrun warnings;
- Wi-Fi reconnects;
- LuxPower reconnects.

## Test Matrix

| Test | Change Group | Result | Notes |
| --- | --- | --- | --- |
| A | Set `lvgl.buffer_size: 12%`; keep `full_refresh` disabled/default; keep predefined display model; reduce duplicate label redraws; set logger to `INFO`; add 10s diagnostics log. | Pending | First controlled test. |
| B | Try `lvgl.buffer_size: 25%`. | Pending | Only if Test A is improved but not eliminated. |
| C | Try LVGL `full_refresh` in a separate build. | Pending | Only if only label regions twitch. |
| D | Inspect ESPHome predefined Waveshare RGB timing/framebuffer/DMA settings. | Pending | Only if the whole panel shifts/tears. |
| E | Treat as power/runtime stability. | Pending | Only if logs show reboots, brownouts, watchdogs, or resets. |

## Stage 19B Diagnostic Build Notes

- `lvgl.buffer_size` is explicitly set to `12%`.
- `full_refresh` remains unset and therefore disabled/default.
- `mipi_rgb` model remains `ESP32-S3-TOUCH-LCD-7-800X480`.
- RGB pins and timings are not overridden.
- LuxPowerTCP transport, polling, reconnect, cache, and protocol behavior are
  unchanged.
- Sensor callbacks format the visible label text and update LVGL only when that
  text changes.
- Binary sensor callbacks already run on state changes.
- A 10 second diagnostic log reports free heap, free internal heap, free PSRAM,
  a LuxPower input-cache-age proxy, and TCP connected state.

`LuxPowerTCP` has `inputCacheAge()`, but the published ESPHome wrapper in
`v0.2.0` does not expose it to YAML. The diagnostic log therefore reports
`input_cache_age_proxy_ms`, measured from the most recent valid LuxPower sensor
publish, without modifying the component or transport.
