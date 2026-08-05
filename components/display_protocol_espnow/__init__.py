import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["wifi"]
AUTO_LOAD = ["sensor", "binary_sensor"]
MULTI_CONF = False

display_protocol_espnow_ns = cg.esphome_ns.namespace("display_protocol_espnow")
DisplayProtocolESPNowComponent = display_protocol_espnow_ns.class_(
    "DisplayProtocolESPNowComponent", cg.Component
)

CONF_STALE_TIMEOUT = "stale_timeout"
CONF_TRACE_FRAMES = "trace_frames"
CONF_DEVICE_PEERS = "device_peers"
CONF_DEVICE_ID = "device_id"
CONF_MAC = "mac"


def validate_mac(value):
    value = cv.string_strict(value)
    parts = value.split(":")
    if len(parts) != 6:
        raise cv.Invalid("MAC address must contain 6 colon-separated bytes")
    try:
        mac = [int(part, 16) for part in parts]
    except ValueError as err:
        raise cv.Invalid("MAC address bytes must be hexadecimal") from err
    if any(byte < 0 or byte > 0xFF for byte in mac):
        raise cv.Invalid("MAC address byte out of range")
    return mac


PEER_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_DEVICE_ID): cv.int_range(min=1, max=255),
        cv.Required(CONF_MAC): validate_mac,
    }
)


def validate_peers(value):
    peers = cv.ensure_list(PEER_SCHEMA)(value)
    seen_device_ids = set()
    seen_macs = set()
    for peer in peers:
        device_id = peer[CONF_DEVICE_ID]
        mac = tuple(peer[CONF_MAC])
        if device_id in seen_device_ids:
            raise cv.Invalid(f"duplicate device_id {device_id}")
        if mac in seen_macs:
            raise cv.Invalid("duplicate MAC address")
        seen_device_ids.add(device_id)
        seen_macs.add(mac)
    if len(peers) > 4:
        raise cv.Invalid("display_protocol_espnow supports up to 4 trusted peers")
    return peers

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(DisplayProtocolESPNowComponent),
        cv.Optional(CONF_STALE_TIMEOUT, default="5s"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_TRACE_FRAMES, default=False): cv.boolean,
        cv.Required(CONF_DEVICE_PEERS): validate_peers,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_stale_timeout(config[CONF_STALE_TIMEOUT]))
    cg.add(var.set_trace_frames(config[CONF_TRACE_FRAMES]))
    for peer in config[CONF_DEVICE_PEERS]:
        cg.add(var.add_device_peer(peer[CONF_DEVICE_ID], *peer[CONF_MAC]))
