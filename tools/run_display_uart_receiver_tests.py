#!/usr/bin/env python3
from __future__ import annotations

import struct
from pathlib import Path

MAGIC = b"SPDP"
VERSION = 1
VERSION_V2 = 2
TYPE_SNAPSHOT = 1
TYPE_FAST = 16
HEADER_SIZE = 14
PAYLOAD_SIZE = 32
CRC_SIZE = 2
FRAME_SIZE = HEADER_SIZE + PAYLOAD_SIZE + CRC_SIZE
MAX_PAYLOAD_SIZE = 128
FIELD_PV1_POWER = 1001
FIELD_BATTERY_SOC = 2001
V2_PAYLOAD_HEADER_SIZE = 5
TYPE_DIAGNOSTICS = 19
# DIAGNOSTICS-group production fields, see
# ESP-LUXPOWER/data/luxpower_entities.json entities[].
FIELD_BATTERY_CAPACITY = 9001
FIELD_BMS_MAX_CELL_TEMPERATURE = 9002
FIELD_POWER_TO_GRID = 9003
FIELD_POWER_FROM_GRID = 9004
FIELD_GRID_FLOW = 9005
# Stage 30.1: first/middle/last positions of the 79-field extended-diagnostics
# rotation (9006..9084), used to prove multi-batch delivery end-to-end.
FIELD_PV1_VOLTAGE = 9006
FIELD_ENERGY_TO_GRID_TOTAL = 9047
FIELD_GENERATOR_ENERGY_TODAY = 9084
FIELD_SYSTEM_OUTPUT_VOLTAGE = 10001
FIELD_SYSTEM_OUTPUT_CURRENT = 10002
FIELD_SYSTEM_OUTPUT_POWER = 10003
FIELD_SYSTEM_OUTPUT_ENERGY = 10004
FIELD_SYSTEM_OUTPUT_FREQUENCY = 10005
FIELD_SYSTEM_OUTPUT_POWER_FACTOR = 10006
FIELD_GRID_INPUT_VOLTAGE = 10007
FIELD_GRID_INPUT_CURRENT = 10008
FIELD_GRID_INPUT_POWER = 10009
FIELD_GRID_INPUT_ENERGY = 10010
FIELD_GRID_INPUT_FREQUENCY = 10011
FIELD_GRID_INPUT_POWER_FACTOR = 10012
FIELD_GRID_RAW_VOLTAGE = 10013
FIELD_DISPLAY_ENABLED = 10014
FIELD_DISPLAY_MAINTENANCE_WIFI_ACTUAL = 12001
INVALID_I32 = -2147483648
DEVICE_CONTROLLER_SYSTEM = 3
REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKED_FIELDS = (
    FIELD_PV1_POWER,
    FIELD_BATTERY_SOC,
    FIELD_BATTERY_CAPACITY,
    FIELD_BMS_MAX_CELL_TEMPERATURE,
    FIELD_POWER_TO_GRID,
    FIELD_POWER_FROM_GRID,
    FIELD_GRID_FLOW,
    FIELD_PV1_VOLTAGE,
    FIELD_ENERGY_TO_GRID_TOTAL,
    FIELD_GENERATOR_ENERGY_TODAY,
)
SYSTEM_FIELDS = (
    FIELD_SYSTEM_OUTPUT_VOLTAGE,
    FIELD_SYSTEM_OUTPUT_CURRENT,
    FIELD_SYSTEM_OUTPUT_POWER,
    FIELD_SYSTEM_OUTPUT_ENERGY,
    FIELD_SYSTEM_OUTPUT_FREQUENCY,
    FIELD_SYSTEM_OUTPUT_POWER_FACTOR,
    FIELD_GRID_INPUT_VOLTAGE,
    FIELD_GRID_INPUT_CURRENT,
    FIELD_GRID_INPUT_POWER,
    FIELD_GRID_INPUT_ENERGY,
    FIELD_GRID_INPUT_FREQUENCY,
    FIELD_GRID_INPUT_POWER_FACTOR,
    FIELD_GRID_RAW_VOLTAGE,
    FIELD_DISPLAY_ENABLED,
)


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
            crc &= 0xFFFF
    return crc


