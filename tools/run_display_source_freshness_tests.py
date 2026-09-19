#!/usr/bin/env python3
"""Host-side mirror of source-freshness diagnostics and display blanking in
DisplayProtocolUARTComponent.

Stage 38 established: a Gateway that is alive but has lost its LuxPower
source keeps sending frames on schedule (the transport link stays up), so
"a frame arrived" is deliberately NOT treated as "the data in it is
fresh" -- RAW freshness comes from each frame's own
SnapshotFlagInputCacheValid/HoldingCacheValid / TelemetryGroupFlagCacheValid
bits (already correctly age-gated by the Gateway -- see
luxpower-gateway/tools/run_gateway_source_freshness_tests.py), not from
arrival timing alone.

Stage 38's ORIGINAL Display-side implementation then tolerated raw
source-staleness INDEFINITELY as long as the transport link stayed up --
only a full stop of ALL packets for stale_timeout_ms_ ever blanked
anything. This is the exact 2026-09-18 Gateway-2 incident: Gateway 2 kept
sending frames while Controller diagnostics repeatedly reported
device_id=2 fresh=NO, and the Display kept showing "LXP2 On" with old
Solar/Battery/SOC numbers because nothing ever declared it stale while
packets kept flowing.

Stage 54 fixes this by porting esp_telemetry_espnow.cpp's already-shipped
Stage 43A pattern to the Display: RAW freshness (last_raw_fresh_ms_,
updated only when a frame reports itself source-fresh) is debounced
against source_fresh_grace_ms_ (10s, matching the Controller's identical
window) by update_stale_state_ before it is allowed to flip the EXPOSED
data_fresh_ false -- recovery remains fully immediate and un-debounced.
This is layered UNDER a second, independent, unchanged transport-arrival
timeout (stale_timeout_ms_ / last_frame_ms_, 60s in production) that
detects the transport link itself being fully dead. The two are
deliberately different lengths and produce two distinct visible states:
Stale (packets arriving, source not fresh past the short grace) and
Offline (no packets at all past the long transport timeout) -- see
update_device_status_'s 0/1/2/3 Waiting/Fresh/Stale/Offline code.

Numeric sensor entities (PV1/PV2/SOC/Grid/Battery-charge/-discharge/etc.)
go unavailable (NAN) on CONFIRMED staleness rather than freezing at their
last value or silently substituting zero -- see mark_device_stale_. The
per-field publish gate (publish_telemetry_field_'s `if
(!this->data_fresh_[device_index]) return;`) additionally prevents a
Gateway that keeps re-sending its last successfully-cached reading (its
own LuxPowerTCP library accessors never expire that cache by age) from
making a stale value look freshly-updated on this Display.

This is a model for fast host testing, not a binding to the real
firmware -- keep it in sync with the C++ by hand when that logic
changes. See stages/Stage38.md, stages/Stage54.md.
"""
from __future__ import annotations

import math
from pathlib import Path

NAN = float("nan")
STALE_TIMEOUT_MS = 5000  # transport-arrival-only (Offline); 60s in the production YAML
SOURCE_FRESH_GRACE_MS = 10000  # Stage 54, matches esp_telemetry_espnow.cpp's Stage 43A window

# Stage 54 device_status_sensor_ codes -- see update_device_status_.
STATUS_WAITING = 0
STATUS_FRESH = 1
STATUS_STALE = 2
STATUS_OFFLINE = 3


