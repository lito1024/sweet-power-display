#!/usr/bin/env python3
from __future__ import annotations

import struct

MAGIC = b"SPDP"
VERSION = 1
VERSION_V2 = 2
TYPE_SNAPSHOT = 1
TYPE_FAST = 16
TYPE_ENERGY = 17
TYPE_STATUS = 18
HEADER_SIZE = 14
PAYLOAD_SIZE = 32
CRC_SIZE = 2
MAX_PAYLOAD_SIZE = 128
V2_PAYLOAD_HEADER_SIZE = 5
FIELD_PV1_POWER = 1001
MAC_GATEWAY = (0x02, 0, 0, 0, 0, 1)
MAC_UNKNOWN = (0x02, 0, 0, 0, 0, 2)


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


def encode_snapshot(sequence: int, device_id: int = 1, version: int = VERSION, payload_size: int = PAYLOAD_SIZE) -> bytes:
    payload = struct.pack("<iiHiiIH8s", 2276, 1739, 1000, 0, 0, 123456, 0x000F, bytes([device_id]) + b"\x00" * 7)
    if payload_size != PAYLOAD_SIZE:
        payload = payload[:payload_size]
    header = MAGIC + bytes([version, TYPE_SNAPSHOT]) + struct.pack("<HHI", len(payload), sequence & 0xFFFF, 1234)
    without_crc = header + payload
    return without_crc + struct.pack("<H", crc16(without_crc))


def encode_v2(sequence: int, device_id: int = 1, message_type: int = TYPE_FAST) -> bytes:
    payload = struct.pack("<BBBH", device_id, 1, 1, 0x0003) + struct.pack("<Hi", FIELD_PV1_POWER, 2276)
    header = MAGIC + bytes([VERSION_V2, message_type]) + struct.pack("<HHI", len(payload), sequence & 0xFFFF, 1234)
    without_crc = header + payload
    return without_crc + struct.pack("<H", crc16(without_crc))


class ESPNowReceiver:
    def __init__(self, stale_timeout_ms: int = 5000) -> None:
        self.trusted = {MAC_GATEWAY: 1}
        self.valid = 0
        self.unknown = 0
        self.mismatch = 0
        self.crc_errors = 0
        self.decode_errors = 0
        self.sequence_gaps = 0
        self.duplicates = 0
        # keyed by (device_id, version, message_type): the sender keeps
        # independent sequence counters per stream (v1 snapshot vs. each v2
        # message type), so continuity must be tracked per stream, not
        # globally per device_id (Stage 26.1 found guaranteed false gaps from
        # interleaved v1/v2 traffic when tracked per device_id only).
        self.last_seq: dict[tuple[int, int, int], int] = {}
        self.last_frame_ms: dict[int, int] = {}
        self.values: dict[int, int] = {}
        self.stale_timeout_ms = stale_timeout_ms

    def receive(self, mac: tuple[int, ...], frame: bytes, now_ms: int = 0) -> None:
        if mac not in self.trusted:
            self.unknown += 1
            return
        if len(frame) < HEADER_SIZE + CRC_SIZE or frame[:4] != MAGIC:
            self.decode_errors += 1
            return
        payload_len = struct.unpack_from("<H", frame, 6)[0]
        if payload_len > MAX_PAYLOAD_SIZE or len(frame) != HEADER_SIZE + payload_len + CRC_SIZE:
            self.decode_errors += 1
            return
        if struct.unpack_from("<H", frame, len(frame) - CRC_SIZE)[0] != crc16(frame[:-CRC_SIZE]):
            self.crc_errors += 1
            return

        version = frame[4]
        message_type = frame[5]
        sequence = struct.unpack_from("<H", frame, 8)[0]
        payload = frame[HEADER_SIZE:-CRC_SIZE]
        if version == VERSION:
            if payload_len != PAYLOAD_SIZE:
                self.decode_errors += 1
                return
            device_id = payload[24]
        elif version == VERSION_V2:
            if payload_len < V2_PAYLOAD_HEADER_SIZE:
                self.decode_errors += 1
                return
            device_id = payload[0]
        else:
            self.decode_errors += 1
            return

        if self.trusted[mac] != device_id:
            self.mismatch += 1
            return

        stream_key = (device_id, version, message_type)
        if stream_key in self.last_seq:
            expected = (self.last_seq[stream_key] + 1) & 0xFFFF
            if sequence == self.last_seq[stream_key]:
                self.duplicates += 1
            elif sequence != expected:
                self.sequence_gaps += 1
        self.last_seq[stream_key] = sequence
        self.last_frame_ms[device_id] = now_ms
        self.valid += 1
        if version == VERSION_V2:
            count = payload[2]
            for index in range(count):
                offset = V2_PAYLOAD_HEADER_SIZE + index * 6
                field_id, value = struct.unpack_from("<Hi", payload, offset)
                self.values[field_id] = value

    def fresh(self, device_id: int, now_ms: int) -> bool:
        return device_id in self.last_frame_ms and now_ms - self.last_frame_ms[device_id] <= self.stale_timeout_ms


