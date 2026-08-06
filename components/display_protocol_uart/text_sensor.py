import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor

from . import DisplayProtocolUARTComponent

CONF_DISPLAY_PROTOCOL_UART_ID = "display_protocol_uart_id"
CONF_CONNECTION_STATUS = "connection_status"

# Stage 33: CONNECTED / STALE / DISCONNECTED, per device -- derived by the
# component itself from the existing have_snapshot_/data_fresh_ state (see
# DisplayProtocolUARTComponent::update_connection_status_). No separate
# timeout mechanism.
TEXT_SENSOR_MAP = {
    CONF_CONNECTION_STATUS: "set_connection_status_text_sensor",
}

DEVICE_PROFILES = [(0, "inverter1"), (1, "inverter2")]


def _per_device_key(prefix: str, base_key: str) -> str:
    return f"{prefix}_{base_key}"


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_DISPLAY_PROTOCOL_UART_ID): cv.use_id(DisplayProtocolUARTComponent),
        **{
            cv.Optional(_per_device_key(prefix, key)): text_sensor.text_sensor_schema()
            for key in TEXT_SENSOR_MAP
            for _device_index, prefix in DEVICE_PROFILES
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_DISPLAY_PROTOCOL_UART_ID])

    for key, setter in TEXT_SENSOR_MAP.items():
        for device_index, prefix in DEVICE_PROFILES:
            config_key = _per_device_key(prefix, key)
            if config_key in config:
                sens = await text_sensor.new_text_sensor(config[config_key])
                cg.add(getattr(parent, setter)(device_index, sens))
