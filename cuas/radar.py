"""
LAYER 1 - DETECTION
===================
Noise-limited radar detection performance.

Replaces the ad-hoc `Pmin` constant of the first prototype with a proper
receiver noise budget and statistical detection theory:

    SNR(R) = Pt * G^2 * lambda^2 * sigma * F^4 * n
             ------------------------------------------
             (4pi)^3 * R^4 * k*Ts*B * NF * L * L_atm(R)

Detection probability is then obtained from the exact distribution of the
square-law detector output rather than assumed:

    Swerling 0/5 (non-fluctuating) : Marcum Q  -> non-central chi-square
    Swerling 2   (fast fluctuating): scaled central chi-square

`albersheim_required_snr_db` gives the classical design-side inverse
(required single-pulse SNR for a target Pd/Pfa) and is used for fast
range-budget work.

References (textbook level, no restricted data):
  Skolnik, "Introduction to Radar Systems", 3rd ed., ch. 2
  Mahafza, "Radar Systems Analysis and Design Using MATLAB", ch. 2-4
  Albersheim, Proc. IEEE 69(7), 1981
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from scipy.optimize import brentq
from scipy.stats import chi2, ncx2

# ---------------------------------------------------------------- constants
C_LIGHT = 299_792_458.0       # m/s
K_BOLTZMANN = 1.380649e-23    # J/K
T0_REF = 290.0                # K, IEEE reference noise temperature

SwerlingModel = Literal["swerling0", "swerling2"]


def db2lin(x):
    """dB -> linear power ratio."""
    return 10.0 ** (np.asarray(x, dtype=float) / 10.0)


def lin2db(x):
    """Linear power ratio -> dB."""
    return 10.0 * np.log10(np.asarray(x, dtype=float))


# ---------------------------------------------------------------- config
@dataclass
class RadarConfig:
    """Generic X-band surveillance radar.

    Values are representative textbook figures for a class of coastal
    surveillance radars. They are NOT taken from any specific system.
    """

    name: str = "Generic X-band coastal surveillance"
    Pt_W: float = 1000.0            # peak transmit power
    gain_dBi: float = 30.0          # antenna gain (Tx = Rx)
    freq_Hz: float = 9.5e9          # X-band
    bandwidth_Hz: float = 1.0e6     # receiver noise bandwidth
    noise_figure_dB: float = 3.0    # receiver noise figure
    losses_dB: float = 6.0          # RF + processing + beam-shape losses
    n_pulses: int = 20              # pulses non-coherently integrated
    pfa: float = 1e-6               # probability of false alarm per cell
    T_sys_K: float = T0_REF         # system noise temperature
    antenna_height_m: float = 15.0  # above mean sea level
    polarization: str = "H"

    # ---- derived -------------------------------------------------------
    @property
    def wavelength_m(self) -> float:
        return C_LIGHT / self.freq_Hz

    @property
    def gain_lin(self) -> float:
        return float(db2lin(self.gain_dBi))

    @property
    def noise_power_W(self) -> float:
        """kTsB * F  - receiver noise power referred to the input."""
        return (
            K_BOLTZMANN
            * self.T_sys_K
            * self.bandwidth_Hz
            * float(db2lin(self.noise_figure_dB))
        )

    def summary(self) -> dict:
        return {
            "name": self.name,
            "freq_GHz": self.freq_Hz / 1e9,
            "wavelength_cm": self.wavelength_m * 100,
            "Pt_kW": self.Pt_W / 1e3,
            "gain_dBi": self.gain_dBi,
            "noise_power_dBm": lin2db(self.noise_power_W * 1e3),
            "n_pulses": self.n_pulses,
            "pfa": self.pfa,
        }

    # ---- presets -------------------------------------------------------
    @classmethod
    def generic_surveillance(cls) -> "RadarConfig":
        """General-purpose coastal surveillance radar.

        A rotating navigation/surveillance set. Optimised for ships, with a
        short dwell per scan. Included to establish the baseline: this class
        of radar is what a port already has, and it is *not* adequate against
        a small UAS.
        """
        return cls(
            name="Generic X-band coastal surveillance (baseline)",
            Pt_W=1000.0, gain_dBi=30.0, freq_Hz=9.5e9,
            bandwidth_Hz=1.0e6, noise_figure_dB=3.0, losses_dB=6.0,
            n_pulses=20, pfa=1e-6, antenna_height_m=15.0,
        )

    @classmethod
    def cuas_staring(cls) -> "RadarConfig":
        """Dedicated C-UAS staring/electronically-scanned radar.

        The design response to the low-RCS problem. Two changes matter, and
        neither is exotic:

          * higher aperture gain (36 dBi vs 30) - +12 dB two-way
          * long dwell (512 pulses vs 20) - a staring array does not have to
            spend its time rotating, so it can integrate ~8 dB longer

        Together these are ~20 dB of SNR, which is a factor of ~3 in range
        because range only grows as SNR^(1/4). That factor-of-3 is the whole
        engineering argument for a dedicated sensor.
        """
        return cls(
            name="Dedicated X-band C-UAS staring array",
            Pt_W=1000.0, gain_dBi=36.0, freq_Hz=9.5e9,
            bandwidth_Hz=2.0e6, noise_figure_dB=3.0, losses_dB=5.0,
            n_pulses=512, pfa=1e-6, antenna_height_m=25.0,
        )


# ---------------------------------------------------------------- SNR
def snr_single_pulse(
    cfg: RadarConfig,
    rcs_m2: float | np.ndarray,
    range_m: float | np.ndarray,
    propagation_factor: float | np.ndarray = 1.0,
    extra_loss_dB: float | np.ndarray = 0.0,
) -> np.ndarray:
    """Single-pulse signal-to-noise ratio (linear).

    Parameters
    ----------
    propagation_factor
        Pattern-propagation factor F (voltage ratio). Enters as F^4 because
        it applies on both the outbound and return path. F = 1 for free
        space; see :mod:`cuas.propagation` for the sea-surface two-ray model.
    extra_loss_dB
        One-way excess loss in dB (atmospheric gas, rain). Applied twice.
    """
    rcs_m2 = np.asarray(rcs_m2, dtype=float)
    range_m = np.asarray(range_m, dtype=float)
    lam = cfg.wavelength_m

    num = cfg.Pt_W * cfg.gain_lin ** 2 * lam ** 2 * rcs_m2
    den = (4.0 * np.pi) ** 3 * range_m ** 4 * cfg.noise_power_W

    snr = num / den
    snr = snr / db2lin(cfg.losses_dB)
    snr = snr * np.asarray(propagation_factor, dtype=float) ** 4
    snr = snr / db2lin(2.0 * np.asarray(extra_loss_dB, dtype=float))
    return snr


def snr_integrated(
    cfg: RadarConfig, snr_sp: float | np.ndarray, coherent: bool = False
) -> np.ndarray:
    """Integration gain over `cfg.n_pulses`.

    Coherent integration gives the full N gain. Non-coherent integration is
    lossy; the ~N^0.8 rule of thumb is used for quick budgets. For rigorous
    work use `probability_of_detection`, which handles N pulses exactly.
    """
    n = cfg.n_pulses
    gain = float(n) if coherent else float(n) ** 0.8
    return np.asarray(snr_sp, dtype=float) * gain


# ---------------------------------------------------------------- Pd
def detection_threshold(pfa: float, n_pulses: int) -> float:
    """Square-law detector threshold for a given Pfa.

    Noise power is normalised to unity per I/Q pair, so the sum of N pulses
    is central chi-square with 2N degrees of freedom under H0.
    """
    return float(chi2.isf(pfa, df=2 * n_pulses))


def probability_of_detection(
    snr_sp: float | np.ndarray,
    pfa: float = 1e-6,
    n_pulses: int = 1,
    model: SwerlingModel = "swerling0",
) -> np.ndarray:
    """Exact Pd for a square-law detector, N non-coherently integrated pulses.

    swerling0 : non-fluctuating RCS. Output is non-central chi-square with
                2N dof and non-centrality 2*N*SNR (equivalent to Marcum's Q
                for N = 1).
    swerling2 : RCS independently Rayleigh-fluctuating pulse to pulse, which
                scales the central chi-square by (1 + SNR).

    Swerling 1/3/4 are deliberately omitted rather than approximated;
    swerling0 and swerling2 bracket the realistic range for small UAS.

    Note on the saturation guard: `scipy.stats.ncx2` is numerically unsafe
    (it can abort the interpreter) for very large non-centrality, which is
    exactly what a short-range, high-SNR cell produces. Those cells are
    Pd = 1 to well beyond double precision - the threshold sits tens of
    standard deviations into the lower tail - so they are set directly
    instead of evaluated.
    """
    scalar_in = np.ndim(snr_sp) == 0
    snr = np.atleast_1d(np.asarray(snr_sp, dtype=float))
    thr = detection_threshold(pfa, n_pulses)
    dof = 2 * n_pulses

    if model == "swerling0":
        nc = 2.0 * n_pulses * np.clip(snr, 0.0, None)
        pd = np.empty_like(nc)

        saturated = nc > max(1.0e4, 30.0 * thr)     # Pd = 1 to machine precision
        vanishing = nc < 1.0e-12                    # degenerates to central chi2
        mid = ~(saturated | vanishing)

        pd[saturated] = 1.0
        pd[vanishing] = float(chi2.sf(thr, df=dof))
        if mid.any():
            pd[mid] = ncx2.sf(thr, df=dof, nc=nc[mid])
    elif model == "swerling2":
        pd = chi2.sf(thr / (1.0 + np.clip(snr, 0.0, None)), df=dof)
    else:
        raise ValueError(f"unknown Swerling model: {model!r}")

    pd = np.clip(np.nan_to_num(pd, nan=0.0), 0.0, 1.0)
    return float(pd[0]) if scalar_in else pd


def albersheim_required_snr_db(pd: float, pfa: float, n_pulses: int = 1) -> float:
    """Required single-pulse SNR (dB) via Albersheim's empirical inversion.

    Valid for a non-fluctuating target, linear detector, non-coherent
    integration, 1e-7 <= Pfa <= 1e-3, 0.1 <= Pd <= 0.9, N <= 8096.
    Accuracy is within ~0.2 dB of the exact result over that region.
    """
    if not 0.0 < pd < 1.0:
        raise ValueError("pd must lie in (0, 1)")
    a = np.log(0.62 / pfa)
    b = np.log(pd / (1.0 - pd))
    n = float(n_pulses)
    return float(
        -5.0 * np.log10(n)
        + (6.2 + 4.54 / np.sqrt(n + 0.44)) * np.log10(a + 0.12 * a * b + 1.7 * b)
    )


# ---------------------------------------------------------------- range
def max_detection_range(
    cfg: RadarConfig,
    rcs_m2: float,
    pd_target: float = 0.9,
    model: SwerlingModel = "swerling0",
    atten_dB_per_km: float = 0.0,
    propagation_factor: float = 1.0,
    r_bounds_m: tuple[float, float] = (50.0, 300_000.0),
) -> float:
    """Range at which Pd falls to `pd_target`, solved numerically.

    Solving numerically (rather than the closed-form R^4 inversion) lets
    range-dependent attenuation and propagation effects be included, which
    is what actually matters over a sea path.
    """

    def excess(r_m: float) -> float:
        atten = atten_dB_per_km * (r_m / 1000.0)
        snr = snr_single_pulse(
            cfg, rcs_m2, r_m,
            propagation_factor=propagation_factor,
            extra_loss_dB=atten,
        )
        pd = probability_of_detection(snr, cfg.pfa, cfg.n_pulses, model)
        return float(pd) - pd_target

    lo, hi = r_bounds_m
    if excess(lo) < 0.0:
        return 0.0            # cannot reach Pd target even at minimum range
    if excess(hi) > 0.0:
        return float(hi)      # target Pd still met at the search ceiling
    return float(brentq(excess, lo, hi, xtol=1.0))


def max_range_classic(
    cfg: RadarConfig, rcs_m2: float, snr_required_lin: float
) -> float:
    """Closed-form R_max for a required SNR - the classic range equation.

    Kept for cross-checking `max_detection_range` and for the thesis
    derivation that shows R_max is proportional to sigma^(1/4).
    """
    lam = cfg.wavelength_m
    num = cfg.Pt_W * cfg.gain_lin ** 2 * lam ** 2 * rcs_m2
    den = (
        (4.0 * np.pi) ** 3
        * cfg.noise_power_W
        * snr_required_lin
        * float(db2lin(cfg.losses_dB))
    )
    return float((num / den) ** 0.25)


# ---------------------------------------------------------------- RCS library
#: Representative RCS values (m^2) at X-band, open-literature order of
#: magnitude only. Real values are strongly aspect and frequency dependent.
RCS_LIBRARY: dict[str, float] = {
    "small bird": 0.001,
    "micro-UAS / nano quad": 0.005,
    "small quadcopter (DJI class)": 0.01,
    "medium multirotor": 0.05,
    "large multirotor / small fixed-wing": 0.1,
    "tactical fixed-wing UAS": 1.0,
}


@dataclass
class RangeBudget:
    """Tabulated detection range for each entry in an RCS library."""

    cfg: RadarConfig
    pd_target: float = 0.9
    model: SwerlingModel = "swerling0"
    atten_dB_per_km: float = 0.0
    library: dict[str, float] = field(default_factory=lambda: dict(RCS_LIBRARY))

    def table(self) -> list[dict]:
        rows = []
        for label, rcs in self.library.items():
            r_free = max_detection_range(
                self.cfg, rcs, self.pd_target, self.model, 0.0
            )
            r_atm = max_detection_range(
                self.cfg, rcs, self.pd_target, self.model, self.atten_dB_per_km
            )
            rows.append(
                {
                    "target": label,
                    "rcs_m2": rcs,
                    "range_free_km": r_free / 1000.0,
                    "range_with_atten_km": r_atm / 1000.0,
                    "atten_penalty_km": (r_free - r_atm) / 1000.0,
                }
            )
        return rows
