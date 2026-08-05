# Waveshare Display UART Pins

Stage: 21B

Board under test:

- Waveshare ESP32-S3-Touch-LCD-7
- Board marking: ESP32-S3-Touch-LCD-7 Rev1.2
- Display: 800x480

## Evidence

Primary source:

- Waveshare official schematic:
  <https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-7/ESP32-S3-Touch-LCD-7-Sch.pdf>
- Waveshare official documentation:
  <https://docs.waveshare.com/ESP32-S3-Touch-LCD-7>

Relevant schematic evidence:

- The schematic title block identifies the board as `ESP32-S3-Touch-LCD-7 V1.2`.
- The ESP32-S3-WROOM symbol shows `TXD0` and `RXD0` and also lists `GPIO43 ESP_TXD`
  and `GPIO44 ESP_RXD`.
- The board function table lists `UART`, `IO15`, `IO16`, and also `GPIO43 ESP_TXD`
  / `GPIO44 ESP_RXD`.
- The UART switching block uses `FSUSB42UMX` (`U13`) with nets:
  `UART_SEL`, `ESP_RXD`, `ESP_TXD`, `CH_RXD`, `CH_TXD`, `EX_RXD`, and `EX_TXD`.
- The external UART connector area is associated with `EX_RXD` and `EX_TXD`.

Relevant Waveshare documentation evidence:

- The board exposes a `USB Type-C Port` and a separate `USB TO UART Type-C Port UART1 Port`.
- The documentation states that the `UART2` connector and the `USB TO UART`
  port share the same UART path and are selected by the board UART switch.
- The USB Serial/JTAG-capable native USB port uses ESP32-S3 GPIO19/GPIO20.
- The documented RS485 interface is GPIO16/GPIO15; that is a separate interface
  and is not the Stage 21B external UART connector.

Interpretation:

- ESP32-S3 UART receive is `ESP_RXD`, mapped to `GPIO44`.
- ESP32-S3 UART transmit is `ESP_TXD`, mapped to `GPIO43`.
- The external connector side is `EX_RXD` / `EX_TXD`.
- The connector labels are from the display board perspective:
  - connector `RX` is display receive input;
  - connector `TX` is display transmit output.

## GPIO Mapping

| Display connector label | Signal meaning on display | ESP32-S3 net | ESP32-S3 GPIO |
| --- | --- | --- | ---: |
| RX | Receive into display ESP32-S3 | ESP_RXD / EX_RXD through UART switch | GPIO44 |
| TX | Transmit from display ESP32-S3 | ESP_TXD / EX_TXD through UART switch | GPIO43 |
| GND | Common ground | GND | - |
| 5V | Board power rail | 5V | - |

## Wiring To Gateway

Gateway:

- Seeed Studio XIAO ESP32-C6
- TX: D6 / GPIO16
- RX: D7 / GPIO17
- UART baud: 230400
- Logic level: 3.3 V

Wiring:

| Gateway | Display connector | Purpose |
| --- | --- | --- |
| XIAO D6 / GPIO16 TX | RX | Gateway telemetry into display |
| XIAO D7 / GPIO17 RX | TX | Future display-to-gateway commands/ACKs |
| XIAO GND | GND | Shared reference |
| - | 5V | Do not connect while both boards are separately USB-powered |

## Conflicts Checked

The selected UART pins are not part of the active RGB LCD, I2C, CH422G, touch,
microSD, CAN, or RS485 pin groups used by the current ESPHome display
configuration:

- RGB display uses the predefined ESPHome model
  `ESP32-S3-TOUCH-LCD-7-800X480`.
- I2C uses GPIO8/GPIO9.
- CH422G is on that I2C bus.
- The schematic lists RGB LCD signals on GPIO3-GPIO7, GPIO10-GPIO14,
  GPIO21, GPIO38-GPIO42, GPIO45-GPIO48, and related control nets.
- The external UART path uses GPIO43/GPIO44 through the UART switch block.

## USB Logger Routing

ESPHome logging must use the ESP32-S3 native USB Serial/JTAG controller:

```yaml
logger:
  hardware_uart: USB_SERIAL_JTAG
```

This keeps logging off GPIO43/GPIO44 while those pins are used by the Stage 21B
UART receiver.

The generated ESPHome build confirms this routing:

```text
logger_logger_id->set_uart_selection(logger::UART_SELECTION_USB_SERIAL_JTAG);
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y
CONFIG_ESP_CONSOLE_UART_NUM=-1
```

The generated receiver UART is ESPHome's ESP-IDF UART component on `UART0`.
ESPHome 2026.6.5 skips hardware UART reservation when the logger uses
`USB_SERIAL_JTAG`, so the first configured `uart:` component is assigned
`uart_num_ = 0`. In this firmware that UART is:

```text
ESP-IDF UART0
RX: GPIO44
TX: GPIO43
Baud: 230400
```

Practical consequence:

- ESPHome logs appear on the native `USB` Type-C port connected to
  GPIO19/GPIO20 / USB Serial-JTAG.
- ESPHome logs should not be expected on the `USB TO UART` Type-C port when the
  board UART switch is in the `UART2` connector position.
- Seeing only the ESP-ROM boot text on one COM port can mean the serial monitor
  is attached to the USB-to-UART bridge instead of the native USB Serial/JTAG
  COM port used by ESPHome.

## Voltage Warning

Use 3.3 V UART logic only.

Do not connect the display connector `5V` pin while the XIAO gateway and the
Waveshare display are separately powered from USB. Connect only TX, RX, and GND
for Stage 21B.

## Routed Directly Or Through Another Chip

The external UART connector is not a simple direct two-wire route in the
schematic. It passes through the `FSUSB42UMX` UART switch (`U13`) between
`ESP_RXD`/`ESP_TXD`, `CH_RXD`/`CH_TXD`, and `EX_RXD`/`EX_TXD`.

The Stage 21B firmware uses ESPHome UART on GPIO44/GPIO43, matching the ESP32-S3
side of that switch.

## Remaining Hardware Assumptions

- The board UART switch must expose `EX_RXD`/`EX_TXD` to the ESP32-S3 UART path
  during normal firmware execution. If no frames are seen, inspect the physical
  switch/jumper state associated with `UART_SEL` and select the `UART2`
  connector position.
- The connector silkscreen order should be visually checked before wiring; this
  document proves signal names and GPIOs, not the left-to-right orientation in a
  particular mounting position.
