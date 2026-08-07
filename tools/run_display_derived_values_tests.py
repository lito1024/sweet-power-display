#!/usr/bin/env python3
"""Host-side mirror of Stage 37's derived-value math and stale/unavailable
handling.

Mirrors DisplayProtocolUARTComponent::recompute_derived_/combine_total_
(display_protocol_uart.cpp) and the LVGL rendering lambdas in
sweet-power-display-offline-uart.yaml: Solar = PV1+PV2, Power =
Load+EPS, Grid = PowerToGrid-PowerFromGrid, Battery =
BatteryCharge-BatteryDischarge, TOTAL = both inverters combined or NaN if
either is unavailable. This is a model for fast host testing, not a
binding to the real firmware -- keep it in sync with the C++/YAML by hand
when that logic changes.
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


def render_signed(value: float) -> tuple[str, str]:
    """Mirrors the Grid/Battery lambda: (text, color)."""
    if math.isnan(value):
        return "--", "white"
    if value > 0:
        return f"+{value:.0f} W", "green"
    if value < 0:
        return f"{value:.0f} W", "red"
    return "0 W", "white"


def render_export(fresh: bool, zero_export_enabled) -> tuple[str, str]:
    # Stage 37 field correction: live verification against the physical
    # inverters showed this must track zero_export_enabled directly (On
    # when set, Off when clear), not the originally-assumed inverse.
    trusted = bool(fresh) and zero_export_enabled is not None
    if not trusted:
        return "--", "white"
    if zero_export_enabled:
        return "On", "green"
    return "Off", "red"


def render_header_status(name: str, fresh: bool) -> str:
    """Mirrors the inverter{1,2}_fresh on_state lambda: name (default
    label color) + a recolor-markup status word, e.g. "LXP1 #00E676 On#".
    No icon/image asset is used -- see Stage 37 design feedback."""
    if fresh:
        return f"{name} #00E676 On#"
    return f"{name} #FF3B30 Off#"


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
# Power = Load + EPS
# ---------------------------------------------------------------------------


def test_power_sums_load_and_eps() -> None:
    dev = _fresh(load=2200.0, eps=410.0)
    assert recompute_power(dev) == 2610.0


def test_power_total_combines_both_inverters() -> None:
    lpx1 = recompute_power(_fresh(load=2200.0, eps=410.0))
    lpx2 = recompute_power(_fresh(load=1100.0, eps=220.0))
    assert combine_total(lpx1, lpx2) == 3930.0


# ---------------------------------------------------------------------------
# Grid = PowerToGrid - PowerFromGrid
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


def test_grid_total_with_opposite_flows_between_inverters() -> None:
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


def test_not_fresh_blanks_every_derived_value_for_that_device() -> None:
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
    assert render_percent(70.0) == "70%"
    assert render_percent(NAN) == "--"


def test_export_tracks_zero_export_enabled_directly() -> None:
    # zero_export_enabled True -> Export displays On (green).
    assert render_export(True, True) == ("On", "green")
    # zero_export_enabled False -> Export displays Off (red).
    assert render_export(True, False) == ("Off", "red")


def test_export_blanks_when_device_not_fresh_even_if_last_known_value_exists() -> None:
    assert render_export(False, False) == ("--", "white")
    assert render_export(False, True) == ("--", "white")


def test_export_blanks_before_first_value_ever_received() -> None:
    assert render_export(True, None) == ("--", "white")


def test_only_four_total_value_labels_exist_in_yaml() -> None:
    # SOC / Export Limit / Export must never grow a TOTAL cell -- guard
    # against a future edit accidentally adding one.
    text = YAML_PATH.read_text(encoding="utf-8")
    total_label_ids = set(re.findall(r"id:\s*(\w*_total_label)\b", text))
    assert total_label_ids == {
        "solar_total_label",
        "power_total_label",
        "grid_total_label",
        "battery_total_label",
    }


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


# ---------------------------------------------------------------------------
# Header connection status ("LXP1 On"/"LXP1 Off") -- no icon/image asset
# ---------------------------------------------------------------------------


def test_header_status_off_when_not_connected() -> None:
    assert render_header_status("LXP1", False) == "LXP1 #FF3B30 Off#"


def test_header_status_on_when_connected() -> None:
    assert render_header_status("LXP1", True) == "LXP1 #00E676 On#"


def test_header_status_switches_on_freshness_transition() -> None:
    states = [False, True, True, False, True]
    rendered = [render_header_status("LXP2", s) for s in states]
    assert rendered == [
        "LXP2 #FF3B30 Off#",
        "LXP2 #00E676 On#",
        "LXP2 #00E676 On#",
        "LXP2 #FF3B30 Off#",
        "LXP2 #00E676 On#",
    ]


def test_header_status_never_updated_without_a_freshness_transition_in_yaml() -> None:
    # The header1_label/header2_label text must only be set inside the
    # fresh binary_sensor's on_state trigger, never inside a per-frame
    # numeric on_value lambda (that would repaint the header on every
    # telemetry frame, not just on an actual connect/disconnect -- a
    # jitter regression).
    text = YAML_PATH.read_text(encoding="utf-8")
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
    assert render_header_status("LXP1", dev.fresh) == "LXP1 #FF3B30 Off#"


# ---------------------------------------------------------------------------
# End-to-end scenario matching the Stage 37 design mockup exactly
# ---------------------------------------------------------------------------


def test_mockup_scenario_end_to_end() -> None:
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

    grid_1, grid_2 = recompute_grid(lpx1), recompute_grid(lpx2)
    assert (grid_1, grid_2) == (-1200.0, -600.0)
    assert combine_total(grid_1, grid_2) == -1800.0
    assert render_signed(grid_1) == ("-1200 W", "red")
    assert render_signed(grid_2) == ("-600 W", "red")

    battery_1, battery_2 = recompute_battery(lpx1), recompute_battery(lpx2)
    assert (battery_1, battery_2) == (600.0, 300.0)
    assert combine_total(battery_1, battery_2) == 900.0
    assert render_signed(battery_1) == ("+600 W", "green")

    assert render_percent(lpx1.soc) == "100%"
    assert render_percent(lpx1.max_backflow) == "70%"
    assert render_percent(lpx2.max_backflow) == "30%"

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
        test_power_total_combines_both_inverters,
        test_grid_export_is_positive_and_green,
        test_grid_import_is_negative_and_red,
        test_grid_total_with_opposite_flows_between_inverters,
        test_grid_total_same_direction_both_inverters,
        test_battery_charging_is_positive_and_green,
        test_battery_discharging_is_negative_and_red,
        test_battery_total_with_opposite_flows_between_inverters,
        test_not_fresh_blanks_every_derived_value_for_that_device,
        test_partial_input_blanks_that_derived_value_even_if_fresh,
        test_total_blanks_if_either_inverter_unavailable,
        test_total_never_treats_missing_inverter_as_zero,
        test_soc_renders_percent_or_dashes_when_unavailable,
        test_export_limit_renders_percent_or_dashes_when_unavailable,
        test_export_tracks_zero_export_enabled_directly,
        test_export_blanks_when_device_not_fresh_even_if_last_known_value_exists,
        test_export_blanks_before_first_value_ever_received,
        test_only_four_total_value_labels_exist_in_yaml,
        test_component_declares_total_sensor_only_for_solar_power_grid_battery,
        test_header_status_off_when_not_connected,
        test_header_status_on_when_connected,
        test_header_status_switches_on_freshness_transition,
        test_header_status_never_updated_without_a_freshness_transition_in_yaml,
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
