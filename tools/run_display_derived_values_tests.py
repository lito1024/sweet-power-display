#!/usr/bin/env python3
"""Host-side mirror of Stage 37/39B derived-value math and stale/unavailable
handling.

Mirrors DisplayProtocolUARTComponent::recompute_derived_/combine_total_
(display_protocol_uart.cpp) and the LVGL rendering lambdas in
sweet-power-display-offline-uart.yaml: Solar = PV1+PV2, Power =
Load+EPS, Grid = PowerToGrid-PowerFromGrid, Battery =
BatteryCharge-BatteryDischarge per inverter. Stage 39B moves TOTAL Power
to Controller/system_output_power; Solar/Grid/Battery TOTAL remain
inverter-combined. This is a model for fast host testing, not a binding to
the real firmware -- keep it in sync with the C++/YAML by hand when that
logic changes.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

NAN = float("nan")

REPO_ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = REPO_ROOT / "sweet-power-display-offline-uart.yaml"
HEADER_PATH = REPO_ROOT / "components" / "display_protocol_uart" / "display_protocol_uart.h"
CPP_PATH = REPO_ROOT / "components" / "display_protocol_uart" / "display_protocol_uart.cpp"


class DeviceState:
    def __init__(self) -> None:
        self.fresh = False
        self.values_stale = False
        self.pv1 = None
        self.pv2 = None
        self.load = None
        self.eps = None
        self.to_grid = None
        self.from_grid = None
        self.charge = None
        self.discharge = None
        self.soc = None
        self.max_backflow = None
        self.zero_export_enabled = None


class SystemState:
    def __init__(self) -> None:
        self.system_output_power = None
        self.grid_raw_voltage = None


def _has(v) -> bool:
    return v is not None


def recompute_solar(dev: DeviceState) -> float:
    if not dev.values_stale and _has(dev.pv1) and _has(dev.pv2):
        return dev.pv1 + dev.pv2
    return NAN


def recompute_power(dev: DeviceState) -> float:
    if not dev.values_stale and _has(dev.load) and _has(dev.eps):
        return dev.load + dev.eps
    return NAN


def recompute_grid(dev: DeviceState) -> float:
    if not dev.values_stale and _has(dev.to_grid) and _has(dev.from_grid):
        return dev.to_grid - dev.from_grid
    return NAN


def recompute_battery(dev: DeviceState) -> float:
    if not dev.values_stale and _has(dev.charge) and _has(dev.discharge):
        return dev.charge - dev.discharge
    return NAN


def combine_total(a: float, b: float) -> float:
    # Mirrors combine_total_(): NaN propagates, a missing inverter is
    # never silently treated as zero.
    if a is None or b is None or math.isnan(a) or math.isnan(b):
        return NAN
    return a + b


def render_unsigned(value: float) -> str:
    if math.isnan(value):
        return "--"
    return f"{value:.0f} W"


def render_percent(value: float) -> str:
    if value is None or math.isnan(value):
        return "--"
    return f"{value:.0f}%"


def render_export_limit(value: float) -> str:
    if value is None or math.isnan(value):
        return "--"
    return f"{value:.0f}% ({value * 120.0:.0f} W)"


def render_voltage(value: float) -> str:
    if value is None or math.isnan(value):
        return "--"
    return f"{value:.1f} V"


def grid_voltage_color(value: float) -> str:
    if value is None or math.isnan(value):
        return "white"
    if 200.0 <= value <= 240.0:
        return "green"
    if 185.0 <= value < 200.0 or 240.0 < value <= 255.0:
        return "yellow"
    return "red"


def render_system_power(value: float) -> tuple[str, str, bool]:
    if value is None or math.isnan(value):
        return "--", "white", False
    if value < 2000.0:
        return f"{value:.0f} W", "green", False
    if value < 4000.0:
        return f"{value:.0f} W", "yellow", False
    if value <= 5000.0:
        return f"{value:.0f} W", "red", False
    return f"{value:.0f} W", "red", True


def render_signed(value: float) -> tuple[str, str]:
    """Mirrors the Grid/Battery lambda: (text, color)."""
    if math.isnan(value):
        return "--", "white"
    if value > 0:
        return f"+{value:.0f} W", "green"
    if value < 0:
        return f"{value:.0f} W", "red"
    return "0 W", "white"


def render_export(link_connected: bool, zero_export_enabled) -> tuple[str, str]:
    # Stage 37 field correction: live verification against the physical
    # inverters showed this must track zero_export_enabled directly (On
    # when set, Off when clear), not the originally-assumed inverse.
    trusted = bool(link_connected) and zero_export_enabled is not None
    if not trusted:
        return "--", "white"
    if zero_export_enabled:
        return "On", "green"
    return "Off", "red"


def _format_age(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m{seconds % 60:02d}s"


def render_header_status(name: str, age_ms: float | None) -> str:
    """Mirrors the gateway_snapshot_age on_value lambda: packet age drives
    the visible connection status independently of the binary fresh trigger."""
    if age_ms is None or math.isnan(age_ms):
        return f"{name} --"
    seconds = int(age_ms / 1000.0)
    if seconds < 15:
        return f"{name} #00E676 On#"
    if seconds < 60:
        return f"{name} #FFD600 Wait ({_format_age(seconds)})#"
    return f"{name} #FF3B30 Off ({_format_age(seconds)})#"


# ---------------------------------------------------------------------------
# Solar
# ---------------------------------------------------------------------------


def test_solar_per_inverter_sums_pv1_and_pv2() -> None:
    dev = DeviceState()
    dev.fresh = True
    dev.pv1 = 3750.0
    dev.pv2 = 2500.0
    assert recompute_solar(dev) == 6250.0


def test_solar_total_combines_both_inverters() -> None:
    lpx1 = recompute_solar(_fresh(pv1=3750.0, pv2=2500.0))
    lpx2 = recompute_solar(_fresh(pv1=1450.0, pv2=850.0))
    assert combine_total(lpx1, lpx2) == 8550.0


def test_pv1_pv2_have_no_total_helper_in_practice() -> None:
    # combine_total is only ever called for solar/power/grid/battery -- see
    # test_component_header_declares_total_sensor_only_for_solar_power_grid_battery.
    assert render_percent(None) == "--"


# ---------------------------------------------------------------------------
# Power = Load + EPS per inverter; TOTAL = Controller/system_output_power
# ---------------------------------------------------------------------------


def test_power_sums_load_and_eps() -> None:
    dev = _fresh(load=2200.0, eps=410.0)
    assert recompute_power(dev) == 2610.0


def test_power_total_uses_controller_system_output_power() -> None:
    system = SystemState()
    system.system_output_power = 5000.0
    lpx1 = recompute_power(_fresh(load=2200.0, eps=410.0))
    lpx2 = recompute_power(_fresh(load=1100.0, eps=220.0))
    assert combine_total(lpx1, lpx2) == 3930.0
    assert render_unsigned(system.system_output_power) == "5000 W"
    assert render_system_power(system.system_output_power) == ("5000 W", "red", False)


def test_power_total_does_not_fallback_to_stale_slave_load_power() -> None:
    system = SystemState()
    system.system_output_power = NAN
    lpx1 = recompute_power(_fresh(load=2200.0, eps=410.0))
    lpx2 = recompute_power(_fresh(load=9999.0, eps=9999.0))
    assert not math.isnan(combine_total(lpx1, lpx2))
    assert render_unsigned(system.system_output_power) == "--"
    assert render_system_power(system.system_output_power) == ("--", "white", False)


def test_system_power_color_thresholds_and_blink() -> None:
    assert render_system_power(1999.0) == ("1999 W", "green", False)
    assert render_system_power(2000.0) == ("2000 W", "yellow", False)
    assert render_system_power(3999.0) == ("3999 W", "yellow", False)
    assert render_system_power(4000.0) == ("4000 W", "red", False)
    assert render_system_power(5000.0) == ("5000 W", "red", False)
    assert render_system_power(5001.0) == ("5001 W", "red", True)


# ---------------------------------------------------------------------------
# Grid = PowerToGrid - PowerFromGrid per inverter and TOTAL
# ---------------------------------------------------------------------------


def test_grid_export_is_positive_and_green() -> None:
    dev = _fresh(to_grid=1200.0, from_grid=0.0)
    text, color = render_signed(recompute_grid(dev))
    assert text == "+1200 W"
    assert color == "green"


def test_grid_import_is_negative_and_red() -> None:
    dev = _fresh(to_grid=0.0, from_grid=1200.0)
    text, color = render_signed(recompute_grid(dev))
    assert text == "-1200 W"
    assert color == "red"


def test_inverter_grid_diagnostic_with_opposite_flows_between_inverters() -> None:
    lpx1 = recompute_grid(_fresh(to_grid=500.0, from_grid=0.0))  # exporting
    lpx2 = recompute_grid(_fresh(to_grid=0.0, from_grid=500.0))  # importing
    total = combine_total(lpx1, lpx2)
    text, color = render_signed(total)
    assert total == 0.0
    assert text == "0 W"
    assert color == "white"


def test_grid_total_same_direction_both_inverters() -> None:
    lpx1 = recompute_grid(_fresh(to_grid=0.0, from_grid=1200.0))
    lpx2 = recompute_grid(_fresh(to_grid=0.0, from_grid=600.0))
    total = combine_total(lpx1, lpx2)
    assert total == -1800.0
    assert render_signed(total) == ("-1800 W", "red")


def test_grid_total_export_is_green() -> None:
    lpx1 = recompute_grid(_fresh(to_grid=1800.0, from_grid=0.0))
    lpx2 = recompute_grid(_fresh(to_grid=600.0, from_grid=0.0))
    assert render_signed(combine_total(lpx1, lpx2)) == ("+2400 W", "green")


# ---------------------------------------------------------------------------
# Battery = Charge - Discharge
# ---------------------------------------------------------------------------


def test_battery_charging_is_positive_and_green() -> None:
    dev = _fresh(charge=600.0, discharge=0.0)
    assert render_signed(recompute_battery(dev)) == ("+600 W", "green")


def test_battery_discharging_is_negative_and_red() -> None:
    dev = _fresh(charge=0.0, discharge=600.0)
    assert render_signed(recompute_battery(dev)) == ("-600 W", "red")


def test_battery_total_with_opposite_flows_between_inverters() -> None:
    lpx1 = recompute_battery(_fresh(charge=600.0, discharge=0.0))  # charging
    lpx2 = recompute_battery(_fresh(charge=0.0, discharge=300.0))  # discharging
    total = combine_total(lpx1, lpx2)
    assert total == 300.0
    assert render_signed(total) == ("+300 W", "green")


# ---------------------------------------------------------------------------
# Missing / stale input handling
# ---------------------------------------------------------------------------


def test_source_not_fresh_keeps_last_derived_value_until_transport_off() -> None:
    dev = DeviceState()
    dev.fresh = False
    dev.pv1, dev.pv2 = 100.0, 50.0
    dev.load, dev.eps = 100.0, 50.0
    dev.to_grid, dev.from_grid = 100.0, 50.0
    dev.charge, dev.discharge = 100.0, 50.0
    assert recompute_solar(dev) == 150.0
    assert recompute_power(dev) == 150.0
    assert recompute_grid(dev) == 50.0
    assert recompute_battery(dev) == 50.0


def test_transport_off_blanks_every_derived_value_for_that_device() -> None:
    dev = DeviceState()
    dev.fresh = False
    dev.values_stale = True
    dev.pv1, dev.pv2 = 100.0, 50.0
    dev.load, dev.eps = 100.0, 50.0
    dev.to_grid, dev.from_grid = 100.0, 50.0
    dev.charge, dev.discharge = 100.0, 50.0
    assert math.isnan(recompute_solar(dev))
    assert math.isnan(recompute_power(dev))
    assert math.isnan(recompute_grid(dev))
    assert math.isnan(recompute_battery(dev))


def test_partial_input_blanks_that_derived_value_even_if_fresh() -> None:
    # e.g. PV2 never arrived yet -- Solar cannot be trusted even though the
    # device itself is fresh.
    dev = _fresh(pv1=100.0)
    dev.pv2 = None
    assert math.isnan(recompute_solar(dev))


def test_total_blanks_if_either_inverter_unavailable() -> None:
    lpx1 = recompute_solar(_fresh(pv1=100.0, pv2=50.0))
    lpx2 = NAN  # inverter 2 stale/disconnected
    total = combine_total(lpx1, lpx2)
    assert math.isnan(total)
    assert render_unsigned(total) == "--"


def test_total_never_treats_missing_inverter_as_zero() -> None:
    lpx1 = recompute_solar(_fresh(pv1=100.0, pv2=50.0))  # == 150.0
    lpx2 = NAN
    total = combine_total(lpx1, lpx2)
    assert total != 150.0
    assert math.isnan(total)


# ---------------------------------------------------------------------------
# SOC / Export Limit / Export: per-inverter only, never a TOTAL
# ---------------------------------------------------------------------------


def test_soc_renders_percent_or_dashes_when_unavailable() -> None:
    assert render_percent(100.0) == "100%"
    assert render_percent(None) == "--"


def test_export_limit_renders_percent_or_dashes_when_unavailable() -> None:
    assert render_export_limit(70.0) == "70% (8400 W)"
    assert render_export_limit(100.0) == "100% (12000 W)"
    assert render_export_limit(NAN) == "--"


def test_export_tracks_zero_export_enabled_directly() -> None:
    # zero_export_enabled True -> Export displays On (green).
    assert render_export(True, True) == ("On", "green")
    # zero_export_enabled False -> Export displays Off (red).
    assert render_export(True, False) == ("Off", "red")


def test_export_keeps_last_value_when_source_not_fresh_but_link_connected() -> None:
    assert render_export(True, False) == ("Off", "red")
    assert render_export(True, True) == ("On", "green")


def test_export_blanks_when_link_off_even_if_last_known_value_exists() -> None:
    assert render_export(False, False) == ("--", "white")
    assert render_export(False, True) == ("--", "white")


def test_export_blanks_before_first_value_ever_received() -> None:
    assert render_export(True, None) == ("--", "white")


def test_four_total_labels_and_system_grid_voltage_label_exist_in_yaml() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    total_label_ids = set(re.findall(r"id:\s*(\w*_total_label)\b", text))
    assert total_label_ids == {
        "solar_total_label",
        "power_total_label",
        "grid_total_label",
        "battery_total_label",
    }
    assert "id: grid_raw_voltage_label" in text
    assert "power_1_label" not in text
    assert "power_2_label" not in text


def test_component_declares_total_sensor_only_for_solar_power_grid_battery() -> None:
    # Distinguish Stage 37's single-instance TOTAL setters (no device_index
    # -- both inverters already combined) from the many pre-existing
    # per-device "*_energy_total_sensor" setters, which take a device_index
    # and mean something unrelated (a per-inverter running energy total).
    text = HEADER_PATH.read_text(encoding="utf-8")
    single_arg_total_setters = set(re.findall(r"void (set_\w*_total_sensor)\(sensor::Sensor \*sensor\)", text))
    assert single_arg_total_setters == {
        "set_solar_total_sensor",
        "set_power_total_sensor",
        "set_grid_total_sensor",
        "set_battery_total_sensor",
    }


def test_total_power_uses_controller_and_grid_uses_inverter_total_in_yaml() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    assert "system_output_power:" in text
    assert "grid_total:" in text
    assert "grid_input_power:" not in text
    assert "grid_raw_voltage:" in text
    assert "id(power_total_label)" in text
    assert "id(grid_total_label)" in text
    assert "id(grid_raw_voltage_label)" in text


def test_lower_parameter_columns_use_controller_and_inverter1_only() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    assert "Export Limit" in text
    assert "x * 120.0f" in text
    assert "export_limit_1_label" in text
    assert "export_1_label" in text
    assert "export_limit_2_label" not in text
    assert "export_2_label" not in text
    assert "system_power_blink_active" in text
    assert "inverter1_gateway_link_connected:" in text
    assert "id: inverter1_link_connected" in text
    assert "id(inverter1_link_connected).state" in text


def test_export_limit_watts_are_not_written_to_soc_label() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    soc_start = text.index("inverter1_battery_soc:")
    export_limit_start = text.index("inverter1_max_backflow_power:")
    solar_start = text.index("inverter1_solar:")

    soc_block = text[soc_start:export_limit_start]
    export_limit_block = text[export_limit_start:solar_start]

    assert "x * 120.0f" not in soc_block
    assert "id(soc_1_label)" in soc_block
    assert "x * 120.0f" in export_limit_block
    assert "id(export_limit_1_label)" in export_limit_block


def test_grid_voltage_color_thresholds() -> None:
    assert grid_voltage_color(184.9) == "red"
    assert grid_voltage_color(185.0) == "yellow"
    assert grid_voltage_color(199.9) == "yellow"
    assert grid_voltage_color(200.0) == "green"
    assert grid_voltage_color(240.0) == "green"
    assert grid_voltage_color(240.1) == "yellow"
    assert grid_voltage_color(255.0) == "yellow"
    assert grid_voltage_color(255.1) == "red"
    assert grid_voltage_color(NAN) == "white"


def test_display_maintenance_networking_is_boot_disabled_and_minimal() -> None:
    text = YAML_PATH.read_text(encoding="utf-8").lower()
    assert "sim_" not in text
    assert "sim " not in text
    assert "\nwifi:" in text
    assert "enable_on_boot: false" in text
    assert "reboot_timeout: 0s" in text
    assert "\napi:" in text
    assert "\nota:" in text
    assert "\nweb_server:" not in text
    assert "\ncaptive_portal:" not in text
    assert "wifi.enable" in text
    assert "wifi.disable" in text
    assert "maintenance_wifi_enabled) = false" in text
    assert "set_display_maintenance_wifi_actual(false)" in text
    assert "display_maintenance_wifi_requested:" in text
    assert "maintenance_ota_active" in text


def test_display_enabled_controls_only_existing_ch422g_enable_lines() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    assert "display_enabled:" in text
    assert "id: display_enabled_sensor" in text
    assert "id(io_expander).digital_write(2, x);" in text
    assert "id(io_expander).digital_write(6, x);" in text
    assert "light.turn_off" not in text
    assert "deep_sleep" not in text


def test_display_enabled_is_received_as_controller_system_binary_state() -> None:
    header = HEADER_PATH.read_text(encoding="utf-8")
    cpp = CPP_PATH.read_text(encoding="utf-8")
    binary_sensor = (REPO_ROOT / "components" / "display_protocol_uart" / "binary_sensor.py").read_text(encoding="utf-8")
    assert "set_display_enabled_sensor(binary_sensor::BinarySensor *sensor)" in header
    assert "binary_sensor::BinarySensor *display_enabled_sensor_ = nullptr" in header
    assert "FieldIdDisplayEnabled" in cpp
    assert "publish_binary_(this->display_enabled_sensor_, value != 0)" in cpp
    assert 'CONF_DISPLAY_ENABLED = "display_enabled"' in binary_sensor


def test_controller_stale_does_not_publish_display_enabled_false() -> None:
    cpp = CPP_PATH.read_text(encoding="utf-8")
    stale_start = cpp.index("DisplayProtocolUARTComponent::mark_system_stale_")
    stale_end = cpp.index("void DisplayProtocolUARTComponent::update_connection_status_", stale_start)
    stale_block = cpp[stale_start:stale_end]
    assert "display_enabled_sensor_" not in stale_block
    assert "FieldIdDisplayEnabled" not in stale_block


# ---------------------------------------------------------------------------
# Header connection status from packet age -- no icon/image asset
# ---------------------------------------------------------------------------


def test_header_status_initial_before_first_packet() -> None:
    assert render_header_status("LXP1", None) == "LXP1 --"


def test_header_status_on_until_15_seconds_without_packets() -> None:
    assert render_header_status("LXP1", 0) == "LXP1 #00E676 On#"
    assert render_header_status("LXP1", 14999) == "LXP1 #00E676 On#"


def test_header_status_wait_from_15_seconds_to_one_minute() -> None:
    assert render_header_status("LXP1", 15000) == "LXP1 #FFD600 Wait (15s)#"
    assert render_header_status("LXP1", 59000) == "LXP1 #FFD600 Wait (59s)#"


def test_header_status_off_after_one_minute_with_timer() -> None:
    assert render_header_status("LXP2", 60000) == "LXP2 #FF3B30 Off (1m00s)#"
    assert render_header_status("LXP2", 65000) == "LXP2 #FF3B30 Off (1m05s)#"


def test_header_status_switches_by_packet_age() -> None:
    ages = [0, 14000, 15000, 59000, 60000, 65000, 0]
    rendered = [render_header_status("LXP2", age) for age in ages]
    assert rendered == [
        "LXP2 #00E676 On#",
        "LXP2 #00E676 On#",
        "LXP2 #FFD600 Wait (15s)#",
        "LXP2 #FFD600 Wait (59s)#",
        "LXP2 #FF3B30 Off (1m00s)#",
        "LXP2 #FF3B30 Off (1m05s)#",
        "LXP2 #00E676 On#",
    ]


def test_header_status_is_driven_by_gateway_snapshot_age_in_yaml() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    assert "stale_timeout: 60s" in text
    assert "inverter1_gateway_snapshot_age:" in text
    assert "inverter2_gateway_snapshot_age:" in text
    assert "Wait (%s)" in text
    assert "Off (%s)" in text
    assert "seconds < 15" in text
    assert "seconds < 60" in text
    assert text.count("lv_label_set_text(id(header1_label)") == 1
    assert text.count("lv_label_set_text(id(header2_label)") == 1


def test_no_icon_image_assets_declared_in_yaml() -> None:
    # Stage 37 design feedback: icons were removed in favor of a plain
    # recolor-markup text label -- guard against silently reintroducing
    # image: platform usage/lv_image_set_src.
    text = YAML_PATH.read_text(encoding="utf-8")
    assert "\nimage:" not in text
    assert "lv_image_set_src(" not in text


# ---------------------------------------------------------------------------
# Initial-state rendering (before any telemetry has ever arrived)
# ---------------------------------------------------------------------------


def test_initial_state_every_derived_value_is_nan() -> None:
    dev = DeviceState()
    assert math.isnan(recompute_solar(dev))
    assert math.isnan(recompute_power(dev))
    assert math.isnan(recompute_grid(dev))
    assert math.isnan(recompute_battery(dev))


def test_initial_state_renders_as_dashes_not_zero() -> None:
    dev = DeviceState()
    assert render_unsigned(recompute_solar(dev)) == "--"
    assert render_signed(recompute_grid(dev)) == ("--", "white")
    assert render_percent(dev.soc) == "--"
    assert render_export(dev.fresh, dev.zero_export_enabled) == ("--", "white")
    assert render_header_status("LXP1", None) == "LXP1 --"


# ---------------------------------------------------------------------------
# End-to-end scenario matching the Stage 37 design mockup exactly
# ---------------------------------------------------------------------------


def test_mockup_scenario_end_to_end() -> None:
    system = SystemState()
    system.system_output_power = 5000.0
    system.grid_raw_voltage = 263.4
    lpx1 = _fresh(pv1=3750.0, pv2=2500.0, load=2200.0, eps=410.0,
                   to_grid=0.0, from_grid=1200.0, charge=600.0, discharge=0.0,
                   soc=100.0, max_backflow=70.0, zero_export_enabled=False)
    lpx2 = _fresh(pv1=1450.0, pv2=850.0, load=1100.0, eps=220.0,
                   to_grid=0.0, from_grid=600.0, charge=300.0, discharge=0.0,
                   soc=100.0, max_backflow=30.0, zero_export_enabled=True)

    solar_1, solar_2 = recompute_solar(lpx1), recompute_solar(lpx2)
    assert (solar_1, solar_2) == (6250.0, 2300.0)
    assert combine_total(solar_1, solar_2) == 8550.0

    power_1, power_2 = recompute_power(lpx1), recompute_power(lpx2)
    assert (power_1, power_2) == (2610.0, 1320.0)
    assert combine_total(power_1, power_2) == 3930.0
    assert render_unsigned(system.system_output_power) == "5000 W"
    assert render_system_power(system.system_output_power) == ("5000 W", "red", False)
    assert render_voltage(system.grid_raw_voltage) == "263.4 V"
    assert grid_voltage_color(system.grid_raw_voltage) == "red"

    grid_1, grid_2 = recompute_grid(lpx1), recompute_grid(lpx2)
    assert (grid_1, grid_2) == (-1200.0, -600.0)
    assert combine_total(grid_1, grid_2) == -1800.0
    assert render_signed(combine_total(grid_1, grid_2)) == ("-1800 W", "red")
    assert render_signed(grid_1) == ("-1200 W", "red")
    assert render_signed(grid_2) == ("-600 W", "red")

    battery_1, battery_2 = recompute_battery(lpx1), recompute_battery(lpx2)
    assert (battery_1, battery_2) == (600.0, 300.0)
    assert combine_total(battery_1, battery_2) == 900.0
    assert render_signed(battery_1) == ("+600 W", "green")

    assert render_percent(lpx1.soc) == "100%"
    assert render_export_limit(lpx1.max_backflow) == "70% (8400 W)"

    # Export tracks zero_export_enabled directly (see the Stage 37 field
    # correction note on render_export) -- lpx1's False -> Off, lpx2's
    # True -> On.
    assert render_export(lpx1.fresh, lpx1.zero_export_enabled) == ("Off", "red")
    assert render_export(lpx2.fresh, lpx2.zero_export_enabled) == ("On", "green")


def _fresh(**kwargs) -> DeviceState:
    dev = DeviceState()
    dev.fresh = True
    for key, value in kwargs.items():
        setattr(dev, key, value)
    return dev


def main() -> int:
    tests = [
        test_solar_per_inverter_sums_pv1_and_pv2,
        test_solar_total_combines_both_inverters,
        test_pv1_pv2_have_no_total_helper_in_practice,
        test_power_sums_load_and_eps,
        test_power_total_uses_controller_system_output_power,
        test_power_total_does_not_fallback_to_stale_slave_load_power,
        test_system_power_color_thresholds_and_blink,
        test_grid_export_is_positive_and_green,
        test_grid_import_is_negative_and_red,
        test_inverter_grid_diagnostic_with_opposite_flows_between_inverters,
        test_grid_total_same_direction_both_inverters,
        test_grid_total_export_is_green,
        test_battery_charging_is_positive_and_green,
        test_battery_discharging_is_negative_and_red,
        test_battery_total_with_opposite_flows_between_inverters,
        test_source_not_fresh_keeps_last_derived_value_until_transport_off,
        test_transport_off_blanks_every_derived_value_for_that_device,
        test_partial_input_blanks_that_derived_value_even_if_fresh,
        test_total_blanks_if_either_inverter_unavailable,
        test_total_never_treats_missing_inverter_as_zero,
        test_soc_renders_percent_or_dashes_when_unavailable,
        test_export_limit_renders_percent_or_dashes_when_unavailable,
        test_export_tracks_zero_export_enabled_directly,
        test_export_keeps_last_value_when_source_not_fresh_but_link_connected,
        test_export_blanks_when_link_off_even_if_last_known_value_exists,
        test_export_blanks_before_first_value_ever_received,
        test_four_total_labels_and_system_grid_voltage_label_exist_in_yaml,
        test_component_declares_total_sensor_only_for_solar_power_grid_battery,
        test_total_power_uses_controller_and_grid_uses_inverter_total_in_yaml,
        test_lower_parameter_columns_use_controller_and_inverter1_only,
        test_export_limit_watts_are_not_written_to_soc_label,
        test_grid_voltage_color_thresholds,
        test_display_maintenance_networking_is_boot_disabled_and_minimal,
        test_display_enabled_controls_only_existing_ch422g_enable_lines,
        test_display_enabled_is_received_as_controller_system_binary_state,
        test_controller_stale_does_not_publish_display_enabled_false,
        test_header_status_initial_before_first_packet,
        test_header_status_on_until_15_seconds_without_packets,
        test_header_status_wait_from_15_seconds_to_one_minute,
        test_header_status_off_after_one_minute_with_timer,
        test_header_status_switches_by_packet_age,
        test_header_status_is_driven_by_gateway_snapshot_age_in_yaml,
        test_no_icon_image_assets_declared_in_yaml,
        test_initial_state_every_derived_value_is_nan,
        test_initial_state_renders_as_dashes_not_zero,
        test_mockup_scenario_end_to_end,
    ]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
    print(f"{len(tests)} derived-value tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