def encode_snapshot(sequence: int, version: int = VERSION, device_id: int = 1) -> bytes:
    payload = struct.pack(
        "<iiHiiIH8s",
        2276,
        1739,
        1000,
        0,
        0,
        123456,
        0x000F,
        bytes([device_id]) + b"\x00" * 7,
    )
    header = MAGIC + bytes([version, TYPE_SNAPSHOT]) + struct.pack("<HHI", len(payload), sequence & 0xFFFF, 1234)
    without_crc = header + payload
    return without_crc + struct.pack("<H", crc16(without_crc))


def encode_v2(
    sequence: int, fields: list[tuple[int, int]], msg_type: int = TYPE_FAST, version: int = VERSION_V2, device_id: int = 1
) -> bytes:
    payload = struct.pack("<BBBH", device_id, 1, len(fields), 0x0003)
    for field_id, value in fields:
        payload += struct.pack("<Hi", field_id, value)
    header = MAGIC + bytes([version, msg_type]) + struct.pack("<HHI", len(payload), sequence & 0xFFFF, 1234)
    without_crc = header + payload
    return without_crc + struct.pack("<H", crc16(without_crc))


def device_index_for_id(device_id: int) -> int | None:
    # Mirrors DisplayProtocolUARTComponent::device_index_for_id_ (Stage 32):
    # 0/1 for device_id 1/2, None for anything else (unrecognized/aggregate).
    if device_id == 1:
        return 0
    if device_id == 2:
        return 1
    return None


class Receiver:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.valid = 0
        self.crc_errors = 0
        self.decode_errors = 0
        self.sequence_gaps = 0
        self.duplicates = 0
        # Stage 32: keyed by (version, messageType, deviceId), mirroring the
        # ESP-TELEMETRY Decoder fix -- two devices' interleaved sequences
        # must never be compared against each other.
        self.last_sequence: dict[tuple[int, int, int], int] = {}
        self.last_frame_ms: int | None = None
        # Legacy single-device view: last value seen for a field_id,
        # regardless of source. All pre-Stage-32 tests use device_id=1
        # exclusively, so this is unchanged for them.
        self.values: dict[int, int] = {}
        # Stage 32: proper per-device view, keyed by (device_id, field_id) --
        # what the real Display component now publishes to (two independent
        # sensor arrays). device_id 0/other (unrecognized) is intentionally
        # not recorded here, mirroring device_index_for_id_ returning None.
        self.device_values: dict[tuple[int, int], int] = {}
        # Stage 39B: Controller/system values live at device_id 3 and are
        # separate from the inverter arrays, not a synthetic inverter 3.
        self.system_values: dict[int, int | None] = {}
        self.last_frame_ms_by_device: dict[int, int] = {}

    def feed(self, data: bytes, now_ms: int = 0) -> None:
        for byte in data:
            self.buffer.append(byte)
            while self.buffer and not bytes(self.buffer).startswith(MAGIC[: len(self.buffer)]):
                del self.buffer[0]
            if len(self.buffer) < HEADER_SIZE:
                continue
            if self.buffer[:4] != MAGIC:
                del self.buffer[0]
                continue
            version = self.buffer[4]
            payload_len = struct.unpack_from("<H", self.buffer, 6)[0]
            if payload_len > MAX_PAYLOAD_SIZE:
                self.decode_errors += 1
                self.buffer.clear()
                continue
            total = HEADER_SIZE + payload_len + CRC_SIZE
            if len(self.buffer) < total:
                continue
            frame = bytes(self.buffer[:total])
            del self.buffer[:total]
            if version not in (VERSION, VERSION_V2):
                self.decode_errors += 1
                continue
            received_crc = struct.unpack_from("<H", frame, len(frame) - CRC_SIZE)[0]
            if received_crc != crc16(frame[:-CRC_SIZE]):
                self.crc_errors += 1
                continue
            sequence = struct.unpack_from("<H", frame, 8)[0]
            message_type = frame[5]
            payload_bytes = frame[HEADER_SIZE:-CRC_SIZE]
            if version == VERSION_V2:
                device_id = payload_bytes[0] if payload_bytes else 0
            else:
                device_id = payload_bytes[24] if len(payload_bytes) >= PAYLOAD_SIZE else 0
            # Stage 32: stream key includes device_id, mirroring the
            # ESP-TELEMETRY Decoder fix.
            stream = (version, message_type, device_id)
            if stream in self.last_sequence:
                if sequence == self.last_sequence[stream]:
                    self.duplicates += 1
                elif sequence != ((self.last_sequence[stream] + 1) & 0xFFFF):
                    self.sequence_gaps += 1
            self.last_sequence[stream] = sequence
            self.last_frame_ms = now_ms
            device_index = device_index_for_id(device_id)
            if device_index is not None:
                self.last_frame_ms_by_device[device_id] = now_ms
            if version == VERSION_V2:
                payload = payload_bytes
                count = payload[2]
                for index in range(count):
                    offset = V2_PAYLOAD_HEADER_SIZE + index * 6
                    field_id, value = struct.unpack_from("<Hi", payload, offset)
                    if device_id == DEVICE_CONTROLLER_SYSTEM and field_id in SYSTEM_FIELDS:
                        self.system_values[field_id] = None if value == INVALID_I32 else value
                    if field_id in TRACKED_FIELDS:
                        self.values[field_id] = value
                        if device_index is not None:
                            self.device_values[(device_id, field_id)] = value
            self.valid += 1

    def stale(self, now_ms: int, timeout_ms: int = 5000) -> bool:
        return self.last_frame_ms is None or now_ms - self.last_frame_ms > timeout_ms

    def stale_for_device(self, device_id: int, now_ms: int, timeout_ms: int = 5000) -> bool:
        last = self.last_frame_ms_by_device.get(device_id)
        return last is None or now_ms - last > timeout_ms


