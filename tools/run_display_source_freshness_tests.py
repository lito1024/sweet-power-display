#!/usr/bin/env python3
"""Host-side mirror of source-freshness diagnostics and display blanking in
DisplayProtocolUARTComponent.

Mirrors handle_snapshot_frame_/handle_telemetry_frame_/update_stale_state_/
set_device_freshness_/mark_device_stale_ (display_protocol_uart.cpp): a
Gateway that is alive but has lost its LuxPower source keeps sending
frames on schedule (the transport link stays up), so "a frame arrived" is
deliberately NOT treated as "the data in it is fresh" -- data_fresh_ now
comes from each frame's own SnapshotFlagInputCacheValid/
HoldingCacheValid / TelemetryGroupFlagCacheValid bits (already correctly
age-gated by the Gateway -- see luxpower-gateway/tools/
run_gateway_source_freshness_tests.py), not from arrival timing alone.
The offline HMI preserves the last valid readings during short source/cache
gaps and only blanks values when update_stale_state_'s arrival-timeout sees
"no frame of any kind" (transport link genuinely dead).

This is a model for fast host testing, not a binding to the real
firmware -- keep it in sync with the C++ by hand when that logic
changes. See stages/Stage38.md.
"""
from __future__ import annotations

from pathlib import Path

STALE_TIMEOUT_MS = 5000


class DeviceFreshnessSim:
    """Mirrors one device_index's freshness-relevant state."""

    def __init__(self) -> None:
        self.have_snapshot = False
        self.link_connected = False
        self.data_fresh = False
        self.last_frame_ms: int | None = None
        self.input_source_fresh = False
        self.holding_source_fresh = False
        self.stale_transitions = 0  # counts visible mark_device_stale_ blanking calls
        self.restored_transitions = 0
        self.values_marked_stale = False

    def _set_device_freshness(self, fresh: bool) -> None:
        was_fresh = self.data_fresh
        self.data_fresh = fresh
        if fresh and not was_fresh:
            self.restored_transitions += 1

    def _mark_values_stale(self) -> None:
        if not self.values_marked_stale:
            self.values_marked_stale = True
            self.stale_transitions += 1

    def receive_v1_frame(self, now_ms: int, input_cache_valid: bool, holding_cache_valid: bool) -> None:
        # Mirrors handle_snapshot_frame_: V1 SnapshotPayload carries both
        # cache-valid bits together in one frame.
        self.have_snapshot = True
        self.link_connected = True
        self.last_frame_ms = now_ms
        source_fresh = input_cache_valid and holding_cache_valid
        if source_fresh:
            self.values_marked_stale = False
        self._set_device_freshness(source_fresh)

    def receive_v2_frame(self, now_ms: int, group: str, cache_valid: bool) -> None:
        # Mirrors handle_telemetry_frame_: a single V2 frame only ever
        # carries one group's bit (Status -> holding, everything else ->
        # input); accumulate both and require both.
        self.have_snapshot = True
        self.link_connected = True
        self.last_frame_ms = now_ms
        if group == "status":
            self.holding_source_fresh = cache_valid
        else:
            self.input_source_fresh = cache_valid
        source_fresh = self.input_source_fresh and self.holding_source_fresh
        if source_fresh:
            self.values_marked_stale = False
        self._set_device_freshness(source_fresh)

    def tick(self, now_ms: int, stale_timeout_ms: int = STALE_TIMEOUT_MS) -> None:
        # Mirrors update_stale_state_: transport-link fallback only.
        if not self.have_snapshot:
            return
        link_alive = self.last_frame_ms is not None and (now_ms - self.last_frame_ms) <= stale_timeout_ms
        if link_alive:
            return
        self.link_connected = False
        self._set_device_freshness(False)
        self._mark_values_stale()


# ---------------------------------------------------------------------------
# 1. Normal live telemetry
# ---------------------------------------------------------------------------


def test_normal_v1_frame_marks_fresh() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(1000, input_cache_valid=True, holding_cache_valid=True)
    assert dev.data_fresh is True


def test_normal_v2_frames_both_groups_marks_fresh() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v2_frame(1000, "fast", cache_valid=True)
    dev.receive_v2_frame(1001, "status", cache_valid=True)
    assert dev.data_fresh is True


