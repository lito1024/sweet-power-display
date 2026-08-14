import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import (
    CONF_ID,
    DEVICE_CLASS_APPARENT_POWER,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_FREQUENCY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_AMPERE,
    UNIT_CELSIUS,
    UNIT_HERTZ,
    UNIT_KILOWATT_HOURS,
    UNIT_MILLISECOND,
    UNIT_PERCENT,
    UNIT_SECOND,
    UNIT_VOLT,
    UNIT_VOLT_AMPS,
    UNIT_WATT,
)

from . import DisplayProtocolUARTComponent

CONF_DISPLAY_PROTOCOL_UART_ID = "display_protocol_uart_id"
CONF_PV1_POWER = "pv1_power"
CONF_PV2_POWER = "pv2_power"
CONF_BATTERY_SOC = "battery_soc"
CONF_BATTERY_CHARGE_POWER = "battery_charge_power"
CONF_BATTERY_DISCHARGE_POWER = "battery_discharge_power"
CONF_PV1_ENERGY_TOTAL = "pv1_energy_total"
CONF_GATEWAY_SNAPSHOT_AGE = "gateway_snapshot_age"
CONF_GATEWAY_SEQUENCE = "gateway_sequence"
CONF_UART_VALID_FRAMES = "uart_valid_frames"
CONF_UART_CRC_ERRORS = "uart_crc_errors"
CONF_UART_DECODE_ERRORS = "uart_decode_errors"
CONF_UART_SEQUENCE_GAPS = "uart_sequence_gaps"
CONF_UART_DUPLICATE_FRAMES = "uart_duplicate_frames"
CONF_BATTERY_CAPACITY = "battery_capacity"
CONF_BMS_MAX_CELL_TEMPERATURE = "bms_max_cell_temperature"
CONF_POWER_TO_GRID = "power_to_grid"
CONF_POWER_FROM_GRID = "power_from_grid"
CONF_GRID_FLOW = "grid_flow"