class DeviceFreshnessSim:
    """Mirrors one device_index's freshness-relevant state and entity
    publish behavior, post-Stage-54."""

    def __init__(self) -> None:
        self.have_snapshot = False
        self.link_connected = False
        # EXTERNALLY VISIBLE (debounced) freshness -- what the LVGL header,
        # recompute_derived_, and publish_telemetry_field_'s gate all see.
        self.data_fresh = False
        self.last_frame_ms: int | None = None
        # Stage 54: last time RAW freshness (a frame reporting itself
        # source-fresh) was observed -- mirrors last_raw_fresh_ms_, the
        # sole signal update_stale_state_ debounces against for Stale.
        self.last_raw_fresh_ms: int | None = None
        self.input_source_fresh = False
        self.holding_source_fresh = False
        self.stale_transitions = 0  # counts visible mark_device_stale_ blanking calls
        self.restored_transitions = 0
        # Field values: None = never published; NAN = published unavailable
        # (mark_device_stale_); a float = last confirmed, trustworthy value.
        self.pv1_power: float | None = None
        self.pv2_power: float | None = None
        self.battery_soc: float | None = None
        self.power_to_grid: float | None = None
        self.power_from_grid: float | None = None
        self.max_backflow_power: float | None = None

    def _set_device_freshness(self, fresh: bool) -> None:
        was_fresh = self.data_fresh
        self.data_fresh = fresh
        if not fresh and was_fresh:
            self.stale_transitions += 1
            self._mark_device_stale()
        if fresh and not was_fresh:
            self.restored_transitions += 1

    def _mark_device_stale(self) -> None:
        # Mirrors mark_device_stale_: every instantaneous measurement goes
        # NAN, never frozen, never a synthetic zero.
        self.pv1_power = NAN
        self.pv2_power = NAN
        self.battery_soc = NAN
        self.power_to_grid = NAN
        self.power_from_grid = NAN
        self.max_backflow_power = NAN

    def receive_v1_frame(
        self,
        now_ms: int,
        input_cache_valid: bool,
        holding_cache_valid: bool,
        pv1_power: float | None = None,
        pv2_power: float | None = None,
        battery_soc: float | None = None,
    ) -> None:
        # Mirrors handle_snapshot_frame_: V1 SnapshotPayload carries both
        # cache-valid bits together in one frame.
        self.have_snapshot = True
        self.link_connected = True
        self.last_frame_ms = now_ms
        source_fresh = input_cache_valid and holding_cache_valid
        # Stage 54: immediate/undebounced restore; only update_stale_state_
        # (tick()) may ever declare this device newly stale.
        if source_fresh:
            self.last_raw_fresh_ms = now_ms
            self._set_device_freshness(True)
        # V1 gates its legacy fields on THIS frame's own source_fresh
        # (mirrors publish_snapshot_'s source_fresh parameter) -- unlike
        # V2's gate on the debounced data_fresh_ below.
        if source_fresh:
            if pv1_power is not None:
                self.pv1_power = pv1_power
            if pv2_power is not None:
                self.pv2_power = pv2_power
            if battery_soc is not None:
                self.battery_soc = battery_soc

    def receive_v2_frame(
        self,
        now_ms: int,
        group: str,
        cache_valid: bool,
        field: str | None = None,
        value: float | None = None,
    ) -> None:
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
            self.last_raw_fresh_ms = now_ms
            self._set_device_freshness(True)
        # Stage 54: publish_telemetry_field_ gates on the (possibly
        # just-restored, above) debounced data_fresh_, not this specific
        # frame's own bit -- so a value keeps updating from any arriving
        # frame for as long as the device is still within the source-fresh
        # grace window, matching "fresh telemetry must still be processed
        # immediately" while a frame that reports itself not-fresh, once
        # data_fresh_ has actually been debounced false, can no longer
        # sneak a value through.
        if self.data_fresh and field is not None:
            if field == "pv1_power":
                self.pv1_power = value
            elif field == "pv2_power":
                self.pv2_power = value
            elif field == "battery_soc":
                self.battery_soc = value
            elif field == "power_to_grid":
                self.power_to_grid = value
            elif field == "power_from_grid":
                self.power_from_grid = value
            elif field == "max_backflow_power":
                self.max_backflow_power = value

    def tick(
        self,
        now_ms: int,
        stale_timeout_ms: int = STALE_TIMEOUT_MS,
        source_fresh_grace_ms: int = SOURCE_FRESH_GRACE_MS,
    ) -> None:
        # Mirrors update_stale_state_: two independent checks per device.
        if not self.have_snapshot:
            return

        # 1) Transport-link fallback (Offline): no frame of any kind
        #    arrived within stale_timeout_ms_ -- unchanged since Stage 32/38.
        link_alive = self.last_frame_ms is not None and (now_ms - self.last_frame_ms) <= stale_timeout_ms
        if not link_alive:
            self.link_connected = False
            self._set_device_freshness(False)
            return

        # 2) Stage 54 debounce (Stale): transport alive, but the source has
        #    not reported itself fresh for source_fresh_grace_ms_.
        if self.data_fresh:
            within_grace = (
                self.last_raw_fresh_ms is not None
                and (now_ms - self.last_raw_fresh_ms) <= source_fresh_grace_ms
            )
            if not within_grace:
                self._set_device_freshness(False)

    @property
    def solar(self) -> float:
        # Mirrors recompute_derived_'s solar_ok gate: values_available
        # (data_fresh_) AND both raw sensors have a published state.
        if not self.data_fresh or self.pv1_power is None or self.pv2_power is None:
            return NAN
        return self.pv1_power + self.pv2_power

    @property
    def grid_net(self) -> float:
        if not self.data_fresh or self.power_to_grid is None or self.power_from_grid is None:
            return NAN
        return self.power_to_grid - self.power_from_grid

    def device_status(self) -> int:
        # Mirrors update_device_status_'s exact priority order.
        if not self.have_snapshot:
            return STATUS_WAITING
        if not self.link_connected:
            return STATUS_OFFLINE
        if not self.data_fresh:
            return STATUS_STALE
        return STATUS_FRESH


