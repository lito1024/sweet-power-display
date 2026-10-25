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
HMI_PATH = REPO_ROOT / "display_hmi.h"


class DeviceState:
    def __init__(self) -> None:
        # Stage 54: `fresh` is the single, already-debounced gate for every
        # derived calculation below -- data_fresh_ in the real component
        # (see DisplayProtocolUARTComponent::recompute_derived_). There is
        # no separate "values_stale" flag any more: before Stage 54, a
        # device could report itself not-fresh indefinitely while transport
        # packets kept arriving, and derived values were only blanked by a
        # SEPARATE, transport-only timeout -- exactly the bug Stage 54
        # fixes. Now not-fresh (for any reason: transport-dead or the
        # source itself stale) always means "do not trust the last values".
        self.fresh = False
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
    if dev.fresh and _has(dev.pv1) and _has(dev.pv2):
        return dev.pv1 + dev.pv2
    return NAN


def recompute_power(dev: DeviceState) -> float:
    if dev.fresh and _has(dev.load) and _has(dev.eps):
        return dev.load + dev.eps
    return NAN


def recompute_grid(dev: DeviceState) -> float:
    if dev.fresh and _has(dev.to_grid) and _has(dev.from_grid):
        return dev.to_grid - dev.from_grid
    return NAN


def recompute_battery(dev: DeviceState) -> float:
    if dev.fresh and _has(dev.charge) and _has(dev.discharge):
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




def render_voltage(value: float) -> str:
    if value is None or math.isnan(value):
        return "--"
    return f"{value:.1f} V"


def grid_voltage_color(value: float) -> str:
    # Stage 56b owner thresholds: 190-230 green; 160-190 / 230-250 yellow;
    # below 160 or above 250 red.
    if value is None or math.isnan(value):
        return "white"
    if 190.0 <= value <= 230.0:
        return "green"
    if 160.0 <= value < 190.0 or 230.0 < value <= 250.0:
        return "yellow"
    return "red"


def render_system_power(value: float) -> tuple[str, str, bool]:
    if value is None or math.isnan(value):
        return "--", "white", False
    # Stage 56b owner thresholds: < 3 kW white, 3-4.5 kW yellow, > 4.5 kW
    # red; the pre-existing > 5 kW blink is kept.
    if value < 3000.0:
        return f"{value:.0f} W", "white", False
    if value <= 4500.0:
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


DEVICE_STATUS_WAITING = 0
DEVICE_STATUS_FRESH = 1
DEVICE_STATUS_STALE = 2
DEVICE_STATUS_OFFLINE = 3


def render_header_status(name: str, code: int | None, offline_age_ms: float | None = None) -> str:
    """Stage 54: mirrors the inverterN_device_status on_value lambda --
    driven by DisplayProtocolUARTComponent::update_device_status_'s single
    Waiting/Fresh/Stale/Offline code, not raw packet age. Age is only shown
    for Offline (offline_age_ms is inverter1/2_packet_age_ms's own state,
    read separately inside that same lambda). Replaces the pre-Stage-54
    packet-age-only thresholds, which showed "On" for up to 15s from ANY
    packet -- including one carrying only a frozen/stale-but-successfully-
    cached reading -- regardless of whether the Gateway's own source was
    actually fresh."""
    if code is None or code == DEVICE_STATUS_WAITING:
        return f"{name} #FFD600 Wait#"
    if code == DEVICE_STATUS_FRESH:
        return f"{name} #00E676 On#"
    if code == DEVICE_STATUS_STALE:
        return f"{name} #FFD600 Stale#"
    seconds = int((offline_age_ms or 0) / 1000.0)
    return f"{name} #FF3B30 Offline ({_format_age(seconds)})#"


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
    assert render_system_power(2999.0) == ("2999 W", "white", False)
    assert render_system_power(3000.0) == ("3000 W", "yellow", False)
    assert render_system_power(4500.0) == ("4500 W", "yellow", False)
    assert render_system_power(4501.0) == ("4501 W", "red", False)
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