# Stage 30: 79 additional production entities, sourced from the upstream
# luxpower-ha-integration register map (see FULL_ENTITY_COVERAGE.md).
CONF_PV1_VOLTAGE = "pv1_voltage"
CONF_PV2_VOLTAGE = "pv2_voltage"
CONF_PV3_VOLTAGE = "pv3_voltage"
CONF_PV3_POWER = "pv3_power"
CONF_PV1_ENERGY_TODAY = "pv1_energy_today"
CONF_PV2_ENERGY_TODAY = "pv2_energy_today"
CONF_PV3_ENERGY_TODAY = "pv3_energy_today"
CONF_PV2_ENERGY_TOTAL = "pv2_energy_total"
CONF_PV3_ENERGY_TOTAL = "pv3_energy_total"
CONF_BATTERY_VOLTAGE = "battery_voltage"
CONF_BATTERY_SOH = "battery_soh"
CONF_BATTERY_TEMPERATURE = "battery_temperature"
CONF_BATTERY_PARALLEL_NUMBER = "battery_parallel_number"
CONF_BATTERY_TYPE_AND_BRAND = "battery_type_and_brand"
CONF_BMS_MAX_CHARGE_CURRENT = "bms_max_charge_current"
CONF_BMS_MAX_DISCHARGE_CURRENT = "bms_max_discharge_current"
CONF_BMS_CHARGE_VOLTAGE_REFERENCE = "bms_charge_voltage_reference"
CONF_BMS_DISCHARGE_CUTOFF_VOLTAGE = "bms_discharge_cutoff_voltage"
CONF_BMS_BATTERY_CURRENT = "bms_battery_current"
CONF_BMS_FAULT_CODE = "bms_fault_code"
CONF_BMS_WARNING_CODE = "bms_warning_code"
CONF_BMS_MAX_CELL_VOLTAGE = "bms_max_cell_voltage"
CONF_BMS_MIN_CELL_VOLTAGE = "bms_min_cell_voltage"
CONF_BMS_MIN_CELL_TEMPERATURE = "bms_min_cell_temperature"
CONF_BMS_FIRMWARE_UPDATE_STATE = "bms_firmware_update_state"
CONF_BMS_CYCLE_COUNT = "bms_cycle_count"
CONF_INVERTER_BATTERY_VOLTAGE_SAMPLE = "inverter_battery_voltage_sample"
CONF_CHARGE_ENERGY_TODAY = "charge_energy_today"
CONF_DISCHARGE_ENERGY_TODAY = "discharge_energy_today"
CONF_CHARGE_ENERGY_TOTAL = "charge_energy_total"
CONF_DISCHARGE_ENERGY_TOTAL = "discharge_energy_total"
CONF_GRID_VOLTAGE = "grid_voltage"
CONF_GRID_VOLTAGE_S = "grid_voltage_s"
CONF_GRID_VOLTAGE_T = "grid_voltage_t"
CONF_GRID_FREQUENCY = "grid_frequency"
CONF_INVERTER_POWER = "inverter_power"
CONF_AC_CHARGING_RECTIFICATION_POWER = "ac_charging_rectification_power"
CONF_INVERTER_CURRENT = "inverter_current"
CONF_POWER_FACTOR = "power_factor"
CONF_ENERGY_TO_GRID_TODAY = "energy_to_grid_today"
CONF_ENERGY_FROM_GRID_TODAY = "energy_from_grid_today"
CONF_ENERGY_TO_GRID_TOTAL = "energy_to_grid_total"
CONF_ENERGY_FROM_GRID_TOTAL = "energy_from_grid_total"
CONF_ONGRID_LOAD_POWER = "ongrid_load_power"
CONF_BUS1_VOLTAGE = "bus1_voltage"
CONF_BUS2_VOLTAGE = "bus2_voltage"
CONF_HALF_BUS_VOLTAGE = "half_bus_voltage"
CONF_EPS_VOLTAGE = "eps_voltage"
CONF_EPS_VOLTAGE_S = "eps_voltage_s"
CONF_EPS_VOLTAGE_T = "eps_voltage_t"
CONF_EPS_FREQUENCY = "eps_frequency"
CONF_EPS_POWER = "eps_power"
CONF_EPS_APPARENT_POWER = "eps_apparent_power"
CONF_EPS_ENERGY_TODAY = "eps_energy_today"
CONF_EPS_ENERGY_TOTAL = "eps_energy_total"
CONF_INTERNAL_TEMPERATURE = "internal_temperature"
CONF_RADIATOR_TEMPERATURE = "radiator_temperature"
CONF_RADIATOR_TEMPERATURE_2 = "radiator_temperature_2"
CONF_INVERTER_STATE = "inverter_state"
CONF_INTERNAL_FAULT_CODE = "internal_fault_code"
CONF_AC_INPUT_TYPE = "ac_input_type"
CONF_AUTO_TEST_STATUS = "auto_test_status"
CONF_INVERTER_ENERGY_TODAY = "inverter_energy_today"
CONF_AC_CHARGE_ENERGY_TODAY = "ac_charge_energy_today"
CONF_INVERTER_ENERGY_TOTAL = "inverter_energy_total"
CONF_AC_CHARGE_ENERGY_TOTAL = "ac_charge_energy_total"
CONF_TOTAL_RUNNING_TIME = "total_running_time"
CONF_GENERATOR_VOLTAGE = "generator_voltage"
CONF_GENERATOR_FREQUENCY = "generator_frequency"
CONF_GENERATOR_POWER = "generator_power"
CONF_GENERATOR_ENERGY_TODAY = "generator_energy_today"
CONF_PV1_CURRENT = "pv1_current"
CONF_PV2_CURRENT = "pv2_current"
CONF_PV3_CURRENT = "pv3_current"
CONF_BATTERY_FLOW = "battery_flow"
CONF_BMS_CELL_DIFFERENCE = "bms_cell_difference"
CONF_GRID_CONNECTED = "grid_connected"
CONF_ACTIVE_FAULT_CODE = "active_fault_code"
CONF_ACTIVE_WARNING_CODE = "active_warning_code"
# Stage 31: load_power (FieldId 9085), FAST class, via the new input block 2.
CONF_LOAD_POWER = "load_power"
# Stage 35: experimentally confirmed export-control readback (holding
# register 103, raw == percent) -- see stages/Stage35.md. Read-only.
CONF_MAX_BACKFLOW_POWER = "max_backflow_power"

