"""Rolling feature helpers (ready for real CSI streams later)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class RollingStats:
    """Simple ring buffer for motion / breathing smoothing."""

    window: int = 30
    _vals: deque[float] | None = None

    def __post_init__(self) -> None:
        self._vals = deque(maxlen=self.window)

    def push(self, x: float) -> None:
        assert self._vals is not None
        self._vals.append(x)

    def mean(self) -> float:
        assert self._vals is not None
        if not self._vals:
            return 0.0
        return sum(self._vals) / len(self._vals)

    def variance(self) -> float:
        assert self._vals is not None
        if len(self._vals) < 2:
            return 0.0
        m = self.mean()
        return sum((v - m) ** 2 for v in self._vals) / len(self._vals)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def normalize_motion(raw_energy: float, p95: float) -> float:
    """Map raw motion energy to 0–1 using a running P95 scale."""
    if p95 <= 1e-9:
        return clamp01(raw_energy)
    return clamp01(raw_energy / p95)
