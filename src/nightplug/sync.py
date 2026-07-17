"""Pull buffered samples from an ESP32 board's local HTTP API.

The board (see `sample_buffer.c` in the sibling RuView firmware repo)
persists sensing output to its own flash even when nothing is listening
on the live UDP stream (`nightplug live`). This module recovers that
backlog over HTTP whenever the PC does come back online, so a PC that
isn't on 24/7 doesn't silently lose whole nights.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from nightplug.config import DATA_DIR, ensure_dirs
from nightplug.ingest import QFLAG_CALIBRATING, QFLAG_DEGRADED_MODE, QFLAG_RESPIRATION_VALID
from nightplug.logger import append_samples
from nightplug.models import Sample

# Matches OTA_PORT in RuView firmware/esp32-csi-node/main/ota_update.c —
# the local buffer's HTTP endpoints are registered on that same server.
DEFAULT_HTTP_PORT = 8032

# Must not exceed PULL_MAX_LIMIT in sample_buffer.c's data_pull_handler.
PULL_LIMIT = 200


def _sync_state_path() -> Path:
    ensure_dirs()
    return DATA_DIR / ".sync_state.json"


def _load_cursor(host: str) -> int:
    path = _sync_state_path()
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    return int(data.get(host, 0))


def _save_cursor(host: str, cursor: int) -> None:
    path = _sync_state_path()
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data[host] = cursor
    path.write_text(json.dumps(data), encoding="utf-8")


def _fetch_json(url: str, timeout: float = 10.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (LAN-local device, user-supplied host)
        return json.loads(resp.read().decode("utf-8"))


def _record_to_sample(rec: dict) -> Sample:
    """Mirror ingest.parse_feature_state_packet's field mapping, but from
    the JSON the buffer's /data/pull endpoint returns rather than the raw
    60-byte struct — the device does that unpacking on its own side.
    """
    quality_flags = int(rec.get("quality_flags", 0))
    respiration_conf = float(rec.get("respiration_conf", 0.0))
    quality = respiration_conf if quality_flags & QFLAG_RESPIRATION_VALID else 0.5
    if quality_flags & (QFLAG_DEGRADED_MODE | QFLAG_CALIBRATING):
        quality *= 0.5

    ts = datetime.fromtimestamp(int(rec["ts"]), tz=timezone.utc).isoformat(timespec="seconds")
    return Sample(
        ts=ts,
        presence=max(0.0, min(1.0, float(rec.get("presence", 0.0)))),
        motion=max(0.0, min(1.0, float(rec.get("motion", 0.0)))),
        breathing_bpm=float(rec.get("respiration_bpm", 0.0)),
        signal_quality=max(0.0, min(1.0, quality)),
        source="esp32",
    )


class SyncError(RuntimeError):
    """Raised when the device can't be reached or returns something unexpected."""


def sync(host: str, port: int = DEFAULT_HTTP_PORT) -> dict[str, int]:
    """Pull everything buffered since the last sync for `host`, merge it
    into the right per-night JSONL file(s) (bucketed by each record's own
    UTC date — a sync after several days can span multiple nights), and
    advance the saved cursor.

    Returns {night_id: samples_added} for nights that got new data.
    """
    base = f"http://{host}:{port}"
    try:
        status = _fetch_json(f"{base}/data/status")
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        raise SyncError(f"Could not reach {base}/data/status: {e}") from e

    if status.get("record_count", 0) == 0:
        return {}

    cursor = _load_cursor(host)
    since = cursor
    new_samples: list[Sample] = []

    while True:
        try:
            resp = _fetch_json(f"{base}/data/pull?since={since}&limit={PULL_LIMIT}")
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            raise SyncError(f"Could not reach {base}/data/pull: {e}") from e

        records = resp.get("records", [])
        if not records:
            break
        for rec in records:
            new_samples.append(_record_to_sample(rec))
            since = max(since, int(rec["ts"]))
        if len(records) < PULL_LIMIT:
            break

    if not new_samples:
        return {}

    by_night: dict[str, list[Sample]] = {}
    for s in new_samples:
        night_id = s.ts[:10]  # ISO date prefix, e.g. "2026-07-17"
        by_night.setdefault(night_id, []).append(s)

    added: dict[str, int] = {}
    for night_id, samples in by_night.items():
        append_samples(samples, night_id=night_id)
        added[night_id] = len(samples)

    _save_cursor(host, since)
    return added
