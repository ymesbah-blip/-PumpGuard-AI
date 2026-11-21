"""PumpGuard AI: educational, open-source vibration-monitoring toolkit for centrifugal pumps.

The bundled signal generator is synthetic. Nothing in this package is validated
for diagnosing real equipment or for operational or safety decisions.
"""

from ._version import __version__
from .bearings import BEARING_PRESETS, BearingGeometry, DefectFrequencies
from .features import TIME_FEATURES, extract_all_features, extract_features
from .health import demo_health_score
from .signals import CONDITIONS, SignalConfig, SyntheticSignal, generate_signal, simulate
from .spectral import amplitude_spectrum, envelope_spectrum, spectral_features

__all__ = [
    "BEARING_PRESETS",
    "CONDITIONS",
    "TIME_FEATURES",
    "BearingGeometry",
    "DefectFrequencies",
    "SignalConfig",
    "SyntheticSignal",
    "__version__",
    "amplitude_spectrum",
    "demo_health_score",
    "envelope_spectrum",
    "extract_all_features",
    "extract_features",
    "generate_signal",
    "simulate",
    "spectral_features",
]
