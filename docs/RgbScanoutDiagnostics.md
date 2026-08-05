# RGB Scanout Diagnostics

Stage: 19C

Project: `C:\Projects\ESP\sweet-power-display`

## Symptom

The visible artifact is an irregular vertical jump of a horizontal block of
scan lines. Sometimes the shifted block is small; sometimes it is close to the
whole screen. The image recovers immediately and the device does not appear to
reboot.

Observed production frequency: approximately every 1-3 seconds.

Important observation: the same symptom was present with a single static
`Sweet Power` label. Stage 19B changes (`lvgl.buffer_size: 12%` and suppressing
redundant label updates) did not materially change the artifact. That makes an
LVGL widget redraw issue unlikely. The current working hypothesis is RGB panel
scanout drift caused by PSRAM/GDMA bandwidth, framebuffer transfer timing, or
RGB pixel clock stability.

## Source Evidence

ESPHome CLI: `C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome`

ESPHome version: 2026.6.5

Model source:

`C:\Projects\ESP\esphome-venv\Lib\site-packages\esphome\components\mipi_rgb\models\waveshare.py`

Relevant symbols:

- `wave_4_3`
- `ESP32-S3-TOUCH-LCD-7-800X480`

Driver source:

`C:\Projects\ESP\esphome-venv\Lib\site-packages\esphome\components\mipi_rgb\display.py`

`C:\Projects\ESP\esphome-venv\Lib\site-packages\esphome\components\mipi_rgb\mipi_rgb.cpp`

Generated C++ inspected:

`C:\Projects\ESP\sweet-power-display\.esphome\build\sweet-power-display-c1\src\main.cpp`

## Effective RGB Configuration

From the ESPHome Waveshare model and generated C++:

| Setting | Effective value | Evidence |
| --- | ---: | --- |
| Model | `ESP32-S3-TOUCH-LCD-7-800X480` | `waveshare.py` model extension |
| Width | 800 | inherited from `wave_4_3` |
| Height | 480 | inherited from `wave_4_3` |
| PCLK | 16 MHz | `pclk_frequency="16MHz"` and generated `set_pclk_frequency(16000000.0f)` |
| PCLK inverted | true | `pclk_inverted=True` and generated `set_pclk_inverted(true)` |
| HSYNC pulse width | 4 | model extension and generated `set_hsync_pulse_width(4)` |
| HSYNC back porch | 8 | model extension and generated `set_hsync_back_porch(8)` |
| HSYNC front porch | 8 | model extension and generated `set_hsync_front_porch(8)` |
| VSYNC pulse width | 4 | model extension and generated `set_vsync_pulse_width(4)` |
| VSYNC back porch | 16 | model extension and generated `set_vsync_back_porch(16)` |
| VSYNC front porch | 16 | model extension and generated `set_vsync_front_porch(16)` |
| DE pin | GPIO5 | inherited from `wave_4_3` |
| HSYNC pin | GPIO46 | inherited from `wave_4_3` |
| VSYNC pin | GPIO3 | inherited from `wave_4_3` |
| PCLK pin | GPIO7 | inherited from `wave_4_3` |
| Red data pins | GPIO1, GPIO2, GPIO42, GPIO41, GPIO40 | inherited from `wave_4_3` |
| Green data pins | GPIO39, GPIO0, GPIO45, GPIO48, GPIO47, GPIO21 | inherited from `wave_4_3` |
| Blue data pins | GPIO14, GPIO38, GPIO18, GPIO17, GPIO10 | inherited from `wave_4_3` |
| Data width | 16 bits | `mipi_rgb.cpp`: `config.data_width = data_pin_count` |
| Reset pin | CH422G output 3 | inherited from `wave_4_3` |
| Enable pins | CH422G outputs 2 and 6 | model extension |
| Display update interval | never | generated `set_update_interval(4294967295UL)` |
| Auto clear | false | generated `set_auto_clear(false)` |
| LVGL buffer | 12% | YAML and generated LVGL config |
| LVGL full refresh | false/default | no `full_refresh: true`; generated LVGL constructor flag is false |

## Framebuffer, Bounce Buffer, DMA

From `mipi_rgb.cpp` in ESPHome 2026.6.5:

| Setting | Effective value |
| --- | --- |
| Framebuffer placement | PSRAM |
| `fb_in_psram` | 1 |
| Number of framebuffers | 1 |
| `num_fbs` | 1 |
| Bounce buffer size | `width * 10` pixels |
| For 800px width | 8000 pixels |
| RGB clock source | `LCD_CLK_SRC_PLL160M` |
| PCLK active edge | negative when `pclk_inverted` is true |

The ESP-IDF RGB panel configuration is created in ESPHome code, not directly in
YAML. The current ESPHome `mipi_rgb` YAML schema exposes `pclk_frequency`, but
does not expose supported YAML options for `bounce_buffer_size_px`, `num_fbs`,
or framebuffer placement.

## Supported YAML Controls

Confirmed supported for `display.platform: mipi_rgb` in ESPHome 2026.6.5:

```yaml
display:
  - platform: mipi_rgb
    model: ESP32-S3-TOUCH-LCD-7-800X480
    pclk_frequency: 12MHz
```

Schema evidence: `display.py` includes `CONF_PCLK_FREQUENCY` with frequency
validation range 4 MHz to 100 MHz.

