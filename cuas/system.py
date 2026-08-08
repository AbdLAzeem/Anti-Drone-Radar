"""
LAYER 4 - SYSTEM INTEGRATION
============================
Layered detection probability, 2-D coverage mapping, gap analysis and
sensor-siting optimisation.

The first prototype set each sensor's Pd curve with hand-picked logistic
parameters, which cannot be defended in review. Here every curve is derived
from a stated physical mechanism:

  radar     : full noise-limited chain from `cuas.radar`, including
              sea-surface multipath and atmospheric loss
  rf_detect : receiver sensitivity against a UAS control/video downlink,
              free-space path loss - fails against an autonomous, RF-silent
              aircraft, which is exactly why the layering matters
  eo_ir     : angular-resolution limit, Johnson-criteria style - needs N
              pixels across the target to declare
  acoustic  : spherical spreading plus air absorption against ambient noise;
              a port is a loud environment, so this layer is short-ranged

Fusion of independent sensors:

    Pd_system(r) = 1 - PROD_i (1 - Pd_i(r))

The independence assumption is stated, not hidden: correlated failure modes
(fog degrading EO/IR and rain degrading radar at once) are handled by
running the whole map under a weather preset instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from . import propagation as prop
from . import radar as rad


# ---------------------------------------------------------------- sensors
@dataclass
class SensorModel:
    """A sensor with a physically-derived range-dependent Pd."""

    name: str
    pd_fn: Callable[[np.ndarray], np.ndarray]
    position_m: tuple[float, float] = (0.0, 0.0)
    weather_sensitive: bool = False

    def pd_at_range(self, range_m: np.ndarray) -> np.ndarray:
        return np.clip(self.pd_fn(np.asarray(range_m, dtype=float)), 0.0, 1.0)

    def pd_on_grid(self, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
        r = np.hypot(xx - self.position_m[0], yy - self.position_m[1])
        return self.pd_at_range(r)


def make_radar_sensor(
    cfg: rad.RadarConfig,
    rcs_m2: float,
    target_alt_m: float = 60.0,
    atmosphere: prop.Atmosphere | None = None,
    sea: prop.SeaState | None = None,
    position_m: tuple[float, float] = (0.0, 0.0),
    include_multipath: bool = True,
    model: rad.SwerlingModel = "swerling0",
    name: str | None = None,
) -> SensorModel:
    """Radar Pd(r) from the full detection chain."""
    atmosphere = atmosphere or prop.Atmosphere()
    sea = sea or prop.SeaState()
    atten = atmosphere.one_way_db_per_km(cfg.freq_Hz)

    def pd_fn(r: np.ndarray) -> np.ndarray:
        r = np.maximum(np.asarray(r, dtype=float), 1.0)
        if include_multipath:
            f = prop.two_ray_propagation_factor(
                r, cfg.antenna_height_m, target_alt_m,
                cfg.wavelength_m, sea, cfg.polarization,
            )
        else:
            horizon = prop.radar_horizon_m(cfg.antenna_height_m, target_alt_m)
            f = np.where(r <= horizon, 1.0, 0.0)
        snr = rad.snr_single_pulse(
            cfg, rcs_m2, r,
            propagation_factor=f,
            extra_loss_dB=atten * (r / 1000.0),
        )
        return rad.probability_of_detection(snr, cfg.pfa, cfg.n_pulses, model)

    return SensorModel(
        name=name or f"Radar ({cfg.freq_Hz/1e9:.1f} GHz)",
        pd_fn=pd_fn,
        position_m=position_m,
        weather_sensitive=True,
    )


def make_rf_sensor(
    eirp_dBm: float = 20.0,
    freq_Hz: float = 2.44e9,
    sensitivity_dBm: float = -95.0,
    required_margin_dB: float = 6.0,
    margin_sigma_dB: float = 5.0,
    position_m: tuple[float, float] = (0.0, 0.0),
    name: str = "RF detector",
) -> SensorModel:
    """Passive RF detection of a UAS downlink, free-space path loss.

    Pd is a soft function of link margin (a normal-CDF over shadowing and
    aspect variation) rather than a hard threshold. Detects nothing if the
    aircraft is autonomous and RF-silent - a stated limitation of the layer.
    """
    from scipy.stats import norm

    def pd_fn(r: np.ndarray) -> np.ndarray:
        r = np.maximum(np.asarray(r, dtype=float), 1.0)
        fspl = 20.0 * np.log10(4.0 * np.pi * r * freq_Hz / rad.C_LIGHT)
        margin = eirp_dBm - fspl - sensitivity_dBm - required_margin_dB
        return norm.cdf(margin / margin_sigma_dB)

    return SensorModel(name=name, pd_fn=pd_fn, position_m=position_m)


def make_eo_ir_sensor(
    target_size_m: float = 0.35,
    pixels_required: float = 6.0,
    ifov_urad: float = 40.0,
    transition_sigma: float = 0.25,
    position_m: tuple[float, float] = (0.0, 0.0),
    weather_derate: float = 1.0,
    name: str = "EO/IR",
) -> SensorModel:
    """Resolution-limited EO/IR detection.

    Range at which the target subtends `pixels_required` detector pixels:

        R_lim = target_size / (pixels_required * IFOV)

    Pd rolls off around R_lim with a log-normal transition representing
    contrast and atmospheric-clarity variation. `weather_derate` < 1 models
    haze or fog.
    """
    from scipy.stats import norm

    r_lim = weather_derate * target_size_m / (pixels_required * ifov_urad * 1e-6)

    def pd_fn(r: np.ndarray) -> np.ndarray:
        r = np.maximum(np.asarray(r, dtype=float), 1.0)
        return norm.cdf(-np.log(r / r_lim) / transition_sigma)

    return SensorModel(name=name, pd_fn=pd_fn, position_m=position_m,
                       weather_sensitive=True)


def make_acoustic_sensor(
    source_level_dB: float = 70.0,
    tonal_fraction_dB: float = -6.0,
    ambient_spectral_dB_per_hz: float = 15.0,
    analysis_bandwidth_Hz: float = 5.0,
    array_gain_dB: float = 12.0,
    required_snr_dB: float = 8.0,
    ref_distance_m: float = 1.0,
    absorption_dB_per_km: float = 3.0,
    transition_sigma_dB: float = 4.0,
    position_m: tuple[float, float] = (0.0, 0.0),
    name: str = "Acoustic array",
) -> SensorModel:
    """Narrowband acoustic detection of the blade-passage tone.

    A broadband level-vs-ambient comparison gives a detection range of a few
    metres and is simply the wrong model: a practical acoustic C-UAS sensor
    beamforms a microphone array and integrates a narrow band around the
    blade-passage harmonic. Both gains are therefore explicit:

        SNR(r) = (L_src + tonal) - 20log10(r) - alpha*r
                 - (N0 + 10log10(B) - G_array)

    with N0 the ambient spectral density (dB re threshold per Hz), B the
    analysis bandwidth and G_array the beamforming gain. Defaults put the
    Pd = 0.5 point in the low hundreds of metres, consistent with reported
    acoustic C-UAS performance, and keep this as the innermost layer.
    """
    from scipy.stats import norm

    in_band_noise = (
        ambient_spectral_dB_per_hz
        + 10.0 * np.log10(max(analysis_bandwidth_Hz, 1e-6))
        - array_gain_dB
    )

    def pd_fn(r: np.ndarray) -> np.ndarray:
        r = np.maximum(np.asarray(r, dtype=float), ref_distance_m)
        spreading = 20.0 * np.log10(r / ref_distance_m)
        absorb = absorption_dB_per_km * (r / 1000.0)
        snr = source_level_dB + tonal_fraction_dB - spreading - absorb - in_band_noise
        return norm.cdf((snr - required_snr_dB) / transition_sigma_dB)

    return SensorModel(name=name, pd_fn=pd_fn, position_m=position_m)


# ---------------------------------------------------------------- fusion
def fused_pd(pd_list: Sequence[np.ndarray]) -> np.ndarray:
    """Pd_sys = 1 - PROD(1 - Pd_i), independent sensors."""
    acc = np.ones_like(np.asarray(pd_list[0], dtype=float))
    for pd in pd_list:
        acc = acc * (1.0 - np.clip(np.asarray(pd, dtype=float), 0.0, 1.0))
    return 1.0 - acc


def fused_pd_correlated(pd_list: Sequence[np.ndarray], rho: float = 0.3) -> np.ndarray:
    """Conservative fusion under partially correlated sensor failures.

    Linear blend between full independence and the best single sensor.
    `rho = 0` recovers the independent case; `rho = 1` credits only the best
    sensor. Useful as a pessimistic bound when reporting to a customer.
    """
    indep = fused_pd(pd_list)
    best = np.max(np.stack([np.asarray(p, float) for p in pd_list]), axis=0)
    rho = float(np.clip(rho, 0.0, 1.0))
    return (1.0 - rho) * indep + rho * best


# ---------------------------------------------------------------- site
@dataclass
class Asset:
    """A critical asset that must be protected, with its stand-off ring."""

    name: str
    position_m: tuple[float, float]
    keepout_radius_m: float = 1_500.0
    priority: int = 1


@dataclass
class ProtectedArea:
    """Analysis grid, protected assets, and the threat approach sector.

    Coordinates are local ENU metres. The grid is square and centred on the
    origin. `assets` defaults to a single asset at the origin so the simple
    single-asset case still works unchanged.
    """

    name: str = "Port approach (generic maritime layout)"
    extent_m: float = 12_000.0
    grid_n: int = 241
    keepout_radius_m: float = 1_500.0     # used when `assets` is empty
    sector_deg: tuple[float, float] = (0.0, 360.0)
    assets: list[Asset] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.assets:
            self.assets = [
                Asset("protected asset", (0.0, 0.0), self.keepout_radius_m)
            ]

    def grid(self) -> tuple[np.ndarray, np.ndarray]:
        ax = np.linspace(-self.extent_m, self.extent_m, self.grid_n)
        return np.meshgrid(ax, ax)

    def sector_mask(self, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
        ang = np.rad2deg(np.arctan2(yy, xx)) % 360.0
        lo, hi = self.sector_deg
        if hi - lo >= 360.0:
            return np.ones_like(xx, dtype=bool)
        lo, hi = lo % 360.0, hi % 360.0
        return (ang >= lo) & (ang <= hi) if lo <= hi else (ang >= lo) | (ang <= hi)

    def keepout_mask(self, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
        """Union of every asset's stand-off ring."""
        mask = np.zeros_like(xx, dtype=bool)
        for a in self.assets:
            r = np.hypot(xx - a.position_m[0], yy - a.position_m[1])
            mask |= r <= a.keepout_radius_m
        return mask