# ---------------------------------------------------------------------------
# 2. Gateway alive, source stale: transport keeps delivering frames, but
#    each one reports the source as not fresh
# ---------------------------------------------------------------------------


def test_frames_keep_arriving_but_source_flag_false_goes_stale() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    assert dev.data_fresh is True
    # Gateway's own age check trips; it keeps sending (transport alive)
    # but now honestly reports the source as stale.
    dev.receive_v1_frame(1000, input_cache_valid=False, holding_cache_valid=False)
    assert dev.data_fresh is False
    # A pure arrival-timeout mechanism would NEVER have caught this,
    # since frames never stopped arriving.
    dev.tick(now_ms=1100, stale_timeout_ms=5000)
    assert dev.data_fresh is False
    assert dev.stale_transitions == 0
    assert dev.values_marked_stale is False


def test_v2_holding_group_alone_going_stale_marks_device_stale() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v2_frame(0, "fast", True)
    dev.receive_v2_frame(1, "status", True)
    assert dev.data_fresh is True
    dev.receive_v2_frame(2000, "status", cache_valid=False)
    assert dev.data_fresh is False  # combined AND: holding alone stale is enough
    assert dev.stale_transitions == 0
    assert dev.values_marked_stale is False


# ---------------------------------------------------------------------------
# 3. Cached values continue existing internally but must not refresh
#    freshness / must not repeatedly re-trigger blanking
# ---------------------------------------------------------------------------


def test_source_stale_does_not_blank_while_packets_keep_arriving() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    dev.receive_v1_frame(1000, False, False)
    dev.receive_v1_frame(2000, False, False)
    dev.receive_v1_frame(3000, False, False)
    assert dev.data_fresh is False
    assert dev.stale_transitions == 0
    assert dev.values_marked_stale is False


# ---------------------------------------------------------------------------
# 4. One inverter's source fails; the other remains fully live
# ---------------------------------------------------------------------------


def test_one_device_stale_other_independent() -> None:
    dev1 = DeviceFreshnessSim()
    dev2 = DeviceFreshnessSim()
    dev1.receive_v1_frame(0, True, True)
    dev2.receive_v1_frame(0, True, True)
    dev1.receive_v1_frame(1000, False, False)
    assert dev1.data_fresh is False
    assert dev2.data_fresh is True
    assert dev1.stale_transitions == 0


# ---------------------------------------------------------------------------
# 6/7. Source reconnect: TCP reconnect alone does not mark fresh; first
#      valid decoded sample does. Full automatic recovery, no reboot.
# ---------------------------------------------------------------------------


def test_recovery_only_on_a_frame_reporting_fresh_again() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    restored_at_start = dev.restored_transitions  # the first-ever frame also counts as a false->true transition
    dev.receive_v1_frame(1000, False, False)
    assert dev.data_fresh is False
    # Several more stale frames -- still not recovered.
    dev.receive_v1_frame(2000, False, False)
    assert dev.data_fresh is False
    # The Gateway's own age check clears (a real successful refresh
    # landed) -- the very next frame reports fresh, and recovery is
    # immediate, no reboot/extra step required on this side.
    dev.receive_v1_frame(3000, True, True)
    assert dev.data_fresh is True
    assert dev.restored_transitions == restored_at_start + 1


def test_v2_mixed_group_recovery_requires_both_bits_fresh_again() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v2_frame(0, "fast", True)
    dev.receive_v2_frame(1, "status", True)
    assert dev.data_fresh is True
    # Both blocks go stale together (e.g. TCP dropped).
    dev.receive_v2_frame(1000, "fast", False)
    dev.receive_v2_frame(1001, "status", False)
    assert dev.data_fresh is False
    # Input recovers but holding's last-known bit is still stale.
    dev.receive_v2_frame(2000, "fast", True)
    assert dev.data_fresh is False
    dev.receive_v2_frame(2001, "status", True)
    assert dev.data_fresh is True


# ---------------------------------------------------------------------------
# 8. Transport link itself dead (Gateway/Bridge/UART down): existing
#    arrival-timeout behavior must still work, independent of source flags
# ---------------------------------------------------------------------------


def test_transport_link_dead_still_detected_by_arrival_timeout() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    assert dev.data_fresh is True
    # No frames at all for longer than stale_timeout_ms.
    dev.tick(now_ms=4000, stale_timeout_ms=5000)
    assert dev.data_fresh is True  # not yet
    dev.tick(now_ms=5001, stale_timeout_ms=5000)
    assert dev.data_fresh is False
    assert dev.stale_transitions == 1
    assert dev.values_marked_stale is True


