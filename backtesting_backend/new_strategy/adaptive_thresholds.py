"""Adaptive threshold manager for dynamic entry score levels.

Keeps a rolling window of recent signal scores and derives percentile-based
thresholds for min/strong/instant entry. Falls back to static thresholds when
insufficient samples or disabled.
"""
from collections import deque
from typing import Deque, Tuple


class AdaptiveThresholdManager:
    def __init__(self, max_samples: int = 1000, min_samples: int = 50,
                 p_min: float = 0.92, p_strong: float = 0.97, p_instant: float = 0.99,
                 hard_floor: float = 95.0):
        self.scores: Deque[float] = deque(maxlen=max_samples)
        self.min_samples = min_samples
        self.p_min = p_min
        self.p_strong = p_strong
        self.p_instant = p_instant
        self.hard_floor = hard_floor

    def add_score(self, score: float) -> None:
        if score is not None and score >= 0:
            self.scores.append(score)

    def _percentile(self, sorted_scores, p: float) -> float:
        if not sorted_scores:
            return 0.0
        k = p * (len(sorted_scores) - 1)
        f = int(k)
        c = min(f + 1, len(sorted_scores) - 1)
        if f == c:
            return sorted_scores[f]
        d = k - f
        return sorted_scores[f] + (sorted_scores[c] - sorted_scores[f]) * d

    def get_thresholds(self, static_min: float, static_strong: float, static_instant: float) -> Tuple[float, float, float]:
        if len(self.scores) < self.min_samples:
            return static_min, static_strong, static_instant
        sorted_scores = sorted(self.scores)
        min_t = max(self.hard_floor, self._percentile(sorted_scores, self.p_min))
        strong_t = max(min_t + 1.0, self._percentile(sorted_scores, self.p_strong))
        instant_t = max(strong_t + 1.0, self._percentile(sorted_scores, self.p_instant))
        return min_t, strong_t, instant_t