# Stage 37: presentation-layer derived values -- see recompute_derived_ in
# display_protocol_uart.cpp. Per-device (Solar/Power/Grid/Battery) plus
# TOTAL (both inverters combined, or unavailable if either inverter is).
CONF_SOLAR = "solar"
CONF_DERIVED_POWER = "derived_power"
CONF_GRID_NET = "grid_net"
CONF_BATTERY_NET = "battery_net"
CONF_SOLAR_TOTAL = "solar_total"
CONF_POWER_TOTAL = "power_total"
CONF_GRID_TOTAL = "grid_total"
CONF_BATTERY_TOTAL = "battery_total"
CONF_SYSTEM_OUTPUT_VOLTAGE = "system_output_voltage"
CONF_SYSTEM_OUTPUT_CURRENT = "system_output_current"
CONF_SYSTEM_OUTPUT_POWER = "system_output_power"
CONF_SYSTEM_OUTPUT_ENERGY = "system_output_energy"
CONF_SYSTEM_OUTPUT_FREQUENCY = "system_output_frequency"
CONF_SYSTEM_OUTPUT_POWER_FACTOR = "system_output_power_factor"
CONF_GRID_INPUT_VOLTAGE = "grid_input_voltage"
CONF_GRID_INPUT_CURRENT = "grid_input_current"
CONF_GRID_INPUT_POWER = "grid_input_power"
CONF_GRID_INPUT_ENERGY = "grid_input_energy"
CONF_GRID_INPUT_FREQUENCY = "grid_input_frequency"
CONF_GRID_INPUT_POWER_FACTOR = "grid_input_power_factor"
CONF_GRID_RAW_VOLTAGE = "grid_raw_voltage"

