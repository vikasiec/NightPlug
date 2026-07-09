"""Paths and tunable thresholds for NightPlug."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Project root: NightPlug/
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "nights"
REPORTS_DIR = ROOT / "reports"
TEMPLATES_DIR = ROOT / "templates"

# Sample rate for personal MVP (1 Hz is enough for sleep macro-dynamics)
SAMPLE_HZ = 1.0

# Hardware note (arriving ~2026-07-22)
ESP32_ETA = "2026-07-22"
ESP32_NOTE = "ESP32-S3 N16R8 ordered — wire CSI after arrival"


@dataclass(frozen=True)
class Thresholds:
    """Rule-based thresholds — tune against your room after hardware arrives."""

    # Motion energy (0–1 normalized)
    motion_sleep_max: float = 0.12
    motion_restless_min: float = 0.18
    motion_awake_min: float = 0.35

    # Breathing rate (breaths per minute)
    br_sleep_min: float = 8.0
    br_sleep_max: float = 22.0

    # Presence confidence 0–1
    presence_in_bed: float = 0.55
    presence_empty: float = 0.35

    # State machine dwell (seconds)
    enter_bed_secs: int = 90
    sleep_onset_secs: int = 300
    wake_confirm_secs: int = 120
    leave_bed_secs: int = 180

    # Apnea-like candidate (heuristic only)
    br_drop_ratio: float = 0.45
    apnea_min_gap_secs: int = 12
    apnea_merge_secs: int = 30


DEFAULT_THRESHOLDS = Thresholds()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
