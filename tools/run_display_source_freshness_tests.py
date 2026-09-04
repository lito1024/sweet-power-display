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
    ]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
    print(f"{len(tests)} display source-freshness tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