SENSOR_MAP = {
    CONF_PV1_POWER: ("set_pv1_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_PV2_POWER: ("set_pv2_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_SOC: ("set_battery_soc_sensor", UNIT_PERCENT, DEVICE_CLASS_BATTERY, STATE_CLASS_MEASUREMENT, 1),
    CONF_BATTERY_CHARGE_POWER: ("set_battery_charge_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_DISCHARGE_POWER: ("set_battery_discharge_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_PV1_ENERGY_TOTAL: ("set_pv1_energy_total_sensor", "kWh", DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 3),
    CONF_GATEWAY_SNAPSHOT_AGE: ("set_gateway_snapshot_age_sensor", UNIT_MILLISECOND, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_GATEWAY_SEQUENCE: ("set_gateway_sequence_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_UART_VALID_FRAMES: ("set_uart_valid_frames_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_UART_CRC_ERRORS: ("set_uart_crc_errors_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_UART_DECODE_ERRORS: ("set_uart_decode_errors_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_UART_SEQUENCE_GAPS: ("set_uart_sequence_gaps_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_UART_DUPLICATE_FRAMES: ("set_uart_duplicate_frames_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_CAPACITY: (
        "set_battery_capacity_sensor",
        "Ah",
        None,
        STATE_CLASS_MEASUREMENT,
        0,
    ),
    CONF_BMS_MAX_CELL_TEMPERATURE: (
        "set_bms_max_cell_temperature_sensor",
        UNIT_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        STATE_CLASS_MEASUREMENT,
        1,
    ),
    CONF_POWER_TO_GRID: (
        "set_power_to_grid_sensor",
        UNIT_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
        0,
    ),
    CONF_POWER_FROM_GRID: (
        "set_power_from_grid_sensor",
        UNIT_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
        0,
    ),
    CONF_GRID_FLOW: (
        "set_grid_flow_sensor",
        UNIT_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
        0,
    ),
    CONF_PV1_VOLTAGE: ("set_pv1_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_PV2_VOLTAGE: ("set_pv2_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_PV3_VOLTAGE: ("set_pv3_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_PV3_POWER: ("set_pv3_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_PV1_ENERGY_TODAY: ("set_pv1_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_PV2_ENERGY_TODAY: ("set_pv2_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_PV3_ENERGY_TODAY: ("set_pv3_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_PV2_ENERGY_TOTAL: ("set_pv2_energy_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_PV3_ENERGY_TOTAL: ("set_pv3_energy_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_BATTERY_VOLTAGE: ("set_battery_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_BATTERY_SOH: ("set_battery_soh_sensor", UNIT_PERCENT, DEVICE_CLASS_BATTERY, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_TEMPERATURE: ("set_battery_temperature_sensor", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_PARALLEL_NUMBER: ("set_battery_parallel_number_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_TYPE_AND_BRAND: ("set_battery_type_and_brand_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_BMS_MAX_CHARGE_CURRENT: ("set_bms_max_charge_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 1),
    CONF_BMS_MAX_DISCHARGE_CURRENT: ("set_bms_max_discharge_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 1),
    CONF_BMS_CHARGE_VOLTAGE_REFERENCE: ("set_bms_charge_voltage_reference_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_BMS_DISCHARGE_CUTOFF_VOLTAGE: ("set_bms_discharge_cutoff_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_BMS_BATTERY_CURRENT: ("set_bms_battery_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 1),
    CONF_BMS_FAULT_CODE: ("set_bms_fault_code_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_BMS_WARNING_CODE: ("set_bms_warning_code_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_BMS_MAX_CELL_VOLTAGE: ("set_bms_max_cell_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 3),
    CONF_BMS_MIN_CELL_VOLTAGE: ("set_bms_min_cell_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 3),
    CONF_BMS_MIN_CELL_TEMPERATURE: ("set_bms_min_cell_temperature_sensor", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, STATE_CLASS_MEASUREMENT, 1),
    CONF_BMS_FIRMWARE_UPDATE_STATE: ("set_bms_firmware_update_state_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_BMS_CYCLE_COUNT: ("set_bms_cycle_count_sensor", None, None, STATE_CLASS_TOTAL_INCREASING, 0),
    CONF_INVERTER_BATTERY_VOLTAGE_SAMPLE: ("set_inverter_battery_voltage_sample_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_CHARGE_ENERGY_TODAY: ("set_charge_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_DISCHARGE_ENERGY_TODAY: ("set_discharge_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_CHARGE_ENERGY_TOTAL: ("set_charge_energy_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_DISCHARGE_ENERGY_TOTAL: ("set_discharge_energy_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_GRID_VOLTAGE: ("set_grid_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_GRID_VOLTAGE_S: ("set_grid_voltage_s_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_GRID_VOLTAGE_T: ("set_grid_voltage_t_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_GRID_FREQUENCY: ("set_grid_frequency_sensor", UNIT_HERTZ, DEVICE_CLASS_FREQUENCY, STATE_CLASS_MEASUREMENT, 2),
    CONF_INVERTER_POWER: ("set_inverter_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_AC_CHARGING_RECTIFICATION_POWER: ("set_ac_charging_rectification_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_INVERTER_CURRENT: ("set_inverter_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 2),
    CONF_POWER_FACTOR: ("set_power_factor_sensor", UNIT_PERCENT, None, STATE_CLASS_MEASUREMENT, 3),
    CONF_ENERGY_TO_GRID_TODAY: ("set_energy_to_grid_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_ENERGY_FROM_GRID_TODAY: ("set_energy_from_grid_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_ENERGY_TO_GRID_TOTAL: ("set_energy_to_grid_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_ENERGY_FROM_GRID_TOTAL: ("set_energy_from_grid_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_ONGRID_LOAD_POWER: ("set_ongrid_load_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_BUS1_VOLTAGE: ("set_bus1_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_BUS2_VOLTAGE: ("set_bus2_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_HALF_BUS_VOLTAGE: ("set_half_bus_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_EPS_VOLTAGE: ("set_eps_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_EPS_VOLTAGE_S: ("set_eps_voltage_s_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_EPS_VOLTAGE_T: ("set_eps_voltage_t_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_EPS_FREQUENCY: ("set_eps_frequency_sensor", UNIT_HERTZ, DEVICE_CLASS_FREQUENCY, STATE_CLASS_MEASUREMENT, 2),
    CONF_EPS_POWER: ("set_eps_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_EPS_APPARENT_POWER: ("set_eps_apparent_power_sensor", UNIT_VOLT_AMPS, DEVICE_CLASS_APPARENT_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_EPS_ENERGY_TODAY: ("set_eps_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_EPS_ENERGY_TOTAL: ("set_eps_energy_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_INTERNAL_TEMPERATURE: ("set_internal_temperature_sensor", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, STATE_CLASS_MEASUREMENT, 0),
    CONF_RADIATOR_TEMPERATURE: ("set_radiator_temperature_sensor", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, STATE_CLASS_MEASUREMENT, 0),
    CONF_RADIATOR_TEMPERATURE_2: ("set_radiator_temperature_2_sensor", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, STATE_CLASS_MEASUREMENT, 0),
    CONF_INVERTER_STATE: ("set_inverter_state_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_INTERNAL_FAULT_CODE: ("set_internal_fault_code_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_AC_INPUT_TYPE: ("set_ac_input_type_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_AUTO_TEST_STATUS: ("set_auto_test_status_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_INVERTER_ENERGY_TODAY: ("set_inverter_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_AC_CHARGE_ENERGY_TODAY: ("set_ac_charge_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_INVERTER_ENERGY_TOTAL: ("set_inverter_energy_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_AC_CHARGE_ENERGY_TOTAL: ("set_ac_charge_energy_total_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_TOTAL_RUNNING_TIME: ("set_total_running_time_sensor", UNIT_SECOND, None, STATE_CLASS_TOTAL_INCREASING, 0),
    CONF_GENERATOR_VOLTAGE: ("set_generator_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_GENERATOR_FREQUENCY: ("set_generator_frequency_sensor", UNIT_HERTZ, DEVICE_CLASS_FREQUENCY, STATE_CLASS_MEASUREMENT, 2),
    CONF_GENERATOR_POWER: ("set_generator_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_GENERATOR_ENERGY_TODAY: ("set_generator_energy_today_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 1),
    CONF_PV1_CURRENT: ("set_pv1_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 2),
    CONF_PV2_CURRENT: ("set_pv2_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 2),
    CONF_PV3_CURRENT: ("set_pv3_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 2),
    CONF_BATTERY_FLOW: ("set_battery_flow_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_BMS_CELL_DIFFERENCE: ("set_bms_cell_difference_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 3),
    CONF_GRID_CONNECTED: ("set_grid_connected_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ACTIVE_FAULT_CODE: ("set_active_fault_code_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_ACTIVE_WARNING_CODE: ("set_active_warning_code_sensor", None, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_LOAD_POWER: ("set_load_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_MAX_BACKFLOW_POWER: ("set_max_backflow_power_sensor", UNIT_PERCENT, None, STATE_CLASS_MEASUREMENT, 0),
    CONF_SOLAR: ("set_solar_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_DERIVED_POWER: ("set_derived_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_GRID_NET: ("set_grid_net_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_NET: ("set_battery_net_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    # Stage 37: TOTAL (both inverters combined) -- single instance, not
    # per-device, same mechanism as the whole-UART-link counters below.
    CONF_SOLAR_TOTAL: ("set_solar_total_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_POWER_TOTAL: ("set_power_total_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_GRID_TOTAL: ("set_grid_total_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_BATTERY_TOTAL: ("set_battery_total_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_SYSTEM_OUTPUT_VOLTAGE: ("set_system_output_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_SYSTEM_OUTPUT_CURRENT: ("set_system_output_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 1),
    CONF_SYSTEM_OUTPUT_POWER: ("set_system_output_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_SYSTEM_OUTPUT_ENERGY: ("set_system_output_energy_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 2),
    CONF_SYSTEM_OUTPUT_FREQUENCY: ("set_system_output_frequency_sensor", UNIT_HERTZ, DEVICE_CLASS_FREQUENCY, STATE_CLASS_MEASUREMENT, 1),
    CONF_SYSTEM_OUTPUT_POWER_FACTOR: ("set_system_output_power_factor_sensor", None, DEVICE_CLASS_POWER_FACTOR, STATE_CLASS_MEASUREMENT, 2),
    CONF_GRID_INPUT_VOLTAGE: ("set_grid_input_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
    CONF_GRID_INPUT_CURRENT: ("set_grid_input_current_sensor", UNIT_AMPERE, DEVICE_CLASS_CURRENT, STATE_CLASS_MEASUREMENT, 1),
    CONF_GRID_INPUT_POWER: ("set_grid_input_power_sensor", UNIT_WATT, DEVICE_CLASS_POWER, STATE_CLASS_MEASUREMENT, 0),
    CONF_GRID_INPUT_ENERGY: ("set_grid_input_energy_sensor", UNIT_KILOWATT_HOURS, DEVICE_CLASS_ENERGY, STATE_CLASS_TOTAL_INCREASING, 2),
    CONF_GRID_INPUT_FREQUENCY: ("set_grid_input_frequency_sensor", UNIT_HERTZ, DEVICE_CLASS_FREQUENCY, STATE_CLASS_MEASUREMENT, 1),
    CONF_GRID_INPUT_POWER_FACTOR: ("set_grid_input_power_factor_sensor", None, DEVICE_CLASS_POWER_FACTOR, STATE_CLASS_MEASUREMENT, 2),
    CONF_GRID_RAW_VOLTAGE: ("set_grid_raw_voltage_sensor", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, STATE_CLASS_MEASUREMENT, 1),
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


# Stage 32: split SENSOR_MAP into per-device (doubled into an
# inverter1_<key>/inverter2_<key> config key pair, published through the
# generic (device_index, sensor) setter -- see
# DisplayProtocolUARTComponent::kDeviceCount) and whole-UART-link-global
# (single config key, unchanged single-arg setter -- these describe the
# physical link itself, not one source; CRC errors and malformed frames
# happen before a device_id is even parseable, see display_protocol_uart.h).
GLOBAL_ONLY_KEYS = {
    CONF_UART_VALID_FRAMES,
    CONF_UART_CRC_ERRORS,
    CONF_UART_DECODE_ERRORS,
    CONF_UART_SEQUENCE_GAPS,
    CONF_UART_DUPLICATE_FRAMES,
    # Stage 37: TOTAL derived sensors are also single-instance (both
    # inverters combined into one value, not one per device) -- see
    # combine_total_ in display_protocol_uart.cpp.
    CONF_SOLAR_TOTAL,
    CONF_POWER_TOTAL,
    CONF_GRID_TOTAL,
    CONF_BATTERY_TOTAL,
    # Stage 39B: Controller/system source (device_id 3), not per-inverter.
    CONF_SYSTEM_OUTPUT_VOLTAGE,
    CONF_SYSTEM_OUTPUT_CURRENT,
    CONF_SYSTEM_OUTPUT_POWER,
    CONF_SYSTEM_OUTPUT_ENERGY,
    CONF_SYSTEM_OUTPUT_FREQUENCY,
    CONF_SYSTEM_OUTPUT_POWER_FACTOR,
    CONF_GRID_INPUT_VOLTAGE,
    CONF_GRID_INPUT_CURRENT,
    CONF_GRID_INPUT_POWER,
    CONF_GRID_INPUT_ENERGY,
    CONF_GRID_INPUT_FREQUENCY,
    CONF_GRID_INPUT_POWER_FACTOR,
    CONF_GRID_RAW_VOLTAGE,
}

PER_DEVICE_SENSOR_MAP = {k: v for k, v in SENSOR_MAP.items() if k not in GLOBAL_ONLY_KEYS}
GLOBAL_SENSOR_MAP = {k: v for k, v in SENSOR_MAP.items() if k in GLOBAL_ONLY_KEYS}

# device_index 0 = inverter1 (device_id 1), 1 = inverter2 (device_id 2).
DEVICE_PROFILES = [(0, "inverter1"), (1, "inverter2")]


def _per_device_key(prefix: str, base_key: str) -> str:
    return f"{prefix}_{base_key}"


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_DISPLAY_PROTOCOL_UART_ID): cv.use_id(DisplayProtocolUARTComponent),
        **{
            cv.Optional(_per_device_key(prefix, key)): receiver_sensor_schema(unit, device_class, state_class, accuracy)
            for key, (_, unit, device_class, state_class, accuracy) in PER_DEVICE_SENSOR_MAP.items()
            for _device_index, prefix in DEVICE_PROFILES
        },
        **{
            cv.Optional(key): receiver_sensor_schema(unit, device_class, state_class, accuracy)
            for key, (_, unit, device_class, state_class, accuracy) in GLOBAL_SENSOR_MAP.items()
        },
    }
)


async def to_code(config):
    parent = await cg.get_variable(config[CONF_DISPLAY_PROTOCOL_UART_ID])

    for key, (setter, *_metadata) in PER_DEVICE_SENSOR_MAP.items():
        for device_index, prefix in DEVICE_PROFILES:
            config_key = _per_device_key(prefix, key)
            if config_key in config:
                sens = await sensor.new_sensor(config[config_key])
                cg.add(getattr(parent, setter)(device_index, sens))

    for key, (setter, *_metadata) in GLOBAL_SENSOR_MAP.items():
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(getattr(parent, setter)(sens))