def test_source_not_fresh_blanks_every_derived_value_immediately() -> None:
    # Stage 54: this is the corrected behavior. Before Stage 54, a device
    # reporting itself not-fresh while transport packets kept arriving left
    # every derived value (Solar/Power/Grid/Battery) showing its last,
    # possibly long-stale, number -- exactly the 2026-09-18 Gateway-2
    # incident this stage fixes. Not-fresh (regardless of whether it is
    # caused by a dead transport link or by the Gateway's own source
    # reporting itself stale) must always blank every derived value for
    # that device, never freeze it.
    dev = DeviceState()
    dev.fresh = False
    dev.pv1, dev.pv2 = 100.0, 50.0
    dev.load, dev.eps = 100.0, 50.0
    dev.to_grid, dev.from_grid = 100.0, 50.0
    dev.charge, dev.discharge = 100.0, 50.0
    assert math.isnan(recompute_solar(dev))
    assert math.isnan(recompute_power(dev))
    assert math.isnan(recompute_grid(dev))
    assert math.isnan(recompute_battery(dev))


def test_transport_off_blanks_every_derived_value_for_that_device() -> None:
    dev = DeviceState()
    dev.fresh = False
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
    # Display 3A: kW format in the GRID tile corner ("LIMIT 50% | 6kW").
    assert render_export_limit(70.0) == "LIMIT 70% | 8.4kW"
    assert render_export_limit(100.0) == "LIMIT 100% | 12kW"
    assert render_export_limit(NAN) == "LIMIT --"


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


def render_grid_power(x: float) -> tuple[str, str]:
    # Python mirror of the Stage 56 grid_input_power lambda (Eastron sign:
    # + import / - export).
    if math.isnan(x):
        return ("--", "white")
    if x > 0:
        return (f"{x:.0f} W", "yellow")
    if x < 0:
        return (f"{x:.0f} W", "green")
    return ("0 W", "white")


def test_grid_power_rendering_follows_eastron_sign() -> None:
    assert render_grid_power(1852.0) == ("1852 W", "yellow")  # import
    assert render_grid_power(-640.0) == ("-640 W", "green")  # export
    assert render_grid_power(0.0) == ("0 W", "white")
    assert render_grid_power(NAN) == ("--", "white")


def render_grid_current(x: float) -> tuple[str, str]:
    # Python mirror of the Stage 56b grid_input_current lambda.
    if math.isnan(x):
        return ("--", "white")
    color = "green" if x < 20.0 else ("yellow" if x < 25.0 else "red")
    return (f"{x:.1f} A", color)


def test_grid_current_rendering_thresholds() -> None:
    assert render_grid_current(19.9) == ("19.9 A", "green")
    assert render_grid_current(20.0) == ("20.0 A", "yellow")
    assert render_grid_current(24.9) == ("24.9 A", "yellow")
    assert render_grid_current(25.0) == ("25.0 A", "red")
    assert render_grid_current(NAN) == ("--", "white")
    hmi = HMI_PATH.read_text(encoding="utf-8")
    block = hmi[hmi.index("inline uint32_t grid_current_color") : hmi.index("// Export limit:")]
    assert "a < 20.0f" in block and "a < 25.0f" in block


def render_export_limit(x: float) -> str:
    # Python mirror of the Stage 56 Export Limit lambda.
    if x is None or math.isnan(x):
        return "LIMIT --"
    kw = x * 120.0 / 1000.0
    if abs(kw - round(kw)) < 0.05:
        return f"LIMIT {x:.0f}% | {kw:.0f}kW"
    return f"LIMIT {x:.0f}% | {kw:.1f}kW"


