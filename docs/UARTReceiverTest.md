# Stage 21B UART Receiver Test

Configuration:

```text
sweet-power-display-test-uart-receiver.yaml
```

Purpose:

- Receive LuxPower gateway telemetry snapshots over binary UART.
- Validate `ESP-TELEMETRY` v0.2.0 decoding on the Waveshare display.
- Keep LuxPower TCP off the display ESP32-S3.
- Keep the display RGB model at the known-working default 16 MHz PCLK.

## Firmware Scope

Included:

- ESPHome logger over USB Serial/JTAG.
- Waveshare `mipi_rgb` display model `ESP32-S3-TOUCH-LCD-7-800X480`.
- LVGL diagnostic dashboard.
- ESPHome UART on GPIO44/GPIO43 at 230400 baud.
- Local `display_protocol_uart` external component.
- Published protocol library:
  `https://github.com/lito1024/ESP-TELEMETRY.git#v0.2.0`.

## USB Logging Requirement

Use the Waveshare native `USB` Type-C port for ESPHome logs. The receiver YAML
intentionally routes the logger to the ESP32-S3 USB Serial/JTAG controller:

```yaml
logger:
  level: INFO
  hardware_uart: USB_SERIAL_JTAG
```

This is required because the Stage 21B UART receiver uses GPIO44/GPIO43, which
are the ESP32-S3 default UART0 RX/TX pins on this board path.

The `USB TO UART` Type-C port is not the right monitor port for this isolation
firmware when the board UART switch is in the `UART2` connector position. In
that state it is normal for a terminal attached to the USB-to-UART bridge to
show only early ESP-ROM boot output or no ESPHome logger output.

Excluded:

- `ESP-LUXPOWER`.
- `luxpower_tcp`.
- Home Assistant sensor imports.
- Wi-Fi/API/OTA for the first isolation build.
- LuxPower writes or commands.

## Wiring

Do not connect the display `5V` pin while both boards are separately powered by
USB.

| Gateway XIAO ESP32-C6 | Waveshare display connector |
| --- | --- |
| D6 / GPIO16 TX | RX |
| D7 / GPIO17 RX | TX |
| GND | GND |
| - | 5V not connected |

## Commands

Compile:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome compile sweet-power-display-test-uart-receiver.yaml
```

Upload by USB, substituting the display COM port:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome upload sweet-power-display-test-uart-receiver.yaml --device COMx
```

Open display logs, substituting the display COM port:

```powershell
C:\Projects\ESP\esphome-venv\Scripts\python.exe -m esphome logs sweet-power-display-test-uart-receiver.yaml --device COMx
```

`COMx` must be the native USB Serial/JTAG COM port from the board `USB` Type-C
connector. If Windows exposes two COM ports for the display, try the other one
before debugging the UART protocol.

Keep the gateway powered and running its validated Stage 21A.4 firmware. The
gateway should transmit one 48-byte snapshot per second on XIAO D6/GPIO16.

## Expected Logs

At boot:

```text
Display UART receiver started
RX GPIO: 44
TX GPIO: 43
Baud: 230400
Protocol version: 1
```

On first valid frame:

```text
UART LINK ESTABLISHED
sequence: ...
frame size: 48
```

Error examples:

```text
CRC ERROR
UNSUPPORTED VERSION
SEQUENCE GAP expected=... received=...
UART DATA STALE
UART LINK RESTORED
```

## Acceptance Criteria

- Display receives valid frames continuously.
- Gateway sequence increases.
- Displayed values match the gateway USB log.
- CRC error count remains zero.
- Data becomes `STALE` if the gateway is disconnected.
- Data returns to `FRESH` when the gateway reconnects.
- No recurring screen jitter over at least 10 minutes.

## Troubleshooting Order

A. Verify USB logger works.

- Connect the PC to the native Waveshare `USB` Type-C port.
- Run `esphome logs` against the corresponding USB Serial/JTAG COM port.
- Confirm ESPHome startup logs and `Display UART receiver started` appear.

B. Verify UART bytes are arriving.

- Confirm gateway TX GPIO16 is wired to display connector `RX`.
- Confirm display connector `GND` and gateway `GND` are connected.
- Confirm the Waveshare UART switch is in the `UART2` connector position.
- Leave `trace_frames: false` unless a short byte-level debug build is needed.

C. Verify protocol decoder sees frames.

- Watch `UART Valid Frames`, `UART Decode Errors`, and the on-screen
  `frames ...` counter.

D. Verify CRC.

- Watch `UART CRC Errors`; it should remain zero with correct wiring and baud.

E. Verify decoded values.

- Compare PV, SOC, energy, feed-in, TCP, and cache state against the gateway USB
  diagnostics.

## Future TX Direction

The display component includes a `send_raw_frame()` transport foundation for a
future reverse channel, but Stage 21B does not send commands.

`ESP-TELEMETRY` v0.2.0 defines telemetry snapshots only. Future command
support requires a new protocol release with command message types,
acknowledgements, transaction IDs, idempotency/replay protection, and semantic
commands rather than raw register writes.
