"""Rolling-element bearing defect frequencies (kinematic, no-slip approximation).

For a bearing with ``n`` rolling elements of diameter ``d`` on a pitch diameter
``D`` with contact angle ``phi``, rotating with a stationary outer race at shaft
frequency ``fr`` (Hz)::

    FTF  = fr / 2 * (1 - d/D * cos(phi))              # cage / fundamental train
    BPFO = n * fr / 2 * (1 - d/D * cos(phi))          # outer-race defect
    BPFI = n * fr / 2 * (1 + d/D * cos(phi))          # inner-race defect
    BSF  = D / (2 d) * fr * (1 - (d/D * cos(phi))**2) # rolling-element spin

A rolling-element defect that strikes both races typically shows up at ``2 * BSF``.
Real bearings slip by roughly 1-2 %, so measured peaks deviate slightly from
these kinematic values.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from ._validation import require_positive

__all__ = ["BEARING_PRESETS", "BearingGeometry", "DefectFrequencies"]


@dataclass(frozen=True)
class DefectFrequencies:
    """Characteristic bearing frequencies in Hz for one shaft speed."""

    shaft_hz: float
    ftf: float
    bpfo: float
    bpfi: float
    bsf: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class BearingGeometry:
    """Geometry of a rolling-element bearing.

    Diameters may be in any consistent unit; only their ratio matters.
    """

    n_elements: int
    ball_diameter_mm: float
    pitch_diameter_mm: float
    contact_angle_deg: float = 0.0
    name: str = "custom"

    def __post_init__(self) -> None:
        if int(self.n_elements) != self.n_elements or self.n_elements < 1:
            raise ValueError("n_elements must be a positive integer")
        require_positive("ball_diameter_mm", self.ball_diameter_mm)
        require_positive("pitch_diameter_mm", self.pitch_diameter_mm)
        if self.ball_diameter_mm >= self.pitch_diameter_mm:
            raise ValueError("ball_diameter_mm must be smaller than pitch_diameter_mm")
        if not 0.0 <= self.contact_angle_deg < 90.0:
            raise ValueError("contact_angle_deg must be in [0, 90)")

    @classmethod
    def from_preset(cls, name: str) -> BearingGeometry:
        """Return a named geometry from :data:`BEARING_PRESETS`."""
        try:
            return BEARING_PRESETS[name]
        except KeyError:
            raise ValueError(
                f"unknown bearing preset {name!r}; available: {sorted(BEARING_PRESETS)}"
            ) from None

    def defect_frequencies(self, rpm: float) -> DefectFrequencies:
        """Kinematic defect frequencies (Hz) at shaft speed ``rpm``."""
        fr = require_positive("rpm", rpm) / 60.0
        ratio = (self.ball_diameter_mm / self.pitch_diameter_mm) * math.cos(
            math.radians(self.contact_angle_deg)
        )
        n = self.n_elements
        return DefectFrequencies(
            shaft_hz=fr,
            ftf=fr / 2.0 * (1.0 - ratio),
            bpfo=n * fr / 2.0 * (1.0 - ratio),
            bpfi=n * fr / 2.0 * (1.0 + ratio),
            bsf=self.pitch_diameter_mm / (2.0 * self.ball_diameter_mm) * fr * (1.0 - ratio**2),
        )


#: Named bearing geometries. Contributions welcome — cite the source of each geometry.
BEARING_PRESETS: dict[str, BearingGeometry] = {
    # 6205 deep-groove ball bearing: 9 balls, 7.94 mm ball diameter, 39.04 mm pitch
    # diameter. This geometry is widely used in public bearing-fault datasets.
    "6205": BearingGeometry(9, 7.94, 39.04, 0.0, "6205 deep-groove ball bearing"),
}