def test_trusted_device_id_accepted() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_GATEWAY, encode_snapshot(1))
    assert rx.valid == 1


def test_unknown_mac_rejected() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_UNKNOWN, encode_snapshot(1))
    assert rx.valid == 0
    assert rx.unknown == 1


def test_wrong_device_id_rejected() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_GATEWAY, encode_snapshot(1, device_id=2))
    assert rx.valid == 0
    assert rx.mismatch == 1


def test_bad_crc_rejected() -> None:
    rx = ESPNowReceiver()
    frame = bytearray(encode_snapshot(1))
    frame[-1] ^= 0x01
    rx.receive(MAC_GATEWAY, bytes(frame))
    assert rx.valid == 0
    assert rx.crc_errors == 1


def test_malformed_length_rejected() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_GATEWAY, encode_snapshot(1, payload_size=4))
    assert rx.valid == 0
    assert rx.decode_errors == 1


def test_rejected_packet_does_not_update_entities() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_GATEWAY, encode_v2(1, device_id=2))
    assert FIELD_PV1_POWER not in rx.values


def test_first_valid_establishes_freshness() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_GATEWAY, encode_snapshot(1), now_ms=1000)
    assert rx.fresh(1, 5000)


def test_stale_and_restore() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_GATEWAY, encode_snapshot(1), now_ms=1000)
    assert not rx.fresh(1, 7001)
    rx.receive(MAC_GATEWAY, encode_snapshot(2), now_ms=7100)
    assert rx.fresh(1, 7100)


def test_two_peers_independent() -> None:
    rx = ESPNowReceiver()
    rx.trusted[MAC_UNKNOWN] = 2
    rx.receive(MAC_GATEWAY, encode_snapshot(1, device_id=1), now_ms=1000)
    rx.receive(MAC_UNKNOWN, encode_snapshot(1, device_id=2), now_ms=5000)
    assert not rx.fresh(1, 7001)
    assert rx.fresh(2, 7001)


# --- Stage 26.2: per-stream sequence tracking -------------------------------


def test_interleaved_v1_v2_no_false_gaps() -> None:
    rx = ESPNowReceiver()
    for seq in (1, 2, 3):
        rx.receive(MAC_GATEWAY, encode_snapshot(seq), now_ms=seq * 1000)
        rx.receive(MAC_GATEWAY, encode_v2(seq, message_type=TYPE_FAST), now_ms=seq * 1000)
    assert rx.sequence_gaps == 0
    assert rx.valid == 6


def test_interleaved_v2_groups_no_false_gaps() -> None:
    rx = ESPNowReceiver()
    for seq in (1, 2, 3):
        rx.receive(MAC_GATEWAY, encode_v2(seq, message_type=TYPE_FAST), now_ms=seq * 1000)
        rx.receive(MAC_GATEWAY, encode_v2(seq, message_type=TYPE_ENERGY), now_ms=seq * 1000)
        rx.receive(MAC_GATEWAY, encode_v2(seq, message_type=TYPE_STATUS), now_ms=seq * 1000)
    assert rx.sequence_gaps == 0
    assert rx.valid == 9


def test_real_gap_in_v1_stream_only() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_GATEWAY, encode_snapshot(1), now_ms=1000)
    rx.receive(MAC_GATEWAY, encode_v2(1, message_type=TYPE_FAST), now_ms=1000)
    rx.receive(MAC_GATEWAY, encode_snapshot(3), now_ms=2000)  # v1 skipped 2
    rx.receive(MAC_GATEWAY, encode_v2(2, message_type=TYPE_FAST), now_ms=2000)  # FAST unaffected
    assert rx.sequence_gaps == 1


def test_duplicate_in_one_stream_does_not_affect_another() -> None:
    rx = ESPNowReceiver()
    rx.receive(MAC_GATEWAY, encode_snapshot(5), now_ms=1000)
    rx.receive(MAC_GATEWAY, encode_snapshot(5), now_ms=2000)  # duplicate v1
    rx.receive(MAC_GATEWAY, encode_v2(1, message_type=TYPE_FAST), now_ms=2000)
    rx.receive(MAC_GATEWAY, encode_v2(2, message_type=TYPE_FAST), now_ms=3000)
    assert rx.duplicates == 1
    assert rx.sequence_gaps == 0


def main() -> int:
    tests = [
        test_trusted_device_id_accepted,
        test_unknown_mac_rejected,
        test_wrong_device_id_rejected,
        test_bad_crc_rejected,
        test_malformed_length_rejected,
        test_rejected_packet_does_not_update_entities,
        test_first_valid_establishes_freshness,
        test_stale_and_restore,
        test_two_peers_independent,
        test_interleaved_v1_v2_no_false_gaps,
        test_interleaved_v2_groups_no_false_gaps,
        test_real_gap_in_v1_stream_only,
        test_duplicate_in_one_stream_does_not_affect_another,
    ]
    for test in tests:
        test()
        print(f"{test.__name__}: OK")
    print(f"{len(tests)} display ESP-NOW receiver tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