@dataclass
class CoverageResult:
    xx: np.ndarray
    yy: np.ndarray
    per_sensor: dict[str, np.ndarray]
    fused: np.ndarray
    area: ProtectedArea

    def gap_mask(self, pd_threshold: float = 0.9) -> np.ndarray:
        """Cells inside the protected sector that fail the Pd requirement."""
        inside = self.area.sector_mask(self.xx, self.yy)
        return inside & (self.fused < pd_threshold)

    def stats(self, pd_threshold: float = 0.9) -> dict[str, float]:
        inside = self.area.sector_mask(self.xx, self.yy)
        keep = self.area.keepout_mask(self.xx, self.yy) & inside
        gaps = self.gap_mask(pd_threshold)
        cell = (self.xx[0, 1] - self.xx[0, 0]) ** 2 / 1e6      # km^2
        return {
            "pd_threshold": pd_threshold,
            "covered_fraction": float((self.fused[inside] >= pd_threshold).mean()),
            "gap_area_km2": float(gaps.sum() * cell),
            "keepout_min_pd": float(self.fused[keep].min()) if keep.any() else float("nan"),
            "keepout_mean_pd": float(self.fused[keep].mean()) if keep.any() else float("nan"),
            "sector_mean_pd": float(self.fused[inside].mean()),
        }

    def asset_stats(self, pd_threshold: float = 0.9) -> list[dict]:
        """Per-asset verdict: does its stand-off ring meet the requirement?

        This is the row a customer actually reads - a sector-average Pd can
        look healthy while one specific asset is uncovered.
        """
        rows = []
        for a in self.area.assets:
            r = np.hypot(self.xx - a.position_m[0], self.yy - a.position_m[1])
            ring = r <= a.keepout_radius_m
            if not ring.any():
                continue
            pd_min = float(self.fused[ring].min())
            rows.append(
                {
                    "asset": a.name,
                    "position_m": a.position_m,
                    "keepout_radius_m": a.keepout_radius_m,
                    "min_pd": pd_min,
                    "mean_pd": float(self.fused[ring].mean()),
                    "meets_requirement": bool(pd_min >= pd_threshold),
                }
            )
        return rows


