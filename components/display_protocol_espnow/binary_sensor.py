import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import CONF_ID, DEVICE_CLASS_CONNECTIVITY

from . import DisplayProtocolESPNowComponent

CONF_DISPLAY_PROTOCOL_ESPNOW_ID = "display_protocol_espnow_id"
CONF_GATEWAY_DATA_FRESH = "gateway_data_fresh"
CONF_GATEWAY_LINK_CONNECTED = "gateway_link_connected"
CONF_LUXPOWER_TCP_CONNECTED = "luxpower_tcp_connected"
CONF_INPUT_CACHE_VALID = "input_cache_valid"
CONF_HOLDING_CACHE_VALID = "holding_cache_valid"
CONF_SNAPSHOT_VALUES_VALID = "snapshot_values_valid"
CONF_FEED_IN_GRID_ENABLED = "feed_in_grid_enabled"

BINARY_SENSOR_MAP = {
    CONF_GATEWAY_DATA_FRESH: ("set_gateway_data_fresh_sensor", DEVICE_CLASS_CONNECTIVITY),
    CONF_GATEWAY_LINK_CONNECTED: ("set_gateway_link_connected_sensor", DEVICE_CLASS_CONNECTIVITY),
    CONF_LUXPOWER_TCP_CONNECTED: ("set_luxpower_tcp_connected_sensor", DEVICE_CLASS_CONNECTIVITY),
    CONF_INPUT_CACHE_VALID: ("set_input_cache_valid_sensor", None),
    CONF_HOLDING_CACHE_VALID: ("set_holding_cache_valid_sensor", None),
    CONF_SNAPSHOT_VALUES_VALID: ("set_snapshot_values_valid_sensor", None),
    CONF_FEED_IN_GRID_ENABLED: ("set_feed_in_grid_enabled_sensor", None),
}


def receiver_binary_sensor_schema(device_class):
    if device_class is None:
        return binary_sensor.binary_sensor_schema()
    return binary_sensor.binary_sensor_schema(device_class=device_class)


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_DISPLAY_PROTOCOL_ESPNOW_ID): cv.use_id(DisplayProtocolESPNowComponent),
        **{
            cv.Optional(key): receiver_binary_sensor_schema(device_class)
            for key, (_, device_class) in BINARY_SENSOR_MAP.items()
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_DISPLAY_PROTOCOL_ESPNOW_ID])

    for key, (setter, _device_class) in BINARY_SENSOR_MAP.items():
        if key in config:
            sens = await binary_sensor.new_binary_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))
