from __future__ import annotations

import pytest

from pumpguard import BearingGeometry, SignalConfig, SyntheticSignal, simulate


@pytest.fixture(scope="session")
def bearing() -> BearingGeometry:
    return BearingGeometry.from_preset("6205")


@pytest.fixture(scope="session")
def signals() -> dict[str, SyntheticSignal]:
    """One default-config signal per condition, generated once per test session."""
    from pumpguard import CONDITIONS

    return {c: simulate(SignalConfig(condition=c)) for c in CONDITIONS}