def test_export_limit_is_rendered_in_kw() -> None:
    assert render_export_limit(50.0) == "LIMIT 50% | 6kW"
    assert render_export_limit(100.0) == "LIMIT 100% | 12kW"
    assert render_export_limit(45.0) == "LIMIT 45% | 5.4kW"
    assert render_export_limit(0.0) == "LIMIT 0% | 0kW"
    assert render_export_limit(NAN) == "LIMIT --"
    hmi = HMI_PATH.read_text(encoding="utf-8")
    assert '"LIMIT %.0f%% | %.0fkW"' in hmi and '"LIMIT %.0f%% | %.1fkW"' in hmi
    assert "EXPORT_LIMIT_W_PER_PERCENT = 120.0f" in hmi


def test_header_icons_are_packed_tightly() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    spc = text[text.index("id: spc_icon_img") : text.index("id: spc_icon_img") + 200]
    ha = text[text.index("id: ha_icon_img") : text.index("id: ha_icon_img") + 200]
    assert "x: -42" in spc
    assert "x: -70" in ha


def test_offline_header_switches_to_small_font_only_when_offline() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    for n in ("1", "2"):
        assert (f"lv_obj_set_style_text_font(id(header{n}_label),\n"
                f"                    code == 3 ? &lv_font_montserrat_14 : &lv_font_montserrat_20, 0);") in text


def test_grid_voltage_color_thresholds() -> None:
    assert grid_voltage_color(159.9) == "red"
    assert grid_voltage_color(160.0) == "yellow"
    assert grid_voltage_color(189.9) == "yellow"
    assert grid_voltage_color(190.0) == "green"
    assert grid_voltage_color(230.0) == "green"
    assert grid_voltage_color(230.1) == "yellow"
    assert grid_voltage_color(250.0) == "yellow"
    assert grid_voltage_color(250.1) == "red"
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
    assert render_header_status("LXP1", None) == "LXP1 #FFD600 Wait#"
    assert render_header_status("LXP1", DEVICE_STATUS_WAITING) == "LXP1 #FFD600 Wait#"


def test_header_status_fresh_is_on_regardless_of_packet_age() -> None:
    # Stage 54: unlike the pre-Stage-54 age-only scheme, "On" now depends
    # solely on the Gateway's own source-fresh signal, not how recently a
    # packet arrived (a fresh device sends roughly every second anyway).
    assert render_header_status("LXP1", DEVICE_STATUS_FRESH) == "LXP1 #00E676 On#"


def test_header_status_stale_shown_while_packets_still_arrive() -> None:
    # Stage 54: this is the exact 2026-09-18 incident state -- packets keep
    # arriving (so the old age-only scheme said "On") but the Gateway's own
    # source-freshness has expired. Must render as a distinct warning
    # state, not "On" and not conflated with a fully dead transport link.
    assert render_header_status("LXP1", DEVICE_STATUS_STALE) == "LXP1 #FFD600 Stale#"


def test_header_status_offline_shows_age_since_last_packet() -> None:
    assert render_header_status("LXP2", DEVICE_STATUS_OFFLINE, offline_age_ms=60000) == "LXP2 #FF3B30 Offline (1m00s)#"
    assert render_header_status("LXP2", DEVICE_STATUS_OFFLINE, offline_age_ms=65000) == "LXP2 #FF3B30 Offline (1m05s)#"


def test_header_status_switches_by_code_not_age() -> None:
    transitions = [
        (DEVICE_STATUS_WAITING, None),
        (DEVICE_STATUS_FRESH, None),
        (DEVICE_STATUS_STALE, None),
        (DEVICE_STATUS_OFFLINE, 60000),
        (DEVICE_STATUS_FRESH, None),  # automatic recovery back to On
    ]
    rendered = [render_header_status("LXP2", code, offline_age_ms=age) for code, age in transitions]
    assert rendered == [
        "LXP2 #FFD600 Wait#",
        "LXP2 #00E676 On#",
        "LXP2 #FFD600 Stale#",
        "LXP2 #FF3B30 Offline (1m00s)#",
        "LXP2 #00E676 On#",
    ]


