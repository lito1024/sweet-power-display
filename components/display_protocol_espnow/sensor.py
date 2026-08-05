import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import (
    CONF_ID,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_MILLISECOND,
    UNIT_PERCENT,
    UNIT_WATT,
)

from . import DisplayProtocolESPNowComponent

CONF_DISPLAY_PROTOCOL_ESPNOW_ID = "display_protocol_espnow_id"
CONF_PV1_POWER = "pv1_power"
CONF_PV2_POWER = "pv2_power"
CONF_BATTERY_SOC = "battery_soc"
CONF_BATTERY_CHARGE_POWER = "battery_charge_power"
CONF_BATTERY_DISCHARGE_POWER = "battery_discharge_power"
CONF_PV1_ENERGY_TOTAL = "pv1_energy_total"
CONF_GATEWAY_SNAPSHOT_AGE = "gateway_snapshot_age"
CONF_GATEWAY_SEQUENCE = "gateway_sequence"
CONF_ESPNOW_RECEIVED_PACKETS = "espnow_received_packets"
CONF_ESPNOW_CRC_ERRORS = "espnow_crc_errors"
CONF_ESPNOW_DECODE_ERRORS = "espnow_decode_errors"
CONF_ESPNOW_SEQUENCE_GAPS = "espnow_sequence_gaps"
CONF_ESPNOW_DUPLICATE_FRAMES = "espnow_duplicate_frames"
CONF_ESPNOW_RSSI = "espnow_rssi"
CONF_ESPNOW_UNKNOWN_SENDER_REJECTS = "espnow_unknown_sender_rejects"
CONF_ESPNOW_DEVICE_ID_MISMATCHES = "espnow_device_id_mismatches"

SENSOR_MAP = {
    CONF_PV1_POWER: ("set_pv1_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_PV2_POWER: ("set_pv2_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_SOC: ("set_battery_soc_sensor", UNIT_PERCENT, DEVICE_CLASS_BATTERY, STATE_CLASS_MEASUREMENT, 1),
    CONF_BATTERY_CHARGE_POWER: ("set_battery_charge_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_DISCHARGE_POWER: ("set_battery_discharge_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_PV1_ENERGY_TOTAL: ("set_pv1_energy_total_sensor", "kWh", DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 3),
    CONF_GATEWAY_SNAPSHOT_AGE: ("set_gateway_snapshot_age_sensor", UNIT_MILLISECOND, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_GATEWAY_SEQUENCE: ("set_gateway_sequence_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ESPNOW_RECEIVED_PACKETS: ("set_espnow_received_packets_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ESPNOW_CRC_ERRORS: ("set_espnow_crc_errors_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ESPNOW_DECODE_ERRORS: ("set_espnow_decode_errors_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ESPNOW_SEQUENCE_GAPS: ("set_espnow_sequence_gaps_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ESPNOW_DUPLICATE_FRAMES: ("set_espnow_duplicate_frames_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ESPNOW_RSSI: ("set_espnow_rssi_sensor", "dBm", None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ESPNOW_UNKNOWN_SENDER_REJECTS: (
        "set_espnow_unknown_sender_rejects_sensor",
        None,
        None,
        STATE_CLASS_MEASUREMENT,
        0,
    ),
    CONF_ESPNOW_DEVICE_ID_MISMATCHES: (
        "set_espnow_device_id_mismatches_sensor",
        None,
        None,
        STATE_CLASS_MEASUREMENT,
        0,
    ),
}


def receiver_sensor_schema(unit, device_class, state_class, accuracy):
    kwargs = {
        "accuracy_decimals": accuracy,
        "state_class": state_class,
    }
    if unit is not None:
        kwargs["unit_of_measurement"] = unit
    if device_class is not None:
        kwargs["device_class"] = device_class
    schema = sensor.sensor_schema(**kwargs)
    return schema


CONFIG_SCHEMA = cv.Schema(
    {
            cv.GenerateID(CONF_DISPLAY_PROTOCOL_ESPNOW_ID): cv.use_id(DisplayProtocolESPNowComponent),
        **{
            cv.Optional(key): receiver_sensor_schema(unit, device_class, state_class, accuracy)
            for key, (_, unit, device_class, state_class, accuracy) in SENSOR_MAP.items()
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_DISPLAY_PROTOCOL_ESPNOW_ID])

    for key, (setter, *_metadata) in SENSOR_MAP.items():
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))