def test_valid_snapshot() -> None:
    rx = Receiver()
    rx.feed(encode_snapshot(1))
    assert rx.valid == 1


def test_partial_frame() -> None:
    rx = Receiver()
    frame = encode_snapshot(1)
    rx.feed(frame[:7])
    rx.feed(frame[7:20])
    rx.feed(frame[20:])
    assert rx.valid == 1


def test_noise_before_magic() -> None:
    rx = Receiver()
    rx.feed(b"\x00noise" + encode_snapshot(1))
    assert rx.valid == 1


def test_bad_crc() -> None:
    rx = Receiver()
    frame = bytearray(encode_snapshot(1))
    frame[-1] ^= 0x01
    rx.feed(bytes(frame))
    assert rx.valid == 0
    assert rx.crc_errors == 1


def test_unsupported_version() -> None:
    rx = Receiver()
    rx.feed(encode_snapshot(1, version=99))
    assert rx.valid == 0
    assert rx.decode_errors == 1


def test_back_to_back_frames() -> None:
    rx = Receiver()
    rx.feed(encode_snapshot(1) + encode_snapshot(2))
    assert rx.valid == 2
    assert rx.sequence_gaps == 0


def test_duplicate_sequence() -> None:
    rx = Receiver()
    rx.feed(encode_snapshot(7) + encode_snapshot(7))
    assert rx.duplicates == 1


def test_sequence_gap() -> None:
    rx = Receiver()
    rx.feed(encode_snapshot(7) + encode_snapshot(9))
    assert rx.sequence_gaps == 1


def test_sequence_wraparound() -> None:
    rx = Receiver()
    rx.feed(encode_snapshot(0xFFFF) + encode_snapshot(0))
    assert rx.valid == 2
    assert rx.sequence_gaps == 0


def test_stale_timeout() -> None:
    rx = Receiver()
    rx.feed(encode_snapshot(1), now_ms=1000)
    assert not rx.stale(5999)
    assert rx.stale(7001)