def test_header_status_is_driven_by_device_status_sensor_in_yaml() -> None:
    text = YAML_PATH.read_text(encoding="utf-8")
    assert "stale_timeout: 60s" in text
    assert "inverter1_device_status:" in text
    assert "inverter2_device_status:" in text
    assert "inverter1_packet_age_ms" in text
    assert "inverter2_packet_age_ms" in text
    assert "Stale#" in text
    assert "Offline (%s)#" in text
    assert text.count("lv_label_set_text(id(header1_label)") == 1
    assert text.count("lv_label_set_text(id(header2_label)") == 1


def test_lxp_headers_still_use_recolor_text_not_icon_images() -> None:
    # Stage 37 design feedback: the LXP1/LXP2 inverter status headers were
    # switched from image-based icons to a plain recolor-markup text label
    # -- guard against silently reintroducing the unused pictures/LPX_*.png
    # icon assets for THAT specific feature. Stage 44H (icon revision)
    # legitimately introduced `image:`/lv_img_set_src for an unrelated
    # feature (the Home Assistant status icon, an official-logo bitmap), so
    # this test no longer bans image: usage outright -- it checks only that
    # the LXP header regression hasn't come back.
    text = YAML_PATH.read_text(encoding="utf-8")
    assert 'id: header1_label, text: "LXP1 --"' in text
    assert 'id: header2_label, text: "LXP2 --"' in text
    assert "recolor: true" in text
    assert "LPX_1_ON.png" not in text
    assert "LPX_1_OFF.png" not in text
    assert "LPX_2_ON.png" not in text
    assert "LPX_2_OFF.png" not in text


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
    assert render_header_status("LXP1", None) == "LXP1 #FFD600 Wait#"


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
    assert render_export_limit(lpx1.max_backflow) == "LIMIT 70% | 8.4kW"  # Display 3A

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


# ---------------------------------------------------------------------------
# Display 3A (owner-approved 2026-10-25) layout and wiring
# ---------------------------------------------------------------------------


def _yaml() -> str:
    return YAML_PATH.read_text(encoding="utf-8")


def test_3a_layout_order_and_height_budget() -> None:
    text = _yaml()
    order = [text.index(x) for x in ('text: "SWEET POWER"', "id: kpi_row", "id: inverter_table",
                                      "id: layout_spacer", "id: source_strip")]
    assert order == sorted(order)
    kpi = text[text.index("id: kpi_row"): text.index("id: inverter_table")]
    tiles = [kpi.index(f"id: {t}_tile") for t in ("solar", "battery", "load", "grid")]
    assert tiles == sorted(tiles)
    strip = text[text.index("id: source_strip"):]
    tiles = [strip.index(f"id: {t}_tile") for t in ("stabilizer", "zegor", "ks")]
    assert tiles == sorted(tiles)
    table = text[text.index("id: inverter_table"): text.index("id: layout_spacer")]
    cols = [table.index(f'text: "{c}"') for c in ("Solar", "PV1", "PV2", "Battery", "SOC")]
    assert cols == sorted(cols)
    for n in ("1", "2"):
        row = table[table.index(f"id: inverter{n}_row"):]
        cells = [row.index(f"id: {c}") for c in (f"header{n}_label", f"solar_{n}_label", f"pv1_{n}_label",
                                                  f"pv2_{n}_label", f"battery_{n}_label", f"soc_{n}_label")]
        assert cells == sorted(cells), n
    # 480 px panel, 4 px root padding: fixed parts must leave room for the spacer.
    heights = {"title": 34, "kpi_row": 118, "inverter_table": 106, "source_strip": 132}
    for key in ("kpi_row", "inverter_table", "source_strip"):
        block = text[text.index(f"id: {key}"): text.index(f"id: {key}") + 120]
        assert f"height: {heights[key]}" in block, key
    assert sum(heights.values()) <= 480 - 8
    # Stage 56 widgets are gone (no duplicate presentation of the same values).
    for removed in ("top_section", "reserved_area", "power_total_label", "grid_power_label",
                    "export_limit_1_label", "export_1_label", "system_voltage_label"):
        assert f"id: {removed}" not in text and f"id({removed})" not in text, removed


