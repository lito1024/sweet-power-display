import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import CONF_ID, DEVICE_CLASS_CONNECTIVITY

from . import DisplayProtocolUARTComponent

CONF_DISPLAY_PROTOCOL_UART_ID = "display_protocol_uart_id"
CONF_GATEWAY_DATA_FRESH = "gateway_data_fresh"
CONF_GATEWAY_LINK_CONNECTED = "gateway_link_connected"
CONF_LUXPOWER_TCP_CONNECTED = "luxpower_tcp_connected"
CONF_INPUT_CACHE_VALID = "input_cache_valid"
CONF_HOLDING_CACHE_VALID = "holding_cache_valid"
CONF_SNAPSHOT_VALUES_VALID = "snapshot_values_valid"
CONF_FEED_IN_GRID_ENABLED = "feed_in_grid_enabled"
# Stage 35: experimentally confirmed export-control readback (holding
# register 21 bit 15) -- see stages/Stage35.md. Read-only, not the same
# register as feed_in_grid_enabled above (which failed the same test).
CONF_ZERO_EXPORT_ENABLED = "zero_export_enabled"
CONF_DISPLAY_ENABLED = "display_enabled"
CONF_DISPLAY_MAINTENANCE_WIFI_REQUESTED = "display_maintenance_wifi_requested"
CONF_SYSTEM_LINK_CONNECTED = "system_link_connected"

BINARY_SENSOR_MAP = {
    CONF_GATEWAY_DATA_FRESH: ("set_gateway_data_fresh_sensor", DEVICE_CLASS_CONNECTIVITY),
    CONF_GATEWAY_LINK_CONNECTED: ("set_gateway_link_connected_sensor", DEVICE_CLASS_CONNECTIVITY),
    CONF_LUXPOWER_TCP_CONNECTED: ("set_luxpower_tcp_connected_sensor", DEVICE_CLASS_CONNECTIVITY),
    CONF_INPUT_CACHE_VALID: ("set_input_cache_valid_sensor", None),
    CONF_HOLDING_CACHE_VALID: ("set_holding_cache_valid_sensor", None),
    CONF_SNAPSHOT_VALUES_VALID: ("set_snapshot_values_valid_sensor", None),
    CONF_FEED_IN_GRID_ENABLED: ("set_feed_in_grid_enabled_sensor", None),
    CONF_ZERO_EXPORT_ENABLED: ("set_zero_export_enabled_sensor", None),
}

SYSTEM_BINARY_SENSOR_MAP = {
    CONF_DISPLAY_ENABLED: ("set_display_enabled_sensor", None),
    CONF_DISPLAY_MAINTENANCE_WIFI_REQUESTED: ("set_display_maintenance_wifi_requested_sensor", None),
    CONF_SYSTEM_LINK_CONNECTED: ("set_system_link_connected_sensor", DEVICE_CLASS_CONNECTIVITY),
}


def receiver_binary_sensor_schema(device_class):
    if device_class is None:
        return binary_sensor.binary_sensor_schema()
    return binary_sensor.binary_sensor_schema(device_class=device_class)


# Stage 32: every entry here is now a per-device [kDeviceCount] array on the
# component (link/cache state and feed_in_grid_enabled are all per-source),
# so every config key is doubled into inverter1_<key>/inverter2_<key>,
# published through the generic (device_index, sensor) setter. There are no
# whole-link-global binary sensors left (unlike sensor.py's UART frame
# counters).
DEVICE_PROFILES = [(0, "inverter1"), (1, "inverter2")]


def _per_device_key(prefix: str, base_key: str) -> str:
    return f"{prefix}_{base_key}"


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_DISPLAY_PROTOCOL_UART_ID): cv.use_id(DisplayProtocolUARTComponent),
        **{
            cv.Optional(key): receiver_binary_sensor_schema(device_class)
            for key, (_, device_class) in SYSTEM_BINARY_SENSOR_MAP.items()
        },
        **{
            cv.Optional(_per_device_key(prefix, key)): receiver_binary_sensor_schema(device_class)
            for key, (_, device_class) in BINARY_SENSOR_MAP.items()
            for _device_index, prefix in DEVICE_PROFILES
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_DISPLAY_PROTOCOL_UART_ID])

    for key, (setter, _device_class) in SYSTEM_BINARY_SENSOR_MAP.items():
        if key in config:
            sens = await binary_sensor.new_binary_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))

    for key, (setter, _device_class) in BINARY_SENSOR_MAP.items():
        for device_index, prefix in DEVICE_PROFILES:
            config_key = _per_device_key(prefix, key)
            if config_key in config:
                sens = await binary_sensor.new_binary_sensor(config[config_key])
                cg.add(getattr(parent, setter)(device_index, sens))