def combine_total(a: float, b: float) -> float:
    # Mirrors combine_total_(): NaN propagates, a missing/stale inverter is
    # never silently treated as zero.
    if math.isnan(a) or math.isnan(b):
        return NAN
    return a + b


# ---------------------------------------------------------------------------
# 1. Normal live telemetry
# ---------------------------------------------------------------------------


def test_normal_v1_frame_marks_fresh() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(1000, input_cache_valid=True, holding_cache_valid=True, pv1_power=2276.0)
    assert dev.data_fresh is True
    assert dev.pv1_power == 2276.0
    assert dev.device_status() == STATUS_FRESH


def test_normal_v2_frames_both_groups_marks_fresh() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v2_frame(1000, "fast", cache_valid=True)
    dev.receive_v2_frame(1001, "status", cache_valid=True)
    assert dev.data_fresh is True
    # Both groups now fresh -- a subsequent field-carrying frame publishes
    # immediately.
    dev.receive_v2_frame(1002, "fast", cache_valid=True, field="pv1_power", value=2276.0)
    assert dev.pv1_power == 2276.0


def test_repeated_identical_readings_remain_valid() -> None:
    # Required scenario: a steady, genuinely fresh reading that happens not
    # to change must never be treated as suspicious/stale merely because
    # the number is unchanged -- gating is purely on source_fresh, never on
    # "did the value change".
    dev = DeviceFreshnessSim()
    for t in range(0, 30000, 1000):
        dev.receive_v1_frame(t, True, True, pv1_power=2276.0)
        dev.tick(t)
    assert dev.data_fresh is True
    assert dev.stale_transitions == 0
    assert dev.pv1_power == 2276.0


# ---------------------------------------------------------------------------
# 2. Required scenario: packets continue arriving while source freshness is
#    false. This is the exact 2026-09-18 Gateway-2 incident -- Controller
#    diagnostics repeatedly reported device_id=2 fresh=NO while Gateway 2
#    kept sending frames. A single not-fresh frame must NOT blank
#    immediately (a short bounded grace period avoids flicker on one
#    dropped/corrupted frame), but continued not-fresh reporting for the
#    full source_fresh_grace_ms_ window must ALWAYS blank eventually, no
#    matter how many "fresh-looking" packets keep arriving in between.
# ---------------------------------------------------------------------------