def test_recovery_after_corruption() -> None:
    rx = Receiver()
    bad = bytearray(encode_snapshot(1))
    bad[-2] ^= 0x40
    rx.feed(bytes(bad) + encode_snapshot(2))
    assert rx.crc_errors == 1
    assert rx.valid == 1


def test_v2_valid_fast_fields() -> None:
    rx = Receiver()
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 2276), (FIELD_BATTERY_SOC, 1000)]))
    assert rx.valid == 1
    assert rx.values[FIELD_PV1_POWER] == 2276
    assert rx.values[FIELD_BATTERY_SOC] == 1000


def test_v1_v2_independent_sequences() -> None:
    rx = Receiver()
    rx.feed(encode_snapshot(0) + encode_v2(0, [(FIELD_PV1_POWER, 1)]))
    assert rx.valid == 2
    assert rx.sequence_gaps == 0


def test_unknown_v2_field_ignored() -> None:
    rx = Receiver()
    rx.feed(encode_v2(0, [(9999, 123), (FIELD_PV1_POWER, 456)]))
    assert rx.valid == 1
    assert 9999 not in rx.values
    assert rx.values[FIELD_PV1_POWER] == 456


def test_diagnostics_fields_decoded() -> None:
    # Confirms the DIAGNOSTICS message type/group decodes exactly like the
    # other v2 groups and field values arrive unchanged (raw wire scale).
    rx = Receiver()
    rx.feed(
        encode_v2(
            0,
            [
                (FIELD_BATTERY_CAPACITY, 142),
                (FIELD_BMS_MAX_CELL_TEMPERATURE, 253),
                (FIELD_POWER_TO_GRID, 0),
                (FIELD_POWER_FROM_GRID, 32),
                (FIELD_GRID_FLOW, 32),
            ],
            msg_type=TYPE_DIAGNOSTICS,
        )
    )
    assert rx.valid == 1
    assert rx.values[FIELD_BATTERY_CAPACITY] == 142
    assert rx.values[FIELD_BMS_MAX_CELL_TEMPERATURE] == 253
    assert rx.values[FIELD_POWER_TO_GRID] == 0
    assert rx.values[FIELD_POWER_FROM_GRID] == 32
    assert rx.values[FIELD_GRID_FLOW] == 32


def test_controller_system_device_id_3_is_accepted() -> None:
    rx = Receiver()
    rx.feed(encode_v2(1, [(FIELD_SYSTEM_OUTPUT_POWER, 5000)], device_id=DEVICE_CONTROLLER_SYSTEM))
    assert rx.valid == 1
    assert rx.system_values[FIELD_SYSTEM_OUTPUT_POWER] == 5000
    assert (DEVICE_CONTROLLER_SYSTEM, FIELD_SYSTEM_OUTPUT_POWER) not in rx.device_values


def test_controller_display_enabled_on_off_reaches_system_state() -> None:
    rx = Receiver()
    rx.feed(encode_v2(1, [(FIELD_DISPLAY_ENABLED, 1)], device_id=DEVICE_CONTROLLER_SYSTEM), now_ms=1000)
    assert rx.system_values[FIELD_DISPLAY_ENABLED] == 1
    rx.feed(encode_v2(2, [(FIELD_DISPLAY_ENABLED, 0)], device_id=DEVICE_CONTROLLER_SYSTEM), now_ms=2000)
    assert rx.system_values[FIELD_DISPLAY_ENABLED] == 0


def test_controller_loss_does_not_force_display_enabled_off() -> None:
    rx = Receiver()
    rx.feed(encode_v2(1, [(FIELD_DISPLAY_ENABLED, 0)], device_id=DEVICE_CONTROLLER_SYSTEM), now_ms=1000)
    assert rx.system_values[FIELD_DISPLAY_ENABLED] == 0
    assert rx.stale(now_ms=7001)
    assert rx.system_values[FIELD_DISPLAY_ENABLED] == 0


def test_all_stage39b_system_fields_decode() -> None:
    rx = Receiver()
    values = [(field_id, 1000 + index) for index, field_id in enumerate(SYSTEM_FIELDS)]
    rx.feed(encode_v2(1, values, device_id=DEVICE_CONTROLLER_SYSTEM))
    assert rx.valid == 1
    assert rx.system_values == dict(values)


