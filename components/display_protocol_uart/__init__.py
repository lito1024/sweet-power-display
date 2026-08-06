import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import uart
from esphome.const import CONF_ID

DEPENDENCIES = ["uart"]
AUTO_LOAD = ["sensor", "binary_sensor", "text_sensor"]
MULTI_CONF = False

display_protocol_uart_ns = cg.esphome_ns.namespace("display_protocol_uart")
DisplayProtocolUARTComponent = display_protocol_uart_ns.class_(
    "DisplayProtocolUARTComponent", cg.Component, uart.UARTDevice
)

CONF_STALE_TIMEOUT = "stale_timeout"
CONF_TRACE_FRAMES = "trace_frames"
CONF_RX_GPIO = "rx_gpio"
CONF_TX_GPIO = "tx_gpio"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(DisplayProtocolUARTComponent),
        cv.Optional(CONF_STALE_TIMEOUT, default="5s"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_TRACE_FRAMES, default=False): cv.boolean,
        cv.Optional(CONF_RX_GPIO, default=44): cv.int_range(min=0, max=48),
        cv.Optional(CONF_TX_GPIO, default=43): cv.int_range(min=0, max=48),
    }
).extend(cv.COMPONENT_SCHEMA).extend(uart.UART_DEVICE_SCHEMA)

FINAL_VALIDATE_SCHEMA = uart.final_validate_device_schema(
    "display_protocol_uart",
    baud_rate=230400,
    require_tx=True,
    require_rx=True,
    data_bits=8,
    parity="NONE",
    stop_bits=1,
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)

    cg.add(var.set_stale_timeout(config[CONF_STALE_TIMEOUT]))
    cg.add(var.set_trace_frames(config[CONF_TRACE_FRAMES]))
    cg.add(var.set_rx_gpio(config[CONF_RX_GPIO]))
    cg.add(var.set_tx_gpio(config[CONF_TX_GPIO]))
