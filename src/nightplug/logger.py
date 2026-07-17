"""JSONL night logs under data/nights/."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from nightplug.config import DATA_DIR, ensure_dirs
from nightplug.models import Sample


def night_path(night_id: str | None = None) -> Path:
    ensure_dirs()
    nid = night_id or date.today().isoformat()
    return DATA_DIR / f"{nid}.jsonl"


def write_samples(samples: list[Sample], night_id: str | None = None) -> Path:
    path = night_path(night_id)
    with path.open("w", encoding="utf-8") as f:
        meta = {
            "_type": "nightplug_meta",
            "night_id": path.stem,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "product": "NightPlug",
            "schema": "sample_v1",
        }
        f.write(json.dumps(meta) + "\n")
        for s in samples:
            f.write(json.dumps(s.to_dict()) + "\n")
    return path


def load_samples(path: Path) -> tuple[str, list[Sample]]:
    samples: list[Sample] = []
    night_id = path.stem
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("_type") == "nightplug_meta":
                night_id = d.get("night_id", night_id)
                continue
            samples.append(Sample.from_dict(d))
    return night_id, samples


def merge_dedupe_samples(existing: list[Sample], new: list[Sample]) -> list[Sample]:
    """Merge two sample lists for the same night, deduping on (ts, source)
    and sorting by ts. Used whenever a night's file might already have
    data from another source (e.g. `live` running after `sync` already
    populated the night, or vice versa) so neither overwrites the other.
    """
    seen = {(s.ts, s.source) for s in existing}
    merged = list(existing)
    for s in new:
        key = (s.ts, s.source)
        if key not in seen:
            merged.append(s)
            seen.add(key)
    merged.sort(key=lambda s: s.ts)
    return merged


def append_samples(samples: list[Sample], night_id: str | None = None) -> Path:
    """Merge `samples` into the night's existing file (if any) instead of
    overwriting it — see merge_dedupe_samples. Prefer this over
    write_samples() for any source that might run more than once per
    night (live, sync) so a second run can't silently discard the first.
    """
    path = night_path(night_id)
    existing: list[Sample] = []
    if path.exists():
        _, existing = load_samples(path)
    merged = merge_dedupe_samples(existing, samples)
    return write_samples(merged, night_id=night_id)


def list_nights() -> list[Path]:
    ensure_dirs()
    return sorted(DATA_DIR.glob("*.jsonl"))


def latest_night() -> Path | None:
    nights = list_nights()
    return nights[-1] if nights else None