def test_single_not_fresh_frame_within_grace_does_not_blank() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True, pv1_power=100.0)
    dev.receive_v1_frame(1000, input_cache_valid=False, holding_cache_valid=False)
    # Still within the 10s grace window -- no transition yet, matching the
    # "short bounded grace period avoids flicker" requirement.
    dev.tick(now_ms=1100)
    assert dev.data_fresh is True
    assert dev.stale_transitions == 0
    assert dev.device_status() == STATUS_FRESH


def test_continued_packet_arrival_never_preserves_stale_measurements_indefinitely() -> None:
    # This is the incident itself, reproduced: Gateway 2 keeps sending a
    # frame every second, every one of them honestly reporting the source
    # as not fresh. A pure arrival-timeout mechanism (the pre-Stage-54
    # design) would NEVER have caught this, since frames never stopped
    # arriving. Stage 54's debounce must still declare Stale once the
    # grace window elapses, regardless of continued packet arrival.
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True, pv1_power=100.0, pv2_power=50.0, battery_soc=42.0)
    assert dev.data_fresh is True
    for t in range(1000, 12000, 1000):
        dev.receive_v1_frame(t, False, False)
        dev.tick(t)
    assert dev.data_fresh is False
    assert dev.stale_transitions == 1
    assert dev.device_status() == STATUS_STALE
    # Every instantaneous measurement this Display shows is unavailable --
    # never frozen at the last (now 12s stale) reading.
    assert math.isnan(dev.pv1_power)
    assert math.isnan(dev.pv2_power)
    assert math.isnan(dev.battery_soc)
    assert math.isnan(dev.solar)


def test_v2_holding_group_alone_going_stale_eventually_blanks() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v2_frame(0, "fast", True)
    dev.receive_v2_frame(1, "status", True)
    assert dev.data_fresh is True
    for t in range(2000, 14000, 2000):
        dev.receive_v2_frame(t, "status", cache_valid=False)  # combined AND: holding alone stale is enough
        dev.tick(t)
    assert dev.data_fresh is False
    assert dev.stale_transitions == 1


def test_cached_retransmission_of_last_good_value_does_not_count_as_fresh() -> None:
    # Verified root cause (2026-09-18 incident): LuxPowerTCP's per-field
    # accessors (pv1Power/pv2Power/batterySoc/...) succeed as long as their
    # cache was EVER populated -- that flag never clears on its own, so the
    # Gateway keeps re-sending the same frozen number every cycle, looking
    # identical on the wire to a genuinely fresh reading. Only the frame's
    # OWN cache-valid bit (age-gated by the Gateway, independent of that
    # accessor) may ever mark this device fresh again.
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True, pv1_power=2276.0)
    for t in range(1000, 12000, 1000):
        # The Gateway keeps sending the SAME cached 2276.0 reading, but its
        # own honest age-gated flags now say the source is not fresh.
        dev.receive_v1_frame(t, False, False, pv1_power=2276.0)
        dev.tick(t)
    assert dev.data_fresh is False
    assert math.isnan(dev.pv1_power)  # never resurrected by the repeated cached number


# ---------------------------------------------------------------------------
# 3. Complete transport loss (Offline): no frame of any kind arrives at
#    all, distinct from Stale (packets arriving, source not fresh).
# ---------------------------------------------------------------------------


def test_transport_link_dead_detected_by_arrival_timeout() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    assert dev.data_fresh is True
    dev.tick(now_ms=4000, stale_timeout_ms=5000)
    assert dev.data_fresh is True  # not yet
    assert dev.device_status() == STATUS_FRESH
    dev.tick(now_ms=5001, stale_timeout_ms=5000)
    assert dev.data_fresh is False
    assert dev.stale_transitions == 1
    assert dev.link_connected is False
    assert dev.device_status() == STATUS_OFFLINE