def test_3a_export_limit_lives_in_the_grid_tile() -> None:
    text = _yaml()
    grid = text[text.index("id: grid_tile"): text.index("id: inverter_table")]
    assert "id: export_limit_label" in grid and "align: RIGHT_MID" in grid
    assert "id: export_use_bar" in grid
    assert "inverter1_max_backflow_power:\n      name: \"Inverter 1 Max Backflow Power\"\n      id: inverter1_max_backflow_power\n" in text
    refresh = text[text.index("display_hmi::refresh_grid("):]
    refresh = refresh[: refresh.index(");") + 2]
    for arg in ("id(export_limit_label)", "id(export_use_bar)", "st(id(grid_input_power_sensor))",
                "st(id(grid_raw_voltage_sensor))", "st(id(grid_input_current_sensor))",
                "st(id(inverter1_max_backflow_power))", "export_state"):
        assert arg in refresh, arg
    hmi = HMI_PATH.read_text(encoding="utf-8")
    assert "100.0f * export_w / (limit_percent * EXPORT_LIMIT_W_PER_PERCENT)" in hmi


def test_3a_sources_are_controller_pzem_eastron_and_lxp1_export() -> None:
    text = _yaml()
    lam = text[text.index("display_hmi::refresh_solar("): text.index("  - interval: 1s\n    then:\n      - if:")]
    assert "st(id(system_output_power_sensor))" in lam and "st(id(system_output_voltage_sensor))" in lam
    assert "st(id(solar_total_sensor))" in lam and "st(id(battery_total_sensor))" in lam
    # Export On/Off only while LXP1's link is up (Stage 37 rule, unchanged).
    assert "id(inverter1_link_connected).state" in lam and "id(inverter1_zero_export_enabled).state ? 1 : 0" in lam
    assert "inverter2_zero_export_enabled).state" not in lam
    # Load blink (> 5 kW) still drives the 500 ms blink interval, now on the LOAD tile.
    assert "id(system_power_blink_active) = blink;" in lam
    assert "id(load_value_label),\n            lv_color_hex(id(system_power_blink_visible) ? 0xFF3B30 : 0x202020)" in text


def test_3a_owner_thresholds_kept_in_display_hmi() -> None:
    hmi = HMI_PATH.read_text(encoding="utf-8")
    load = hmi[hmi.index("inline uint32_t load_color"): hmi.index("// Eastron grid power")]
    assert "w < 3000.0f" in load and "w <= 4500.0f" in load and "w > 5000.0f" in load
    volt = hmi[hmi.index("inline uint32_t grid_voltage_color"): hmi.index("// Grid current")]
    assert "v >= 190.0f && v <= 230.0f" in volt and "v >= 160.0f && v < 190.0f" in volt and "v <= 250.0f" in volt
    gp = hmi[hmi.index("inline uint32_t grid_power_color"): hmi.index("// Grid voltage")]
    assert "w > 0.0f ? YELLOW : GREEN" in gp


