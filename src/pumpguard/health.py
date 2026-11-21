"""Toy health indicator for demonstrations.

This is deliberately simple and **not** calibrated to any machine, standard or
failure mode. Because it only looks at RMS, it is blind to early bearing faults
(impacts raise kurtosis and envelope peaks long before they raise RMS) — a
useful teaching point, not a bug to hide.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

__all__ = ["demo_health_score"]


def demo_health_score(features: Mapping[str, float]) -> float:
    """Toy score from 0-100 based only on RMS; illustrative only, not calibrated."""
    rms = float(features["rms"])
    if not math.isfinite(rms) or rms < 0:
        raise ValueError("features['rms'] must be a finite, non-negative number")
    score = 100.0 - min(100.0, max(0.0, (rms - 0.1) * 80))
    return round(score, 1)
