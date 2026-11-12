"""Published reference ranges used to put a trial's numbers in context.

These are context references for healthy adults (mostly stair descent), NOT clinical good/bad
thresholds. A value is classified as below / within / above the band; the app never calls a value
"healthy" or "risky". Sources and verification status are listed in docs/research/reference-ranges.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefRange:
    low: float
    high: float
    source: str
    context: str        # population / task the band comes from
    verified: bool = True


# Filled from docs/research/reference-ranges.md (keys = metric keys in metrics.INFO).
# Bands are mean +- 1 SD of a cited cohort where an SD exists, otherwise the range of study means
# reported in a review. Our values are 2D video estimates, so small offsets from lab 3D data are expected.
RANGES: dict[str, RefRange] = {
    "knee_flexion_peak": RefRange(76.0, 89.1, "Lewis et al. 2015",
                                  "healthy adults, stair descent, mean ± 1 SD (n = 30)"),
    "knee_flexion_rom": RefRange(76.0, 90.0, "Zhang et al. 2020 review",
                                 "healthy adults, stair descent, range of study means"),
    "hip_flexion_peak": RefRange(13.4, 28.9, "Lewis et al. 2015",
                                 "healthy adults, stair descent, mean ± 1 SD (n = 30)"),
    "ankle_dorsiflexion_peak": RefRange(23.3, 38.0, "Lewis et al. 2015",
                                        "healthy adults, stair descent, mean ± 1 SD (n = 30)"),
    "knee_ext_moment_peak": RefRange(1.0, 1.6, "Zhang et al. 2020 review",
                                     "healthy adults, stair descent (late stance), range of study means"),
    "knee_power_absorption_peak": RefRange(2.1, 5.5, "Zhang et al. 2020 review; Riener et al. 2002",
                                           "healthy adults, stair descent, peak absorption, range of study means"),
}


def classify(key: str, value: float | None) -> str | None:
    """'below' | 'within' | 'above' | None (no reference or no value)."""
    r = RANGES.get(key)
    if r is None or value is None:
        return None
    if value < r.low:
        return "below"
    if value > r.high:
        return "above"
    return "within"