Not exposed as supported YAML options for `mipi_rgb` in ESPHome 2026.6.5:

- bounce buffer size
- number of framebuffers
- framebuffer placement

These would require an ESPHome component patch or upstream change, so they are
not part of the first diagnostic experiments.

## ESP-IDF / sdkconfig Observations

Inspected generated ESPHome build configuration:

| Option | Current state |
| --- | --- |
| `CONFIG_ESP32S3_DEFAULT_CPU_FREQ_240` | enabled |
| CPU frequency | 240 MHz |
| `CONFIG_SPIRAM_MODE_OCT` | enabled |
| `CONFIG_SPIRAM_SPEED_80M` | enabled |
| `CONFIG_SPIRAM_FETCH_INSTRUCTIONS` | not enabled |
| `CONFIG_SPIRAM_RODATA` | not enabled |
| `CONFIG_COMPILER_OPTIMIZATION_PERF` | not enabled |
| `CONFIG_COMPILER_OPTIMIZATION_SIZE` | enabled |
| `CONFIG_ESP32S3_DATA_CACHE_LINE_64B` | not enabled |
| `CONFIG_ESP32S3_DATA_CACHE_LINE_32B` | enabled |
| `CONFIG_ESP32S3_DATA_CACHE_LINE_SIZE` | 32 |
| `CONFIG_FREERTOS_HZ` | 1000 |
| `CONFIG_LCD_RGB_ISR_IRAM_SAFE` | not enabled |
| `CONFIG_LCD_RGB_RESTART_IN_VSYNC` | not enabled |

No ESP-IDF sdkconfig options were changed for Test C1.

## Stage 19D Full-Screen Runtime Isolation Results

The small centered-label tests were not conclusive because large black regions
could shift invisibly. Stage 19D.1 replaced the static content in C1-C5 with a
full-screen diagnostic pattern covering all 800x480 pixels.

Hardware results:

| Test | Runtime subsystem | Result |
| --- | --- | --- |
| C1 | Offline full-screen pattern | Stable |
| C2 | Wi-Fi full-screen pattern | Startup artifacts only, then stable |
| C3 | Wi-Fi + API full-screen pattern | Startup artifacts only, then stable |
| C4 | Wi-Fi + API + OTA full-screen pattern | Startup artifacts only, then stable |
| C5 | Wi-Fi + API + OTA + LuxPower polling, static full-screen pattern | Recurring small horizontal row-block jumps every 1-7 seconds |

Conclusion: LuxPower TCP polling load is sufficient to trigger RGB scanout
instability. LVGL redraw and dynamic dashboard updates are not required to
reproduce the jitter.

## Test C1 - Static Offline Display

File:

`sweet-power-display-test-c1-static-offline.yaml`

Purpose:

Determine whether Wi-Fi, API, OTA, LuxPower polling, or other network/flash
activity is triggering the RGB scanout drift.

Configuration:

- Keeps the predefined Waveshare display model unchanged.
- Keeps ESP32-S3 board, ESP-IDF framework, flash size, octal PSRAM, I2C pins,
  I2C frequency, CH422G, display `auto_clear_enabled: false`, and
  `update_interval: never`.
- Uses LVGL with `buffer_size: 12%`.
- Uses one static centered label only.
- Removes Wi-Fi, API, OTA, captive portal, LuxPower component, sensors,
  binary sensors, interval diagnostics, and dynamic widget updates.
- Logger remains available over USB/UART.

Validation: Passed.

Compilation: Passed.

Runtime result: Pending.

## Test C2 - PCLK Reduction

File:

`sweet-power-display-test-c2-pclk-12mhz.yaml`

Purpose:

If Test C1 still shows whole-panel or large-block vertical jumps, reduce RGB
pixel clock load while preserving all other display model parameters.

Default PCLK discovered: 16 MHz.

Proposed PCLK: 12 MHz.

Configuration change:

```yaml
display:
  - platform: mipi_rgb
    model: ESP32-S3-TOUCH-LCD-7-800X480
    pclk_frequency: 12MHz
```

Only PCLK is changed in this test variant. Porches, pins, PCLK inversion,
layout, LVGL behavior, LuxPower behavior, and polling are left unchanged.

Validation: Passed.

Compilation: Not run yet.

Runtime result: Pending.

## Next Experiments

Stage 19E mitigation tests:

| Test | File | Change from C5 | Runtime result |
| --- | --- | --- | --- |
| E1 | `sweet-power-display-test-e1-lux-pclk-12mhz.yaml` | Lower PCLK only: 16 MHz to 12 MHz | Pending |
| E2 | `sweet-power-display-test-e2-lux-poll-3s.yaml` | Lower input polling only: 1s to 3s | Pending |
| E3 | `sweet-power-display-test-e3-lux-pclk-12mhz-poll-3s.yaml` | Lower PCLK to 12 MHz and input polling to 3s | Pending |

Flash order:

1. E1 first; observe at least 5 minutes.
2. If E1 is stable, stop and recommend 12 MHz for production.
3. If E1 still jitters, test E2.
4. If E2 still jitters, test E3.
5. Stop at the first stable configuration.

Do not enable `full_refresh`, change `lvgl.buffer_size`, change RGB porches or
inversion, add diagnostics intervals, or modify LuxPower transport code during
these tests.