def test_transport_timeout_blanks_even_after_source_was_already_stale() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    dev.receive_v1_frame(1000, False, False)
    assert dev.data_fresh is False
    assert dev.stale_transitions == 0
    dev.tick(now_ms=7001, stale_timeout_ms=5000)
    assert dev.stale_transitions == 1
    assert dev.values_marked_stale is True


def test_transport_alive_source_fresh_arrival_timeout_never_fires() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    for t in range(1000, 20000, 1000):
        dev.receive_v1_frame(t, True, True)
        dev.tick(t, stale_timeout_ms=5000)
    assert dev.data_fresh is True
    assert dev.stale_transitions == 0


# ---------------------------------------------------------------------------
# Stage 44H: SPC ("Sweet POWER Controller" link) and effective Home Assistant
# icon state. Deliberately a SEPARATE, independent 3000ms watchdog from
# DeviceFreshnessSim/STALE_TIMEOUT_MS above -- that existing 5000ms model is
# per-Gateway-device (Inverter 1/2) transport freshness and must not be
# reused or altered for this. Mirrors handle_system_telemetry_frame_/
# update_stale_state_/update_ha_connected_display_ in
# display_protocol_uart.cpp -- keep in sync by hand if that logic changes.
# ---------------------------------------------------------------------------

SPC_LINK_TIMEOUT_MS = 3000


class SpcHaSim:
    """Mirrors spc_link_fresh_/ha_reported_connected_/effective HA state."""

    def __init__(self) -> None:
        self.have_system_frame = False
        self.spc_link_fresh = False  # boot-safe default: RED
        self.ha_reported_connected = False
        self.last_system_frame_ms: int | None = None

    @property
    def spc_green(self) -> bool:
        return self.spc_link_fresh

    @property
    def ha_effective_connected(self) -> bool:
        # Mirrors update_ha_connected_display_(): AND, never the raw report
        # alone -- a stale Controller link must never show stale "connected".
        return self.spc_link_fresh and self.ha_reported_connected

    def receive_system_frame(self, now_ms: int, ha_connected: bool | None = None) -> None:
        # Mirrors handle_system_telemetry_frame_: every periodic Controller/
        # System frame refreshes the timestamp and forces spc_link_fresh_
        # true, regardless of whether this specific frame happens to carry
        # the HA field (it always does in production -- see
        # send_system_measurement_telemetry_ -- but the None case here
        # proves the two are independently tracked).
        self.have_system_frame = True
        self.last_system_frame_ms = now_ms
        self.spc_link_fresh = True
        if ha_connected is not None:
            self.ha_reported_connected = ha_connected

    def tick(self, now_ms: int, timeout_ms: int = SPC_LINK_TIMEOUT_MS) -> None:
        # Mirrors update_stale_state_'s dedicated SPC/HA block: >=, not >,
        # per the required "no valid telemetry for >= 3000ms -> RED" spec.
        if not self.have_system_frame or not self.spc_link_fresh:
            return
        assert self.last_system_frame_ms is not None
        if (now_ms - self.last_system_frame_ms) >= timeout_ms:
            self.spc_link_fresh = False


def test_spc_boot_state_is_red() -> None:
    sim = SpcHaSim()
    assert sim.spc_green is False
    assert sim.ha_effective_connected is False


def test_spc_valid_frame_turns_green() -> None:
    sim = SpcHaSim()
    sim.receive_system_frame(0)
    assert sim.spc_green is True


def test_spc_remains_green_under_3000ms() -> None:
    sim = SpcHaSim()
    sim.receive_system_frame(0)
    sim.tick(2999)
    assert sim.spc_green is True


def test_spc_turns_red_at_3000ms() -> None:
    sim = SpcHaSim()
    sim.receive_system_frame(0)
    sim.tick(3000)
    assert sim.spc_green is False


def test_spc_turns_green_again_after_new_frame_following_stale() -> None:
    sim = SpcHaSim()
    sim.receive_system_frame(0)
    sim.tick(3000)
    assert sim.spc_green is False
    sim.receive_system_frame(3050)
    assert sim.spc_green is True