def test_controller_invalid_value_blanks_only_that_system_field() -> None:
    rx = Receiver()
    rx.feed(
        encode_v2(
            1,
            [
                (FIELD_SYSTEM_OUTPUT_POWER, INVALID_I32),
                (FIELD_GRID_INPUT_POWER, 2500),
                (FIELD_GRID_RAW_VOLTAGE, 2634),
            ],
            device_id=DEVICE_CONTROLLER_SYSTEM,
        )
    )
    assert rx.system_values[FIELD_SYSTEM_OUTPUT_POWER] is None
    assert rx.system_values[FIELD_GRID_INPUT_POWER] == 2500
    assert rx.system_values[FIELD_GRID_RAW_VOLTAGE] == 2634


def test_diagnostics_independent_stream_from_fast() -> None:
    # DIAGNOSTICS frames must not be mistaken for FAST_TELEMETRY sequence
    # continuity -- distinct (version, message_type) stream.
    rx = Receiver()
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 1)], msg_type=TYPE_FAST))
    rx.feed(encode_v2(0, [(FIELD_POWER_TO_GRID, 5)], msg_type=TYPE_DIAGNOSTICS))
    assert rx.valid == 2
    assert rx.sequence_gaps == 0


def test_multi_batch_first_middle_last_all_update() -> None:
    # Stage 30.1: the real Gateway shares one global sequence counter across
    # all v2 message types, so the DIAGNOSTICS stream's 4 rotating extended-
    # diagnostics batches arrive with non-consecutive sequence numbers (other
    # message types' sends increment the counter in between). None of the 3
    # target positions (first/middle/last of the 79-field rotation) may be
    # lost or rejected as a duplicate because of this.
    rx = Receiver()
    rx.feed(encode_v2(10, [(FIELD_PV1_VOLTAGE, 2314)], msg_type=TYPE_DIAGNOSTICS))
    rx.feed(encode_v2(23, [(FIELD_ENERGY_TO_GRID_TOTAL, 5678)], msg_type=TYPE_DIAGNOSTICS))
    rx.feed(encode_v2(30, [(FIELD_GENERATOR_ENERGY_TODAY, 91)], msg_type=TYPE_DIAGNOSTICS))
    assert rx.valid == 3
    assert rx.duplicates == 0
    assert rx.crc_errors == 0
    assert rx.decode_errors == 0
    assert rx.values[FIELD_PV1_VOLTAGE] == 2314
    assert rx.values[FIELD_ENERGY_TO_GRID_TOTAL] == 5678
    assert rx.values[FIELD_GENERATOR_ENERGY_TODAY] == 91


def test_unavailable_field_never_appears_before_first_receipt() -> None:
    # Stage 31 section 14: a field that has never been received must not
    # appear in rx.values at all (unavailable), never a synthetic zero.
    rx = Receiver()
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 100)], msg_type=TYPE_FAST))
    assert FIELD_PV1_POWER in rx.values
    assert FIELD_BATTERY_SOC not in rx.values  # never sent -> stays absent, not 0


def test_real_zero_publishes_as_zero_after_actual_receipt() -> None:
    # Stage 31 section 14: once a field IS received with value 0 (a real
    # zero reading, e.g. PV1 Power at night), it must be distinguishable
    # from "never received" -- present in rx.values with value exactly 0.
    rx = Receiver()
    assert FIELD_PV1_POWER not in rx.values
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 0)], msg_type=TYPE_FAST))
    assert FIELD_PV1_POWER in rx.values
    assert rx.values[FIELD_PV1_POWER] == 0