def test_offline_is_distinct_from_stale_in_device_status() -> None:
    # Stage 54's core UX requirement: Offline (transport itself dead) and
    # Stale (transport alive, source not fresh) must render as visibly
    # different states, not both collapsed into one "not fresh" label.
    stale_dev = DeviceFreshnessSim()
    stale_dev.receive_v1_frame(0, True, True)
    for t in range(1000, 12000, 1000):
        stale_dev.receive_v1_frame(t, False, False)  # transport alive throughout
        stale_dev.tick(t, stale_timeout_ms=60000)  # production's 60s Offline threshold
    assert stale_dev.device_status() == STATUS_STALE

    offline_dev = DeviceFreshnessSim()
    offline_dev.receive_v1_frame(0, True, True)
    offline_dev.tick(now_ms=60001, stale_timeout_ms=60000)  # no frames at all
    assert offline_dev.device_status() == STATUS_OFFLINE


def test_expiration_runs_even_when_no_further_packets_arrive() -> None:
    # Both the Offline and Stale transitions must be driven by tick() alone
    # (mirrors update_stale_state_ running every loop() regardless of
    # frame arrival) -- no new packet is required to notice either.
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    assert dev.stale_transitions == 0
    dev.tick(now_ms=20000)  # nothing else ever arrives again
    assert dev.data_fresh is False
    assert dev.stale_transitions == 1


def test_transport_alive_source_fresh_arrival_timeout_never_fires() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    for t in range(1000, 20000, 1000):
        dev.receive_v1_frame(t, True, True)
        dev.tick(t, stale_timeout_ms=5000)
    assert dev.data_fresh is True
    assert dev.stale_transitions == 0


# ---------------------------------------------------------------------------
# 4. One stale inverter with the other healthy; affected totals become
#    unavailable while the healthy inverter's own column stays operational.
# ---------------------------------------------------------------------------


def test_one_device_stale_other_independent() -> None:
    dev1 = DeviceFreshnessSim()
    dev2 = DeviceFreshnessSim()
    dev1.receive_v1_frame(0, True, True, pv1_power=100.0, pv2_power=50.0)
    dev2.receive_v1_frame(0, True, True, pv1_power=200.0, pv2_power=80.0)
    for t in range(1000, 12000, 1000):
        dev1.receive_v1_frame(t, False, False)
        dev1.tick(t)
        dev2.receive_v1_frame(t, True, True, pv1_power=200.0, pv2_power=80.0)
        dev2.tick(t)
    assert dev1.data_fresh is False
    assert dev2.data_fresh is True
    # The healthy inverter's own column stays fully operational.
    assert dev2.solar == 280.0
    assert math.isnan(dev1.solar)


def test_total_unavailable_when_either_inverter_invalid_or_stale() -> None:
    dev1 = DeviceFreshnessSim()
    dev2 = DeviceFreshnessSim()
    dev1.receive_v1_frame(0, True, True, pv1_power=100.0, pv2_power=50.0)
    dev2.receive_v1_frame(0, True, True, pv1_power=200.0, pv2_power=80.0)
    assert combine_total(dev1.solar, dev2.solar) == 430.0
    for t in range(1000, 12000, 1000):
        dev1.receive_v1_frame(t, False, False)
        dev1.tick(t)
    # A partial total (only inverter 2's contribution) must never be
    # silently presented as the complete system total.
    total = combine_total(dev1.solar, dev2.solar)
    assert math.isnan(total)
    assert total != dev2.solar


# ---------------------------------------------------------------------------
# 5. Startup before valid measurements: waiting/unknown, no restored or
#    cached numbers appearing live.
# ---------------------------------------------------------------------------


