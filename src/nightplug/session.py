"""Sleep session state machine."""

from __future__ import annotations

from dataclasses import dataclass, field

from nightplug.config import DEFAULT_THRESHOLDS, Thresholds
from nightplug.models import ApneaCandidate, NightSummary, Sample, SleepState, parse_ts


@dataclass
class SessionEngine:
    """Tracks bed presence and coarse sleep-like states over a night."""

    thresholds: Thresholds = field(default_factory=lambda: DEFAULT_THRESHOLDS)
    state: SleepState = SleepState.EMPTY
    _class_dwell: int = 0
    _prev_class: SleepState = SleepState.EMPTY
    _present_dwell: int = 0
    _absent_dwell: int = 0
    _timeline: list[dict] = field(default_factory=list)
    _seg_start_ts: str | None = None
    _counts: dict[str, int] = field(default_factory=dict)
    _br_values: list[float] = field(default_factory=list)
    _apnea_open: str | None = None
    _apnea_len: int = 0
    _apnea_candidates: list[ApneaCandidate] = field(default_factory=list)
    _samples: int = 0
    _first_ts: str | None = None
    _last_ts: str | None = None
    _source: str = "sim"
    _br_baseline: float | None = None

    def __post_init__(self) -> None:
        for s in SleepState:
            self._counts[s.value] = 0

    def _instant_class(self, sample: Sample) -> SleepState:
        """Classify this second (not yet dwell-committed)."""
        t = self.thresholds
        p, m, br = sample.presence, sample.motion, sample.breathing_bpm

        if p < t.presence_empty:
            return SleepState.EMPTY

        if m >= t.motion_awake_min:
            return SleepState.AWAKE_IN_BED
        if m >= t.motion_restless_min:
            return SleepState.RESTLESS
        if m <= t.motion_sleep_max and t.br_sleep_min <= br <= t.br_sleep_max:
            return SleepState.SLEEP_LIKE
        return SleepState.IN_BED

    def _set_state(self, new: SleepState, ts: str) -> None:
        if new == self.state:
            return
        if self._seg_start_ts is not None:
            self._timeline.append(
                {
                    "state": self.state.value,
                    "start": self._seg_start_ts,
                    "end": ts,
                }
            )
        self.state = new
        self._seg_start_ts = ts

    def process(self, sample: Sample) -> SleepState:
        """Ingest one sample; return committed state after dwell rules."""
        self._samples += 1
        self._source = sample.source
        if self._first_ts is None:
            self._first_ts = sample.ts
            self._seg_start_ts = sample.ts
        self._last_ts = sample.ts

        present = sample.presence >= self.thresholds.presence_in_bed
        weak_present = sample.presence >= self.thresholds.presence_empty

        if present or weak_present:
            self._present_dwell += 1
            self._absent_dwell = 0
        else:
            self._absent_dwell += 1
            self._present_dwell = 0

        if present:
            self._br_values.append(sample.breathing_bpm)
            if self._br_baseline is None:
                self._br_baseline = sample.breathing_bpm
            else:
                self._br_baseline = 0.995 * self._br_baseline + 0.005 * sample.breathing_bpm

        instant = self._instant_class(sample)
        if instant == self._prev_class:
            self._class_dwell += 1
        else:
            self._prev_class = instant
            self._class_dwell = 1

        t = self.thresholds
        committed = self.state

        # --- Presence gates (stable even when motion class flickers) ---
        if self.state in (SleepState.EMPTY, SleepState.UP):
            if self._present_dwell >= 45:
                # Enter bed with best current class
                committed = instant if instant != SleepState.EMPTY else SleepState.IN_BED
        elif self.state != SleepState.UP:
            if self._absent_dwell >= t.leave_bed_secs:
                committed = SleepState.UP
            else:
                # Motion class changes while still present
                if instant == SleepState.SLEEP_LIKE and self._class_dwell >= 90:
                    committed = SleepState.SLEEP_LIKE
                elif instant == SleepState.RESTLESS and self._class_dwell >= 20:
                    committed = SleepState.RESTLESS
                elif instant == SleepState.AWAKE_IN_BED and self._class_dwell >= 45:
                    committed = SleepState.AWAKE_IN_BED
                elif instant == SleepState.IN_BED and self._class_dwell >= 30:
                    committed = SleepState.IN_BED
                elif instant == SleepState.EMPTY and self._absent_dwell >= 60:
                    committed = SleepState.UP

        self._set_state(committed, sample.ts)
        self._counts[self.state.value] = self._counts.get(self.state.value, 0) + 1
        sample.state = self.state.value
        self._track_apnea(sample)
        return self.state

    def _track_apnea(self, sample: Sample) -> None:
        t = self.thresholds
        if self.state not in (
            SleepState.SLEEP_LIKE,
            SleepState.RESTLESS,
            SleepState.IN_BED,
        ):
            self._close_apnea(sample.ts)
            return
        if self._br_baseline is None or self._br_baseline < 1:
            return
        dip = sample.breathing_bpm < self._br_baseline * t.br_drop_ratio
        low_motion = sample.motion < t.motion_restless_min
        if dip and low_motion and sample.presence >= t.presence_in_bed:
            if self._apnea_open is None:
                self._apnea_open = sample.ts
                self._apnea_len = 1
            else:
                self._apnea_len += 1
        else:
            self._close_apnea(sample.ts)

    def _close_apnea(self, end_ts: str) -> None:
        t = self.thresholds
        if self._apnea_open is None:
            return
        if self._apnea_len >= t.apnea_min_gap_secs:
            if self._apnea_candidates:
                prev = self._apnea_candidates[-1]
                gap = int(
                    (parse_ts(self._apnea_open) - parse_ts(prev.end_ts)).total_seconds()
                )
                if gap <= t.apnea_merge_secs:
                    prev.end_ts = end_ts
                    prev.duration_secs += self._apnea_len
                    self._apnea_open = None
                    self._apnea_len = 0
                    return
            self._apnea_candidates.append(
                ApneaCandidate(
                    start_ts=self._apnea_open,
                    end_ts=end_ts,
                    duration_secs=self._apnea_len,
                )
            )
        self._apnea_open = None
        self._apnea_len = 0

    def finalize(self, night_id: str) -> NightSummary:
        if self._last_ts and self._seg_start_ts:
            self._timeline.append(
                {
                    "state": self.state.value,
                    "start": self._seg_start_ts,
                    "end": self._last_ts,
                }
            )
        if self._last_ts:
            self._close_apnea(self._last_ts)

        in_bed = (
            self._counts.get(SleepState.IN_BED.value, 0)
            + self._counts.get(SleepState.SLEEP_LIKE.value, 0)
            + self._counts.get(SleepState.RESTLESS.value, 0)
            + self._counts.get(SleepState.AWAKE_IN_BED.value, 0)
        )
        br = self._br_values
        avg_br = sum(br) / len(br) if br else 0.0
        min_br = min(br) if br else 0.0
        max_br = max(br) if br else 0.0

        return NightSummary(
            night_id=night_id,
            source=self._source,
            sample_count=self._samples,
            started_at=self._first_ts or "",
            ended_at=self._last_ts or "",
            time_in_bed_secs=in_bed,
            sleep_like_secs=self._counts.get(SleepState.SLEEP_LIKE.value, 0),
            restless_secs=self._counts.get(SleepState.RESTLESS.value, 0),
            awake_in_bed_secs=self._counts.get(SleepState.AWAKE_IN_BED.value, 0),
            avg_breathing_bpm=round(avg_br, 2),
            min_breathing_bpm=round(min_br, 2),
            max_breathing_bpm=round(max_br, 2),
            apnea_like_events=len(self._apnea_candidates),
            apnea_candidates=list(self._apnea_candidates),
            state_timeline=list(self._timeline),
        )


def analyze_samples(samples: list[Sample], night_id: str) -> NightSummary:
    engine = SessionEngine()
    for s in samples:
        engine.process(s)
    return engine.finalize(night_id)