def test_3a_generators_stabilizer_and_oil() -> None:
    text = _yaml()
    for g in ("zegor", "ks"):
        call = text[text.index(f"display_hmi::refresh_generator(id({g}_tile)"):]
        call = call[: call.index(");") + 2]
        for arg in (f"id({g}_status_label)", f"id({g}_value_label)", f"id({g}_oil_label)", f"id({g}_oil_bar)",
                    f"st(id({g}_generator_power_sensor))", f"st(id({g}_oil_hours_sensor))",
                    f"st(id({g}_oil_interval_sensor))", f"id({g}_run_start_ms)"):
            assert arg in call, (g, arg)
        assert f"{g}_generator_power: {{id: {g}_generator_power_sensor, internal: true}}" in text
    stab = text[text.index("display_hmi::refresh_stabilizer("):]
    assert "st(id(quant9_output_voltage_sensor)), st(id(elex_output_voltage_sensor))" in stab[:300]
    hmi = HMI_PATH.read_text(encoding="utf-8")
    assert "STABILIZER_PRESENT_V = 150.0f" in hmi and "NOT the Stage 48L validity threshold" in hmi
    oil = hmi[hmi.index("inline uint32_t oil_color"): hmi.index("// ---- tiles ----")]
    assert "used >= 0.95f) return RED" in oil and "used >= 0.80f) return AMBER" in oil
    assert "OIL CHANGE" in hmi


def test_3a_new_controller_fields_decoded_and_blanked() -> None:
    cpp = CPP_PATH.read_text(encoding="utf-8")
    pub = cpp[cpp.index("void DisplayProtocolUARTComponent::publish_system_telemetry_field_"):]
    pub = pub[: pub.index("default:")]
    stale = cpp[cpp.index("void DisplayProtocolUARTComponent::mark_system_stale_"):]
    stale = stale[: stale.index("\n}\n")]
    for name, sensor, scale in (("KsGeneratorPower", "ks_generator_power", "1.0f"),
                                ("ZegorGeneratorPower", "zegor_generator_power", "1.0f"),
                                ("Quant9OutputVoltage", "quant9_output_voltage", "10.0f"),
                                ("ElexOutputVoltage", "elex_output_voltage", "10.0f"),
                                ("KsOilHours", "ks_oil_hours", "10.0f"), ("KsOilInterval", "ks_oil_interval", "10.0f"),
                                ("ZegorOilHours", "zegor_oil_hours", "10.0f"),
                                ("ZegorOilInterval", "zegor_oil_interval", "10.0f")):
        assert (f"case ESPTelemetry::FieldId{name}:\n      this->publish_float_(this->{sensor}_sensor_, "
                f"scaled_or_nan_(value, {scale}));") in pub, name
        assert f"this->publish_float_(this->{sensor}_sensor_, NAN);" in stale, name


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
        test_source_not_fresh_blanks_every_derived_value_immediately,
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
        test_component_declares_total_sensor_only_for_solar_power_grid_battery,
        test_grid_power_rendering_follows_eastron_sign,
        test_export_limit_is_rendered_in_kw,
        test_3a_layout_order_and_height_budget,
        test_3a_export_limit_lives_in_the_grid_tile,
        test_3a_sources_are_controller_pzem_eastron_and_lxp1_export,
        test_3a_owner_thresholds_kept_in_display_hmi,
        test_3a_generators_stabilizer_and_oil,
        test_3a_new_controller_fields_decoded_and_blanked,
        test_grid_current_rendering_thresholds,
        test_header_icons_are_packed_tightly,
        test_offline_header_switches_to_small_font_only_when_offline,
        test_grid_voltage_color_thresholds,
        test_display_maintenance_networking_is_boot_disabled_and_minimal,
        test_display_enabled_controls_only_existing_ch422g_enable_lines,
        test_display_enabled_is_received_as_controller_system_binary_state,
        test_controller_stale_does_not_publish_display_enabled_false,
        test_header_status_initial_before_first_packet,
        test_header_status_fresh_is_on_regardless_of_packet_age,
        test_header_status_stale_shown_while_packets_still_arrive,
        test_header_status_offline_shows_age_since_last_packet,
        test_header_status_switches_by_code_not_age,
        test_header_status_is_driven_by_device_status_sensor_in_yaml,
        test_lxp_headers_still_use_recolor_text_not_icon_images,
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