def test_startup_before_any_frame_is_waiting_not_a_cached_number() -> None:
    dev = DeviceFreshnessSim()
    assert dev.device_status() == STATUS_WAITING
    assert dev.data_fresh is False
    assert math.isnan(dev.solar)  # never a leftover/default 0 or cached value


# ---------------------------------------------------------------------------
# 6/7. Source reconnect and recovery: TCP reconnect alone does not mark
#      fresh; the first genuinely fresh decoded sample does, immediately
#      and automatically, without restarting any node. Recovery of the
#      source-fresh status alone must not resurrect a field that has not
#      itself become valid again (partial/group recovery).
# ---------------------------------------------------------------------------


def test_recovery_only_on_a_frame_reporting_fresh_again() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    restored_at_start = dev.restored_transitions  # the first-ever frame also counts as a false->true transition
    dev.receive_v1_frame(1000, False, False)
    assert dev.data_fresh is True  # still within the 10s grace window
    dev.tick(11001)
    assert dev.data_fresh is False
    # The Gateway's own age check clears (a real successful refresh
    # landed) -- the very next frame reports fresh, and recovery is
    # immediate, no reboot/extra step required on this side.
    dev.receive_v1_frame(12000, True, True)
    assert dev.data_fresh is True
    assert dev.restored_transitions == restored_at_start + 1


def test_v2_mixed_group_recovery_requires_both_bits_fresh_again() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v2_frame(0, "fast", True)
    dev.receive_v2_frame(1, "status", True)
    assert dev.data_fresh is True
    # Both blocks go stale together (e.g. TCP dropped) long enough to clear
    # the grace window.
    for t in range(1000, 12000, 1000):
        dev.receive_v2_frame(t, "fast", False)
        dev.receive_v2_frame(t + 1, "status", False)
        dev.tick(t + 1)
    assert dev.data_fresh is False
    # Input recovers but holding's last-known bit is still stale -- not
    # fresh yet (a single group's own recovery must not resurrect the
    # other group's fields).
    dev.receive_v2_frame(12000, "fast", True)
    assert dev.data_fresh is False
    dev.receive_v2_frame(12001, "status", True)
    assert dev.data_fresh is True


def test_partial_group_recovery_does_not_resurrect_the_other_groups_stale_field() -> None:
    # Required scenario: recovery of the source status alone must not
    # resurrect cached fields that have not themselves become valid again.
    dev = DeviceFreshnessSim()
    dev.receive_v2_frame(0, "status", True)
    dev.receive_v2_frame(1, "fast", True, field="pv1_power", value=100.0)
    assert dev.pv1_power == 100.0
    for t in range(2000, 14000, 2000):
        dev.receive_v2_frame(t, "fast", False)
        dev.receive_v2_frame(t, "status", False)
        dev.tick(t)
    assert dev.data_fresh is False
    assert math.isnan(dev.pv1_power)
    # "status" group recovers, but the "fast" group (which actually carries
    # pv1_power) has not sent a new value yet -- data_fresh_ requires BOTH,
    # so it must still be false, and pv1_power must still read unavailable,
    # not silently reappear as the old 100.0.
    dev.receive_v2_frame(14000, "status", True)
    assert dev.data_fresh is False
    assert math.isnan(dev.pv1_power)
    # Only once the fast group ALSO reports itself fresh again, carrying a
    # genuinely new reading, does the field become trustworthy again.
    dev.receive_v2_frame(14001, "fast", True, field="pv1_power", value=105.0)
    assert dev.data_fresh is True
    assert dev.pv1_power == 105.0


def test_automatic_full_recovery_without_node_restart() -> None:
    # No restart/reboot concept exists anywhere in this simulation --
    # recovery is purely a function of the next frame's own content,
    # matching the requirement that recovery must happen automatically.
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True, pv1_power=100.0)
    for t in range(1000, 12000, 1000):
        dev.receive_v1_frame(t, False, False)
        dev.tick(t)
    assert dev.device_status() == STATUS_STALE
    dev.receive_v1_frame(12000, True, True, pv1_power=110.0)
    assert dev.device_status() == STATUS_FRESH
    assert dev.pv1_power == 110.0