def test_same_field_id_two_devices_publish_independently() -> None:
    # Stage 32 core requirement: device 1 and device 2 sending the same
    # FieldId must never overwrite each other.
    rx = Receiver()
    rx.feed(encode_v2(1, [(FIELD_PV1_POWER, 100)], msg_type=TYPE_FAST, device_id=1))
    rx.feed(encode_v2(1, [(FIELD_PV1_POWER, 250)], msg_type=TYPE_FAST, device_id=2))
    assert rx.device_values[(1, FIELD_PV1_POWER)] == 100
    assert rx.device_values[(2, FIELD_PV1_POWER)] == 250


def test_interleaved_two_device_decoding() -> None:
    rx = Receiver()
    rx.feed(encode_v2(1, [(FIELD_PV1_POWER, 10)], msg_type=TYPE_FAST, device_id=1))
    rx.feed(encode_v2(1, [(FIELD_PV1_POWER, 20)], msg_type=TYPE_FAST, device_id=2))
    rx.feed(encode_v2(2, [(FIELD_BATTERY_SOC, 500)], msg_type=TYPE_FAST, device_id=1))
    rx.feed(encode_v2(2, [(FIELD_BATTERY_SOC, 600)], msg_type=TYPE_FAST, device_id=2))
    assert rx.valid == 4
    assert rx.sequence_gaps == 0  # independent per-device streams, no false gaps
    assert rx.device_values[(1, FIELD_PV1_POWER)] == 10
    assert rx.device_values[(2, FIELD_PV1_POWER)] == 20
    assert rx.device_values[(1, FIELD_BATTERY_SOC)] == 500
    assert rx.device_values[(2, FIELD_BATTERY_SOC)] == 600


def test_independent_sequence_state_real_gap_one_device() -> None:
    rx = Receiver()
    rx.feed(encode_v2(1, [(FIELD_PV1_POWER, 1)], msg_type=TYPE_FAST, device_id=1))
    rx.feed(encode_v2(1, [(FIELD_PV1_POWER, 1)], msg_type=TYPE_FAST, device_id=2))
    rx.feed(encode_v2(5, [(FIELD_PV1_POWER, 2)], msg_type=TYPE_FAST, device_id=1))  # gap: skipped 2,3,4
    rx.feed(encode_v2(2, [(FIELD_PV1_POWER, 2)], msg_type=TYPE_FAST, device_id=2))  # no gap
    assert rx.sequence_gaps == 1


def test_independent_unavailable_and_zero_per_device() -> None:
    rx = Receiver()
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 0)], msg_type=TYPE_FAST, device_id=1))
    assert (1, FIELD_PV1_POWER) in rx.device_values
    assert rx.device_values[(1, FIELD_PV1_POWER)] == 0  # real zero, device 1
    assert (2, FIELD_PV1_POWER) not in rx.device_values  # device 2 never sent -> unavailable


def test_independent_stale_state_per_device() -> None:
    rx = Receiver()
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 1)], msg_type=TYPE_FAST, device_id=1), now_ms=1000)
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 1)], msg_type=TYPE_FAST, device_id=2), now_ms=1000)
    assert not rx.stale_for_device(1, now_ms=1000)
    assert not rx.stale_for_device(2, now_ms=1000)

    # Device 2 stops transmitting; device 1 keeps going -- power-cycling one
    # Gateway must not affect the other's freshness (section 11).
    rx.feed(encode_v2(1, [(FIELD_PV1_POWER, 2)], msg_type=TYPE_FAST, device_id=1), now_ms=4000)
    assert not rx.stale_for_device(1, now_ms=8000)
    assert rx.stale_for_device(2, now_ms=8000)

    rx.feed(encode_v2(1, [(FIELD_PV1_POWER, 2)], msg_type=TYPE_FAST, device_id=2), now_ms=8100)
    assert not rx.stale_for_device(2, now_ms=8100)


def test_unrecognized_device_id_not_recorded() -> None:
    # device_id 0 (reserved aggregate, not yet supported) and any other
    # unrecognized id must not silently create a third device slot.
    rx = Receiver()
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 999)], msg_type=TYPE_FAST, device_id=0))
    assert rx.valid == 1  # frame itself still decodes fine
    assert (0, FIELD_PV1_POWER) not in rx.device_values
    assert all(device_id in (1, 2) for device_id, _field_id in rx.device_values)