def test_ha_blue_when_reported_connected_and_spc_fresh() -> None:
    sim = SpcHaSim()
    sim.receive_system_frame(0, ha_connected=True)
    assert sim.ha_effective_connected is True


def test_ha_grey_when_reported_disconnected_and_spc_fresh() -> None:
    sim = SpcHaSim()
    sim.receive_system_frame(0, ha_connected=False)
    assert sim.ha_effective_connected is False


def test_ha_grey_when_reported_connected_but_spc_stale() -> None:
    sim = SpcHaSim()
    sim.receive_system_frame(0, ha_connected=True)
    sim.tick(3000)
    assert sim.spc_green is False
    # Fail-safe requirement: stale link must never keep showing blue.
    assert sim.ha_effective_connected is False


def test_ha_reconnect_turns_blue_automatically() -> None:
    sim = SpcHaSim()
    sim.receive_system_frame(0, ha_connected=False)
    assert sim.ha_effective_connected is False
    sim.receive_system_frame(1000, ha_connected=True)
    assert sim.ha_effective_connected is True


def test_existing_wifi_indicator_unchanged_by_stage_44h() -> None:
    # Stage 44H added HA/SPC labels into the same container but must not
    # touch the Wi-Fi icon's own semantics/colors -- confirmed here at the
    # YAML level rather than a runtime sim, since Wi-Fi status itself is
    # driven by wifi.connected/on_connect/on_disconnect actions elsewhere.
    yaml_path = Path(__file__).resolve().parent.parent / "sweet-power-display-offline-uart.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    assert 'id: wifi_icon_label' in text
    assert 'text: "\\uF1EB"' in text  # LV_SYMBOL_WIFI, unchanged glyph
    assert "0x666666" in text  # disconnected/grey Wi-Fi color still present
    assert "id: wifi_alert_label" in text


def test_ha_icon_uses_image_widgets_not_glyph() -> None:
    # Icon revision: the "HA" icon was switched from an LV_SYMBOL_HOME glyph
    # (recolored text) to the official Home Assistant logo, rasterized at
    # compile time from two user-supplied SVG files under pictures/. Confirm
    # the glyph-based label is gone and the image-widget wiring is present.
    yaml_path = Path(__file__).resolve().parent.parent / "sweet-power-display-offline-uart.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    assert "id: ha_icon_label" not in text  # old glyph label fully removed
    assert "id: ha_icon_img" in text
    assert "src: ha_icon_gray" in text  # boot-safe default source
    assert "id: ha_icon_blue" in text
    assert "id: ha_icon_gray" in text
    assert "pictures/home-assistant-blue.svg" in text
    assert "pictures/home-assistant-gray.svg" in text
    assert "lv_img_set_src(id(ha_icon_img), id(ha_icon_blue))" in text
    assert "lv_img_set_src(id(ha_icon_img), id(ha_icon_gray))" in text


def main() -> int:
    tests = [
        test_normal_v1_frame_marks_fresh,
        test_normal_v2_frames_both_groups_marks_fresh,
        test_frames_keep_arriving_but_source_flag_false_goes_stale,
        test_v2_holding_group_alone_going_stale_marks_device_stale,
        test_source_stale_does_not_blank_while_packets_keep_arriving,
        test_one_device_stale_other_independent,
        test_recovery_only_on_a_frame_reporting_fresh_again,
        test_v2_mixed_group_recovery_requires_both_bits_fresh_again,
        test_transport_link_dead_still_detected_by_arrival_timeout,
        test_transport_timeout_blanks_even_after_source_was_already_stale,
        test_transport_alive_source_fresh_arrival_timeout_never_fires,
        test_spc_boot_state_is_red,
        test_spc_valid_frame_turns_green,
        test_spc_remains_green_under_3000ms,
        test_spc_turns_red_at_3000ms,
        test_spc_turns_green_again_after_new_frame_following_stale,
        test_ha_blue_when_reported_connected_and_spc_fresh,
        test_ha_grey_when_reported_disconnected_and_spc_fresh,
        test_ha_grey_when_reported_connected_but_spc_stale,
        test_ha_reconnect_turns_blue_automatically,
        test_existing_wifi_indicator_unchanged_by_stage_44h,
        test_ha_icon_uses_image_widgets_not_glyph,
    ]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
    print(f"{len(tests)} display source-freshness tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