# ---------------------------------------------------------------------------
# 8. Transport link itself dead (Gateway/Bridge/UART down): unchanged
#    arrival-timeout behavior, independent of source flags, still fires
#    even after the source was already confirmed Stale.
# ---------------------------------------------------------------------------


def test_transport_timeout_blanks_even_after_source_was_already_stale() -> None:
    dev = DeviceFreshnessSim()
    dev.receive_v1_frame(0, True, True)
    for t in range(1000, 12000, 1000):
        dev.receive_v1_frame(t, False, False)
        dev.tick(t, stale_timeout_ms=60000)  # transport stays alive throughout
    assert dev.data_fresh is False  # already Stale
    assert dev.stale_transitions == 1
    # Now the transport itself dies too (last frame was at t=11000).
    dev.tick(now_ms=71001, stale_timeout_ms=60000)
    assert dev.link_connected is False
    assert dev.device_status() == STATUS_OFFLINE


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


def test_spc_icon_uses_image_widgets_not_glyph() -> None:
    # Icon revision: the "SPC" text label (green/red recolor) was switched
    # to the Sweet POWER Controller house+bolt mark, rasterized at compile
    # time from two pre-colored SVG files under pictures/ -- same pattern
    # as test_ha_icon_uses_image_widgets_not_glyph above. Confirm the old
    # text label and its colors are gone and the image-widget wiring is
    # present.
    yaml_path = Path(__file__).resolve().parent.parent / "sweet-power-display-offline-uart.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    assert "id: spc_icon_label" not in text  # old text label fully removed
    assert 'text: "SPC"' not in text
    assert "0xCC0000" not in text  # old red (stale) text color
    assert "0x00CC44" not in text  # old green (fresh) text color
    assert "id: spc_icon_img" in text
    assert "src: spc_icon_gray" in text  # boot-safe default source
    assert "id: spc_icon_yellow" in text
    assert "id: spc_icon_gray" in text
    assert "pictures/spc-icon-yellow.svg" in text
    assert "pictures/spc-icon-gray.svg" in text
    assert "lv_img_set_src(id(spc_icon_img), id(spc_icon_yellow))" in text
    assert "lv_img_set_src(id(spc_icon_img), id(spc_icon_gray))" in text


def main() -> int:
    tests = [
        test_normal_v1_frame_marks_fresh,
        test_normal_v2_frames_both_groups_marks_fresh,
        test_repeated_identical_readings_remain_valid,
        test_single_not_fresh_frame_within_grace_does_not_blank,
        test_continued_packet_arrival_never_preserves_stale_measurements_indefinitely,
        test_v2_holding_group_alone_going_stale_eventually_blanks,
        test_cached_retransmission_of_last_good_value_does_not_count_as_fresh,
        test_transport_link_dead_detected_by_arrival_timeout,
        test_offline_is_distinct_from_stale_in_device_status,
        test_expiration_runs_even_when_no_further_packets_arrive,
        test_transport_alive_source_fresh_arrival_timeout_never_fires,
        test_one_device_stale_other_independent,
        test_total_unavailable_when_either_inverter_invalid_or_stale,
        test_startup_before_any_frame_is_waiting_not_a_cached_number,
        test_recovery_only_on_a_frame_reporting_fresh_again,
        test_v2_mixed_group_recovery_requires_both_bits_fresh_again,
        test_partial_group_recovery_does_not_resurrect_the_other_groups_stale_field,
        test_automatic_full_recovery_without_node_restart,
        test_transport_timeout_blanks_even_after_source_was_already_stale,
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
        test_spc_icon_uses_image_widgets_not_glyph,
    ]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
    print(f"{len(tests)} display source-freshness tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