def connection_status(have_snapshot: bool, data_fresh: bool) -> str:
    # Mirrors DisplayProtocolUARTComponent::update_connection_status_
    # (Stage 33) exactly -- purely derived from have_snapshot_/data_fresh_,
    # no separate timeout mechanism.
    if not have_snapshot:
        return "DISCONNECTED"
    if data_fresh:
        return "CONNECTED"
    return "STALE"


def test_connection_status_disconnected_before_first_frame() -> None:
    assert connection_status(have_snapshot=False, data_fresh=False) == "DISCONNECTED"


def test_connection_status_connected_when_fresh() -> None:
    assert connection_status(have_snapshot=True, data_fresh=True) == "CONNECTED"


def test_connection_status_stale_when_timed_out() -> None:
    assert connection_status(have_snapshot=True, data_fresh=False) == "STALE"


def test_connection_status_independent_per_device_via_receiver_state() -> None:
    # End-to-end through the Receiver mirror: device 1 gets a frame (would
    # be CONNECTED), device 2 never does (would stay DISCONNECTED) -- same
    # have_snapshot_/data_fresh_ inputs the real component derives from.
    rx = Receiver()
    rx.feed(encode_v2(0, [(FIELD_PV1_POWER, 1)], msg_type=TYPE_FAST, device_id=1), now_ms=1000)
    device1_has_snapshot = (1, FIELD_PV1_POWER) in rx.device_values
    device2_has_snapshot = (2, FIELD_PV1_POWER) in rx.device_values
    assert connection_status(device1_has_snapshot, not rx.stale_for_device(1, now_ms=1000)) == "CONNECTED"
    assert connection_status(device2_has_snapshot, not rx.stale_for_device(2, now_ms=1000)) == "DISCONNECTED"


def test_display_status_transmitter_uses_display_device_id_and_real_field() -> None:
    source = (REPO_ROOT / "components" / "display_protocol_uart" / "display_protocol_uart.cpp").read_text(
        encoding="utf-8"
    )
    assert "status.deviceId = ESPTelemetry::kDeviceIdDisplay" in source
    assert "FieldIdDisplayMaintenanceWifiActual" in source
    assert "encodeTelemetry(status, ESPTelemetry::kMessageTypeStatus" in source
    assert "send_raw_frame(frame, frame_length)" in source


def main() -> int:
    tests = [
        test_valid_snapshot,
        test_partial_frame,
        test_noise_before_magic,
        test_bad_crc,
        test_unsupported_version,
        test_back_to_back_frames,
        test_duplicate_sequence,
        test_sequence_gap,
        test_sequence_wraparound,
        test_stale_timeout,
        test_recovery_after_corruption,
        test_v2_valid_fast_fields,
        test_v1_v2_independent_sequences,
        test_unknown_v2_field_ignored,
        test_diagnostics_fields_decoded,
        test_diagnostics_independent_stream_from_fast,
        test_controller_system_device_id_3_is_accepted,
        test_controller_display_enabled_on_off_reaches_system_state,
        test_controller_loss_does_not_force_display_enabled_off,
        test_all_stage39b_system_fields_decode,
        test_controller_invalid_value_blanks_only_that_system_field,
        test_multi_batch_first_middle_last_all_update,
        test_unavailable_field_never_appears_before_first_receipt,
        test_real_zero_publishes_as_zero_after_actual_receipt,
        test_same_field_id_two_devices_publish_independently,
        test_interleaved_two_device_decoding,
        test_independent_sequence_state_real_gap_one_device,
        test_independent_unavailable_and_zero_per_device,
        test_independent_stale_state_per_device,
        test_unrecognized_device_id_not_recorded,
        test_connection_status_disconnected_before_first_frame,
        test_connection_status_connected_when_fresh,
        test_connection_status_stale_when_timed_out,
        test_connection_status_independent_per_device_via_receiver_state,
        test_display_status_transmitter_uses_display_device_id_and_real_field,
    ]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
    print(f"{len(tests)} display UART receiver tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
