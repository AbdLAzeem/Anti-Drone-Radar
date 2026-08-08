"""
MARITIME PROPAGATION
====================
The differentiator for a port-defence study: over a sea path the dominant
error in a naive range budget is not the radar equation, it is propagation.

Three effects are modelled:

1. Sea-surface multipath (two-ray). The direct and sea-reflected rays
   interfere, producing a lobed vertical coverage pattern. For a low-flying
   UAS this can cost tens of dB in the nulls, or give ~12 dB of gain at a
   lobe peak. This is the single most important effect for low-altitude
   detection and is entirely absent from the free-space model.

2. Excess attenuation - atmospheric gases and rain.

3. Radar horizon with 4/3-Earth refraction, which hard-limits the geometry
   regardless of transmit power.

References (all open, textbook / ITU recommendations):
  Skolnik, "Introduction to Radar Systems", 3rd ed., sec. 2.12 & ch. 8
  Blake, "Radar Range-Performance Analysis", ch. 5-6
  ITU-R P.676 (gaseous attenuation), ITU-R P.838-3 (rain), ITU-R P.834
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EARTH_RADIUS_M = 6_371_000.0
REFRACTION_K = 4.0 / 3.0     # standard atmosphere effective-Earth factor


# --------------------------------------------------------- radar horizon
def radar_horizon_m(h_radar_m: float, h_target_m: float, k: float = REFRACTION_K) -> float:
    """Geometric line-of-sight range over a curved Earth (metres).

    Uses the effective-Earth-radius approximation: k = 4/3 for a standard
    atmosphere. Elevated ducting over warm sea can extend this considerably
    and is flagged as future work rather than modelled here.
    """
    re = k * EARTH_RADIUS_M
    return float(np.sqrt(2.0 * re * max(h_radar_m, 0.0))
                 + np.sqrt(2.0 * re * max(h_target_m, 0.0)))


def grazing_angle_rad(h_radar_m: float, h_target_m: float, range_m: np.ndarray) -> np.ndarray:
    """Small-angle grazing angle of the sea-reflected ray."""
    range_m = np.asarray(range_m, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        psi = (h_radar_m + h_target_m) / np.where(range_m > 0, range_m, np.nan)
    return np.nan_to_num(psi, nan=0.0)


# --------------------------------------------------------- sea reflection
@dataclass
class SeaState:
    """Sea surface roughness. `sigma_h` is RMS wave height in metres."""

    name: str = "calm (sea state 1)"
    sigma_h_m: float = 0.15

    @classmethod
    def from_state(cls, state: int) -> "SeaState":
        # Douglas sea-state scale, representative RMS wave heights.
        table = {
            0: ("glassy (sea state 0)", 0.01),
            1: ("calm (sea state 1)", 0.15),
            2: ("smooth (sea state 2)", 0.35),
            3: ("slight (sea state 3)", 0.75),
            4: ("moderate (sea state 4)", 1.50),
            5: ("rough (sea state 5)", 2.50),
        }
        name, sh = table.get(state, table[3])
        return cls(name=name, sigma_h_m=sh)


def rough_surface_factor(
    sigma_h_m: float, wavelength_m: float, psi_rad: np.ndarray
) -> np.ndarray:
    """Ament / Miller-Brown specular scattering coefficient.

    A rough surface scatters energy diffusely, which suppresses the coherent
    reflected ray and therefore washes out the multipath lobing. g -> 1 for a
    smooth surface, g -> 0 for a very rough one.
    """
    g = 4.0 * np.pi * sigma_h_m * np.asarray(psi_rad, dtype=float) / wavelength_m
    return np.exp(-0.5 * g ** 2)


def sea_reflection_coefficient(
    psi_rad: np.ndarray,
    sea: SeaState,
    wavelength_m: float,
    polarization: str = "H",
) -> np.ndarray:
    """Effective (complex-magnitude) sea reflection coefficient.

    At the very small grazing angles that matter here, both polarisations
    approach |Gamma| = 1 with a 180 deg phase reversal; horizontal stays
    close to 1 while vertical dips near the pseudo-Brewster angle. Roughness
    then reduces the coherent component.
    """
    psi = np.abs(np.asarray(psi_rad, dtype=float))
    if polarization.upper().startswith("V"):
        # Crude pseudo-Brewster suppression, adequate for grazing geometry.
        gamma0 = np.clip(1.0 - 4.0 * psi, 0.2, 1.0)
    else:
        gamma0 = np.full_like(psi, 1.0)
    return gamma0 * rough_surface_factor(sea.sigma_h_m, wavelength_m, psi)


def two_ray_propagation_factor(
    range_m: np.ndarray,
    h_radar_m: float,
    h_target_m: float,
    wavelength_m: float,
    sea: SeaState | None = None,
    polarization: str = "H",
    divergence: bool = True,
) -> np.ndarray:
    """Pattern-propagation factor F (voltage ratio) over a sea surface.

        F = |1 + Gamma * exp(j * dphi)|,   dphi = 4*pi*h_r*h_t / (lambda*R)

    A 180 deg phase reversal on reflection is folded into the model, so the
    result is F = |1 - |Gamma| exp(j dphi)|. F enters the SNR as F^4, i.e.
    F = 2 is +12 dB of SNR and F -> 0 is a deep null.

    Beyond the radar horizon F is forced to zero: the reflection geometry is
    no longer valid and diffraction is not modelled.
    """
    range_m = np.atleast_1d(np.asarray(range_m, dtype=float))
    sea = sea or SeaState()

    psi = grazing_angle_rad(h_radar_m, h_target_m, range_m)
    gamma = sea_reflection_coefficient(psi, sea, wavelength_m, polarization)

    if divergence:
        # Spherical-Earth divergence reduces the reflected ray further.
        re = REFRACTION_K * EARTH_RADIUS_M
        div = 1.0 / np.sqrt(
            1.0 + (2.0 * range_m ** 2) / (re * (h_radar_m + h_target_m + 1e-9))
        )
        gamma = gamma * np.clip(div, 0.0, 1.0)

    with np.errstate(divide="ignore", invalid="ignore"):
        dphi = 4.0 * np.pi * h_radar_m * h_target_m / (wavelength_m * range_m)
    dphi = np.nan_to_num(dphi, nan=0.0, posinf=0.0)

    f = np.abs(1.0 - gamma * np.exp(1j * dphi))

    horizon = radar_horizon_m(h_radar_m, h_target_m)
    f = np.where(range_m <= horizon, f, 0.0)
    return f


# --------------------------------------------------------- attenuation
#: Approximate one-way clear-air specific attenuation at sea level for a
#: standard atmosphere (dB/km), from ITU-R P.676 curves.
_GAS_ATTEN_TABLE_GHZ_DBKM = np.array(
    [
        [1.0, 0.0045],
        [3.0, 0.0060],
        [5.0, 0.0075],
        [8.0, 0.0100],
        [10.0, 0.0120],
        [12.0, 0.0150],
        [15.0, 0.0250],
        [18.0, 0.0500],
        [20.0, 0.1100],
        [22.0, 0.1900],
        [25.0, 0.1200],
        [35.0, 0.1000],
    ]
)


def gaseous_attenuation_db_per_km(freq_Hz: float) -> float:
    """Clear-air one-way gaseous attenuation (dB/km) at sea level."""
    f_ghz = freq_Hz / 1e9
    return float(np.interp(f_ghz, _GAS_ATTEN_TABLE_GHZ_DBKM[:, 0],
                           _GAS_ATTEN_TABLE_GHZ_DBKM[:, 1]))


#: ITU-R P.838-3 rain coefficients (horizontal polarisation).
_RAIN_K_ALPHA = {
    2.0: (0.000154, 0.9630),
    4.0: (0.000650, 1.1210),
    6.0: (0.001800, 1.3080),
    8.0: (0.004510, 1.3270),
    10.0: (0.010100, 1.2760),
    12.0: (0.018800, 1.2170),
    15.0: (0.036700, 1.1540),
    20.0: (0.075100, 1.0990),
}


def rain_attenuation_db_per_km(freq_Hz: float, rain_rate_mm_h: float) -> float:
    """One-way rain attenuation (dB/km) from the ITU-R P.838 power law."""
    if rain_rate_mm_h <= 0.0:
        return 0.0
    f_ghz = freq_Hz / 1e9
    freqs = np.array(sorted(_RAIN_K_ALPHA))
    ks = np.array([_RAIN_K_ALPHA[f][0] for f in freqs])
    alphas = np.array([_RAIN_K_ALPHA[f][1] for f in freqs])
    # k is interpolated logarithmically, alpha linearly, per P.838 guidance.
    k = float(np.exp(np.interp(f_ghz, freqs, np.log(ks))))
    alpha = float(np.interp(f_ghz, freqs, alphas))
    return k * rain_rate_mm_h ** alpha


@dataclass
class Atmosphere:
    """Excess-loss budget for one propagation path."""

    rain_rate_mm_h: float = 0.0
    name: str = "clear air"

    def one_way_db_per_km(self, freq_Hz: float) -> float:
        return (
            gaseous_attenuation_db_per_km(freq_Hz)
            + rain_attenuation_db_per_km(freq_Hz, self.rain_rate_mm_h)
        )

    @classmethod
    def presets(cls) -> dict[str, "Atmosphere"]:
        return {
            "clear": cls(0.0, "clear air"),
            "light_rain": cls(4.0, "light rain (4 mm/h)"),
            "moderate_rain": cls(16.0, "moderate rain (16 mm/h)"),
            "heavy_rain": cls(50.0, "heavy rain (50 mm/h)"),
        }
