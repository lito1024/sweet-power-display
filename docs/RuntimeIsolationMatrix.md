# Runtime Isolation Matrix

Stage: 19D

Project: `C:\Projects\ESP\sweet-power-display`

Known preliminary result: Test C1 (`sweet-power-display-test-c1-static-offline.yaml`)
was stable with the original small centered label. The small-label test covered
only a small fraction of display rows, so only the full-screen diagnostic
pattern results are conclusive.

Observed production symptom: a horizontal block of lines, sometimes almost the
whole screen, jumps vertically for a fraction of a second every 1-3 seconds.

Minimum observation time per flashed test: 3 minutes.

Ignore a single startup artifact, but record its timing separately. Treat
recurring artifacts after startup as the test result.

Allowed result values:

- Stable
- Jitter
- Reboot
- Other

Stop immediately at the first test that reproduces jitter. Do not continue to
later tests until the failing subsystem has been recorded.

## Test Matrix

| Test | File | Added subsystem | Static/Dynamic UI | Small-label observation | Full-screen pattern |
| --- | --- | --- | --- | --- | --- |
| C1 | `sweet-power-display-test-c1-static-offline.yaml` | None | Static | Stable, preliminary | Stable |
| C2 | `sweet-power-display-test-c2-wifi-only.yaml` | Wi-Fi | Static | Preliminary: small-label test | Startup artifacts only, then stable |
| C3 | `sweet-power-display-test-c3-wifi-api.yaml` | API | Static | Preliminary: small-label test | Startup artifacts only, then stable |
| C4 | `sweet-power-display-test-c4-wifi-api-ota.yaml` | OTA | Static | Preliminary: small-label test | Startup artifacts only, then stable |
| C5 | `sweet-power-display-test-c5-luxpower-no-ui-updates.yaml` | LuxPower polling and verified entity publish | Static | Not tested | Recurring jitter every 1-7 seconds |
| C6 | `sweet-power-display-test-c6-full-runtime.yaml` | Dynamic dashboard | Dynamic | Known jitter / Retest | Not part of Stage 19D.1 |

Conclusion: LuxPower TCP polling load is the first isolated runtime subsystem
that reintroduces recurring RGB scanout jitter.

## Stage 19E Mitigation Matrix

| Test | File | Change From C5 | Result |
| --- | --- | --- | --- |
| E1 | `sweet-power-display-test-e1-lux-pclk-12mhz.yaml` | Lower PCLK only: 16 MHz to 12 MHz | Pending |
| E2 | `sweet-power-display-test-e2-lux-poll-3s.yaml` | Lower input polling only: 1s to 3s | Pending |
| E3 | `sweet-power-display-test-e3-lux-pclk-12mhz-poll-3s.yaml` | Lower PCLK to 12 MHz and input polling to 3s | Pending |

Stage 19E flash order:

1. E1 first, observe at least 5 minutes.
2. If E1 is stable, stop and recommend 12 MHz for production.
3. If E1 still jitters, test E2.
4. If E2 still jitters, test E3.
5. Stop at the first stable configuration.

## Hardware Test Order

1. C1 full-screen pattern first.
2. C2 only if C1 is stable.
3. C3 only if C2 is stable.
4. C4 only if C3 is stable.
5. C5 only if C4 is stable.

## Flash Commands

Test C1:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome run sweet-power-display-test-c1-static-offline.yaml --device COM6
```

Test C2:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome run sweet-power-display-test-c2-wifi-only.yaml --device COM6
```

Test C3:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome run sweet-power-display-test-c3-wifi-api.yaml --device COM6
```

Test C4:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome run sweet-power-display-test-c4-wifi-api-ota.yaml --device COM6
```

Test C5:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome run sweet-power-display-test-c5-luxpower-no-ui-updates.yaml --device COM6
```

Test C6:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome run sweet-power-display-test-c6-full-runtime.yaml --device COM6
```

Test E1:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome upload sweet-power-display-test-e1-lux-pclk-12mhz.yaml --device COM6
```

Test E2:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome upload sweet-power-display-test-e2-lux-poll-3s.yaml --device COM6
```

Test E3:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome upload sweet-power-display-test-e3-lux-pclk-12mhz-poll-3s.yaml --device COM6
```

## Isolation Rules

- C1-C5 keep the same full-screen static diagnostic pattern.
- C2-C5 keep `lvgl.buffer_size: 12%`.
- C2-C5 keep `full_refresh` disabled/default.
- C2-C5 do not change RGB pins, timings, PCLK, porches, inversion,
  framebuffer, bounce buffer, layout, font, or static label.
- C5 adds LuxPower polling and verified ESPHome entities without LVGL callbacks
  or dynamic label updates.
- C6 reproduces the current full dashboard runtime for a final comparison.

## Notes

The project uses `!secret` keys for Wi-Fi and LuxPower values. Do not place real
Wi-Fi credentials, local IP addresses, dongle serials, or inverter serials in
tracked YAML files.
