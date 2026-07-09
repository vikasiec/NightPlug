"""Synthetic overnight generator for development before ESP32 arrives."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from nightplug.models import Sample


PROFILES = ("normal", "restless", "short", "apnea_prone")


def simulate_night(
    hours: float = 8.0,
    seed: int = 42,
    profile: str = "normal",
    start: datetime | None = None,
    source: str = "sim",
) -> list[Sample]:
    """
    Generate 1 Hz samples for a synthetic night.

    Profiles:
      normal      — mostly quiet sleep, light restlessness
      restless    — more motion / wake-ups
      short       — ~5.5 h effective night
      apnea_prone — inject breathing dips during sleep-like stretches
    """
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile {profile!r}; choose from {PROFILES}")

    rng = random.Random(seed)
    if start is None:
        # Default: last night 23:00 local
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=1) + timedelta(hours=23)

    total = int(hours * 3600)
    samples: list[Sample] = []

    # Phase boundaries as fractions of night
    if profile == "short":
        total = int(5.5 * 3600)
        hours = 5.5

    settle = int(0.05 * total)  # getting into bed
    deep_end = int(0.75 * total)
    morning = int(0.92 * total)

    base_br = 14.0 + rng.uniform(-1.0, 1.0)

    for i in range(total):
        t = start + timedelta(seconds=i)
        frac = i / max(total, 1)

        # Default: in bed, quiet
        presence = 0.85 + rng.uniform(-0.05, 0.08)
        motion = 0.04 + abs(rng.gauss(0, 0.02))
        br = base_br + 0.8 * math.sin(i / 400.0) + rng.gauss(0, 0.3)
        quality = 0.9

        # Pre-bed empty
        if i < settle:
            presence = 0.1 + rng.random() * 0.15
            motion = 0.05 + rng.random() * 0.1
            br = 12 + rng.random() * 4

        # Settling / reading in bed
        elif i < settle + 600:
            presence = 0.8
            motion = 0.2 + rng.random() * 0.25
            br = 15 + rng.random() * 2

        # Core night
        elif i < deep_end:
            # Circadian-ish quiet with occasional rolls
            if profile == "restless":
                if rng.random() < 0.04:
                    motion = 0.4 + rng.random() * 0.4
                    br = 16 + rng.random() * 3
                else:
                    motion = 0.08 + abs(rng.gauss(0, 0.04))
            else:
                if rng.random() < 0.008:
                    motion = 0.35 + rng.random() * 0.3
                else:
                    motion = 0.03 + abs(rng.gauss(0, 0.015))

            # Apnea-like dips (fixed period so they actually land)
            if profile == "apnea_prone" and 0.2 < frac < 0.75:
                cycle = i % 900  # every 15 minutes
                if cycle < 20:  # ~20 s dip
                    br = base_br * 0.25 + rng.uniform(0, 0.5)
                    motion = 0.02
                    presence = 0.9

        # Early morning lighter sleep
        elif i < morning:
            motion = 0.1 + abs(rng.gauss(0, 0.05))
            if rng.random() < 0.02:
                motion = 0.45
            br = base_br + 1.5 + rng.gauss(0, 0.4)

        # Wake and leave
        else:
            if i < morning + 400:
                presence = 0.85
                motion = 0.4 + rng.random() * 0.35
                br = 16 + rng.random() * 3
            else:
                presence = 0.1 + rng.random() * 0.1
                motion = 0.08
                br = 14

        presence = max(0.0, min(1.0, presence))
        motion = max(0.0, min(1.0, motion))
        br = max(3.0, min(35.0, br))

        samples.append(
            Sample(
                ts=t.isoformat(timespec="seconds"),
                presence=round(presence, 4),
                motion=round(motion, 4),
                breathing_bpm=round(br, 2),
                signal_quality=round(quality, 3),
                source=source,
            )
        )

    return samples
