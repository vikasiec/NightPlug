"""Live ingest from a RuView esp32-csi-node board over UDP.

The board's default upstream payload (ADR-081, magic 0xC5110006,
`rv_feature_state_t`, 60 bytes) is parsed into a NightPlug Sample. The
older ADR-039 vitals packet (magic 0xC5110002, 32 bytes) is also accepted
as a fallback for firmware builds that still emit it. Raw ADR-018 CSI
frames (magic 0xC5110001) are received but skipped — not needed for the
1 Hz sample rate NightPlug's session engine expects.
"""

from __future__ import annotations

import socket
import struct
import time
from collections.abc import Iterator
from datetime import datetime, timezone

from nightplug.models import Sample

CSI_MAGIC = 0xC5110001
VITALS_MAGIC = 0xC5110002
FEATURE_STATE_MAGIC = 0xC5110006

# ADR-039 vitals packet (32 bytes) — legacy fallback.
VITALS_STRUCT = struct.Struct("<IBBHIbBHffII")

# ADR-081 rv_feature_state_t (60 bytes, packed) — current default stream.
# magic, node_id, mode, seq, ts_us, motion_score, presence_score,
# respiration_bpm, respiration_conf, heartbeat_bpm, heartbeat_conf,
# anomaly_score, env_shift_score, node_coherence, quality_flags, reserved, crc32
FEATURE_STATE_STRUCT = struct.Struct("<IBBHQfffffffffHHI")

QFLAG_RESPIRATION_VALID = 1 << 1
QFLAG_DEGRADED_MODE = 1 << 5
QFLAG_CALIBRATING = 1 << 6

DEFAULT_PORT = 5005


def _rssi_to_quality(rssi_dbm: int) -> float:
    """Map RSSI (~-90..-30 dBm) to a 0-1 signal quality score."""
    return max(0.0, min(1.0, (rssi_dbm + 90) / 60))


def parse_feature_state_packet(data: bytes, ts_override: str | None = None) -> Sample | None:
    """Parse a 60-byte ADR-081 rv_feature_state_t into a Sample, or None if not this type.

    By default stamps the Sample with the receipt time (correct for the
    live UDP path, where receipt is contemporaneous with sensing). Pass
    ts_override (an ISO-8601 string) when parsing a record pulled from the
    ESP32's local flash buffer (see sync.py) — those records carry their
    own real sensing-time timestamp, which must be used instead of "now"
    or backfilled data would be silently misdated to whenever it happened
    to sync.
    """
    if len(data) < FEATURE_STATE_STRUCT.size:
        return None
    (
        magic,
        _node_id,
        _mode,
        _seq,
        _ts_us,
        motion_score,
        presence_score,
        respiration_bpm,
        respiration_conf,
        _heartbeat_bpm,
        _heartbeat_conf,
        _anomaly_score,
        _env_shift_score,
        _node_coherence,
        quality_flags,
        _reserved,
        _crc32,
    ) = FEATURE_STATE_STRUCT.unpack_from(data, 0)

    if magic != FEATURE_STATE_MAGIC:
        return None

    quality = respiration_conf if quality_flags & QFLAG_RESPIRATION_VALID else 0.5
    if quality_flags & (QFLAG_DEGRADED_MODE | QFLAG_CALIBRATING):
        quality *= 0.5

    return Sample(
        ts=ts_override or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        presence=max(0.0, min(1.0, presence_score)),
        motion=max(0.0, min(1.0, motion_score)),
        breathing_bpm=respiration_bpm,
        signal_quality=max(0.0, min(1.0, quality)),
        source="esp32",
    )


def parse_vitals_packet(data: bytes) -> Sample | None:
    """Parse a 32-byte ADR-039 vitals packet into a Sample, or None if not vitals."""
    if len(data) < VITALS_STRUCT.size:
        return None
    (
        magic,
        _node_id,
        flags,
        breathing_fp,
        _heart_fp,
        rssi,
        _n_persons,
        _reserved1,
        motion_energy,
        presence_score,
        _timestamp_ms,
        _reserved2,
    ) = VITALS_STRUCT.unpack_from(data, 0)

    if magic != VITALS_MAGIC:
        return None

    presence_flag = bool(flags & 0x01)
    presence = max(presence_score, 1.0 if presence_flag else 0.0)
    presence = max(0.0, min(1.0, presence))
    motion = max(0.0, min(1.0, motion_energy))
    breathing_bpm = breathing_fp / 100.0

    return Sample(
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        presence=presence,
        motion=motion,
        breathing_bpm=breathing_bpm,
        signal_quality=_rssi_to_quality(rssi),
        source="esp32",
    )


def parse_packet(data: bytes) -> Sample | None:
    """Parse whichever known packet type this datagram is, or None."""
    if len(data) < 4:
        return None
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic == FEATURE_STATE_MAGIC:
        return parse_feature_state_packet(data)
    if magic == VITALS_MAGIC:
        return parse_vitals_packet(data)
    return None


def listen(
    host: str = "0.0.0.0",
    port: int = DEFAULT_PORT,
    duration_secs: float | None = None,
    socket_timeout: float = 2.0,
) -> Iterator[Sample]:
    """Yield Samples parsed from incoming vitals packets until duration_secs elapses.

    duration_secs=None runs until interrupted (Ctrl+C).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    sock.settimeout(socket_timeout)
    start = time.monotonic()
    try:
        while duration_secs is None or (time.monotonic() - start) < duration_secs:
            try:
                data, _addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            sample = parse_packet(data)
            if sample is not None:
                yield sample
    finally:
        sock.close()
