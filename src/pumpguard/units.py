"""Explicit unit conversions. Everything inside PumpGuard is SI.

Field data often arrive in oilfield units (barrels per day, feet, psi, bar).
Convert at the boundary with these functions and keep SI everywhere else.
"""

from __future__ import annotations

__all__ = [
    "BAR_PA",
    "BBL_M3",
    "FT_M",
    "PSI_PA",
    "STANDARD_GRAVITY",
    "WATER_DENSITY_KG_M3",
    "bar_to_pa",
    "bpd_to_m3s",
    "celsius_to_kelvin",
    "ft_to_m",
    "m3s_to_bpd",
    "m_to_ft",
    "pa_to_bar",
    "pa_to_psi",
    "psi_to_pa",
]

STANDARD_GRAVITY = 9.80665  # m/s^2 (exact, CGPM 1901)
WATER_DENSITY_KG_M3 = 1000.0  # reference density for specific gravity
BBL_M3 = 0.158987294928  # 1 US oil barrel = 42 US gal (exact)
FT_M = 0.3048  # international foot (exact)
BAR_PA = 1.0e5  # exact
PSI_PA = 6894.757293168361  # 1 lbf/in^2
_DAY_S = 86_400.0


def bpd_to_m3s(bpd: float) -> float:
    """Barrels per day -> cubic metres per second."""
    return bpd * BBL_M3 / _DAY_S


def m3s_to_bpd(m3s: float) -> float:
    """Cubic metres per second -> barrels per day."""
    return m3s * _DAY_S / BBL_M3


def ft_to_m(ft: float) -> float:
    return ft * FT_M


def m_to_ft(m: float) -> float:
    return m / FT_M


def bar_to_pa(bar: float) -> float:
    return bar * BAR_PA


def pa_to_bar(pa: float) -> float:
    return pa / BAR_PA


def psi_to_pa(psi: float) -> float:
    return psi * PSI_PA


def pa_to_psi(pa: float) -> float:
    return pa / PSI_PA


def celsius_to_kelvin(celsius: float) -> float:
    if celsius < -273.15:
        raise ValueError("temperature below absolute zero")
    return celsius + 273.15
