"""Small, dependency-free statistical routines with documented behaviour.

They are deliberately simple so results can be reproduced by hand or in a
spreadsheet. Each function documents its assumptions.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from statistics import median


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def mad(values: list[float]) -> float:
    """Median absolute deviation (unscaled)."""
    med = median(values)
    return median([abs(v - med) for v in values])


def robust_z_scores(values: list[float]) -> list[float] | None:
    """Modified z-scores (Iglewicz & Hoaglin, 1993): 0.6745 · (x − median) / MAD.

    Returns ``None`` when MAD is zero (more than half the values are identical),
    in which case the method cannot discriminate outliers.
    """
    if len(values) < 3:
        return None
    med = median(values)
    m = mad(values)
    if m == 0:
        return None
    return [0.6745 * (v - med) / m for v in values]


@dataclass
class TrendResult:
    n: int
    s: int
    z: float
    p_value: float
    sen_slope: float
    direction: str  # "increasing" | "decreasing" | "none"


def mann_kendall(values: list[float], alpha: float = 0.05) -> TrendResult | None:
    """Mann-Kendall monotonic trend test with tie correction and Sen's slope.

    Normal approximation; recommended for n ≥ 8 but computed from n ≥ 4.
    Autocorrelation is not corrected (documented limitation).
    """
    n = len(values)
    if n < 4:
        return None
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = values[j] - values[i]
            s += (diff > 0) - (diff < 0)
    ties = Counter(values).values()
    var_s = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties)) / 18.0
    if var_s <= 0:
        return TrendResult(n, s, 0.0, 1.0, 0.0, "none")
    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    p = 2.0 * (1.0 - normal_cdf(abs(z)))
    slopes = [(values[j] - values[i]) / (j - i) for i in range(n - 1) for j in range(i + 1, n)]
    sen = median(slopes)
    direction = "none"
    if p < alpha:
        direction = "increasing" if z > 0 else "decreasing"
    return TrendResult(n, s, z, p, sen, direction)


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator is None or denominator == 0 or numerator is None:
        return None
    return numerator / denominator


def round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return None
    return round(float(value), digits)