def compute_coverage(
    sensors: Sequence[SensorModel],
    area: ProtectedArea | None = None,
    rho: float = 0.0,
) -> CoverageResult:
    """Evaluate every sensor over the grid and fuse."""
    area = area or ProtectedArea()
    xx, yy = area.grid()
    per = {s.name: s.pd_on_grid(xx, yy) for s in sensors}
    layers = list(per.values())
    fused = fused_pd(layers) if rho <= 0.0 else fused_pd_correlated(layers, rho)
    return CoverageResult(xx=xx, yy=yy, per_sensor=per, fused=fused, area=area)


# ---------------------------------------------------------------- siting
def optimise_sites(
    sensor_factory: Callable[[tuple[float, float]], SensorModel],
    candidate_sites_m: Sequence[tuple[float, float]],
    n_select: int,
    area: ProtectedArea | None = None,
    fixed_sensors: Sequence[SensorModel] = (),
    pd_threshold: float = 0.9,
) -> dict:
    """Greedy maximum-coverage sensor siting.

    At each step, add the candidate site that most increases the fraction of
    the protected sector meeting `pd_threshold`. Greedy is not optimal, but
    maximum coverage is submodular, so it carries the standard
    (1 - 1/e) ~ 63% approximation guarantee - a defensible claim to make in
    front of an engineering audience.
    """
    area = area or ProtectedArea()
    xx, yy = area.grid()
    inside = area.sector_mask(xx, yy)

    base = [s.pd_on_grid(xx, yy) for s in fixed_sensors]
    chosen: list[tuple[float, float]] = []
    history: list[dict] = []
    remaining = list(candidate_sites_m)

    for step in range(n_select):
        best_site, best_score, best_grid = None, -1.0, None
        for site in remaining:
            grid = sensor_factory(site).pd_on_grid(xx, yy)
            score = float((fused_pd(base + [grid])[inside] >= pd_threshold).mean())
            if score > best_score:
                best_site, best_score, best_grid = site, score, grid
        if best_site is None:
            break
        base.append(best_grid)
        chosen.append(best_site)
        remaining.remove(best_site)
        history.append(
            {"step": step + 1, "site_m": best_site, "covered_fraction": best_score}
        )

    return {
        "selected_sites_m": chosen,
        "history": history,
        "final_covered_fraction": history[-1]["covered_fraction"] if history else 0.0,
    }


# ---------------------------------------------------------------- default
def default_layered_suite(
    rcs_m2: float = 0.01,
    target_alt_m: float = 60.0,
    atmosphere: prop.Atmosphere | None = None,
    sea_state: int = 2,
    radar_cfg: rad.RadarConfig | None = None,
) -> list[SensorModel]:
    """The four-layer suite used in the reference scenario."""
    cfg = radar_cfg or rad.RadarConfig()
    atmosphere = atmosphere or prop.Atmosphere()
    sea = prop.SeaState.from_state(sea_state)
    haze = 1.0 if atmosphere.rain_rate_mm_h < 1.0 else 0.55
    return [
        make_radar_sensor(cfg, rcs_m2, target_alt_m, atmosphere, sea),
        make_rf_sensor(),
        make_eo_ir_sensor(weather_derate=haze),
        make_acoustic_sensor(),
    ]
