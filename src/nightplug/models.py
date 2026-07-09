"""Core data types for samples, states, and night summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SleepState(str, Enum):
    EMPTY = "empty"
    IN_BED = "in_bed"
    SLEEP_LIKE = "sleep_like"
    RESTLESS = "restless"
    AWAKE_IN_BED = "awake_in_bed"
    UP = "up"


@dataclass
class Sample:
    """One time-step of bedside sensing (sim or ESP32)."""

    ts: str  # ISO-8601
    presence: float  # 0–1
    motion: float  # 0–1
    breathing_bpm: float
    signal_quality: float  # 0–1
    source: str = "sim"  # sim | esp32 | ruview
    state: str | None = None  # filled by session engine when processing

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Sample:
        return cls(
            ts=str(d["ts"]),
            presence=float(d["presence"]),
            motion=float(d["motion"]),
            breathing_bpm=float(d["breathing_bpm"]),
            signal_quality=float(d.get("signal_quality", 1.0)),
            source=str(d.get("source", "sim")),
            state=d.get("state"),
        )


@dataclass
class ApneaCandidate:
    start_ts: str
    end_ts: str
    duration_secs: int
    note: str = "Heuristic breathing dip — not a medical finding"


@dataclass
class NightSummary:
    night_id: str
    source: str
    sample_count: int
    started_at: str
    ended_at: str
    time_in_bed_secs: int
    sleep_like_secs: int
    restless_secs: int
    awake_in_bed_secs: int
    avg_breathing_bpm: float
    min_breathing_bpm: float
    max_breathing_bpm: float
    apnea_like_events: int
    apnea_candidates: list[ApneaCandidate] = field(default_factory=list)
    state_timeline: list[dict[str, Any]] = field(default_factory=list)
    score: int = 0
    score_reasons: list[str] = field(default_factory=list)
    disclaimer: str = (
        "NightPlug is a personal wellness tool, not a medical device. "
        "It does not diagnose sleep apnea or any condition."
    )

    @property
    def time_in_bed_hours(self) -> float:
        return self.time_in_bed_secs / 3600.0

    @property
    def sleep_like_hours(self) -> float:
        return self.sleep_like_secs / 3600.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
