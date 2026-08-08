"""
SCENARIOS
=========
Reference deployment geometries.

The layout below is a *generic Mediterranean container-port geometry*, sized
and oriented after Damietta as the motivating case: coastline running roughly
east-west, open sea to the north, terminals set back behind a breakwater, and
the navigation channel entering from the north-west.

All coordinates are local ENU metres relative to the main container terminal.
Nothing here is a survey product - it is a plausible layout at the right
scale, which is what a coverage study needs. Swapping in real surveyed asset
and mast positions is a data change, not a code change.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import propagation as prop
from . import radar as rad
from . import system as sysmod


@dataclass
class SiteOption:
    """A candidate mast/tower position with its usable height."""

    name: str
    position_m: tuple[float, float]
    height_m: float = 25.0
    notes: str = ""


@dataclass
class PortScenario:
    """A complete deployment case: assets, threat sector, candidate sites."""

    name: str
    assets: list[sysmod.Asset]
    candidate_sites: list[SiteOption]
    threat_sector_deg: tuple[float, float]
    extent_m: float = 15_000.0
    grid_n: int = 241
    coastline_y_m: float = 0.0
    sea_state: int = 3
    description: str = ""

    def protected_area(self, grid_n: int | None = None) -> sysmod.ProtectedArea:
        return sysmod.ProtectedArea(
            name=self.name,
            extent_m=self.extent_m,
            grid_n=grid_n or self.grid_n,
            sector_deg=self.threat_sector_deg,
            assets=self.assets,
        )


def damietta_style_port(sea_state: int = 3) -> PortScenario:
    """Generic Mediterranean container port, Damietta-scale.

    Threat sector is the seaward approach: 0-180 deg in ENU convention, i.e.
    everything north of the coastline. A UAS launched from a small boat
    offshore is the driving case, because it removes every land-side
    perimeter control the port already has.
    """
    assets = [
        sysmod.Asset("Container terminal", (0.0, 0.0), 1_200.0, priority=1),
        sysmod.Asset("LNG / fuel jetty", (3_200.0, 900.0), 1_500.0, priority=1),
        sysmod.Asset("Grain silos", (-2_600.0, -400.0), 800.0, priority=2),
        sysmod.Asset("Control tower / VTS", (600.0, 1_400.0), 600.0, priority=1),
    ]

    # Candidate masts: along the breakwater, on terminal cranes, and inland.
    candidate_sites = [
        SiteOption("Breakwater head (west)", (-3_800.0, 2_600.0), 22.0,
                   "exposed, best seaward look, hardest to power"),
        SiteOption("Breakwater head (east)", (4_600.0, 2_400.0), 22.0,
                   "covers the LNG jetty approach"),
        SiteOption("Channel entrance mast", (200.0, 3_100.0), 30.0,
                   "furthest seaward, dominates the approach lane"),
        SiteOption("Container crane rail", (300.0, 700.0), 45.0,
                   "high mast, existing power and fibre"),
        SiteOption("LNG jetty mast", (3_300.0, 1_500.0), 28.0,
                   "co-located with the highest-value asset"),
        SiteOption("Silo roof", (-2_600.0, 100.0), 40.0,
                   "good height, poor seaward horizon"),
        SiteOption("VTS tower", (600.0, 1_500.0), 55.0,
                   "highest available structure"),
        SiteOption("West perimeter", (-5_200.0, 300.0), 20.0,
                   "flank cover, cheap to install"),
        SiteOption("East perimeter", (6_000.0, 200.0), 20.0,
                   "flank cover"),
    ]

    return PortScenario(
        name="Damietta-scale Mediterranean container port (generic layout)",
        assets=assets,
        candidate_sites=candidate_sites,
        threat_sector_deg=(0.0, 180.0),
        extent_m=15_000.0,
        coastline_y_m=0.0,
        sea_state=sea_state,
        description=(
            "Seaward UAS approach against a working container port. Driving "
            "case is a small multirotor launched from a boat offshore, which "
            "bypasses land-side perimeter security entirely."
        ),
    )


# ------------------------------------------------------------------ suites
def build_suite_at_sites(
    sites: list[SiteOption],
    rcs_m2: float,
    target_alt_m: float,
    atmosphere: prop.Atmosphere,
    sea_state: int,
    radar_cfg_factory=rad.RadarConfig.cuas_staring,
    with_rf: bool = True,
    with_eo: bool = True,
    with_acoustic: bool = True,
) -> list[sysmod.SensorModel]:
    """Instantiate a full sensor suite at each of the given sites.

    Every radar inherits its site's mast height, so a taller mast genuinely
    buys horizon and shifts the multipath lobe pattern - the siting study is
    not just a 2-D translation of one identical footprint.
    """
    sea = prop.SeaState.from_state(sea_state)
    haze = 1.0 if atmosphere.rain_rate_mm_h < 1.0 else 0.55
    sensors: list[sysmod.SensorModel] = []

    for site in sites:
        cfg = radar_cfg_factory()
        cfg.antenna_height_m = site.height_m
        sensors.append(
            sysmod.make_radar_sensor(
                cfg, rcs_m2, target_alt_m, atmosphere, sea,
                position_m=site.position_m,
                name=f"Radar @ {site.name}",
            )
        )
        if with_rf:
            sensors.append(
                sysmod.make_rf_sensor(position_m=site.position_m,
                                      name=f"RF @ {site.name}")
            )
        if with_eo:
            sensors.append(
                sysmod.make_eo_ir_sensor(position_m=site.position_m,
                                         weather_derate=haze,
                                         name=f"EO/IR @ {site.name}")
            )
        if with_acoustic:
            sensors.append(
                sysmod.make_acoustic_sensor(position_m=site.position_m,
                                            name=f"Acoustic @ {site.name}")
            )
    return sensors


def baseline_vs_dedicated(
    scenario: PortScenario,
    rcs_m2: float = 0.01,
    target_alt_m: float = 60.0,
    atmosphere: prop.Atmosphere | None = None,
    pd_threshold: float = 0.9,
    grid_n: int | None = None,
) -> dict:
    """The core comparison for the pitch, in three steps.

    A. What the port already has: one general-purpose surveillance radar.
    B. One dedicated C-UAS staring radar on the best mast.
    C. Optimised multi-site dedicated suite.

    Reporting all three is what makes the recommendation credible: it shows
    the gap, shows that a better sensor alone does not close it, and shows
    what does.
    """
    atmosphere = atmosphere or prop.Atmosphere()
    area = scenario.protected_area(grid_n)
    best_mast = max(scenario.candidate_sites, key=lambda s: s.height_m)

    def _coverage(sensors):
        cov = sysmod.compute_coverage(sensors, area)
        return cov, cov.stats(pd_threshold)

    # --- A. existing surveillance radar, single site ---------------------
    suite_a = build_suite_at_sites(
        [best_mast], rcs_m2, target_alt_m, atmosphere, scenario.sea_state,
        radar_cfg_factory=rad.RadarConfig.generic_surveillance,
        with_rf=False, with_eo=False, with_acoustic=False,
    )
    cov_a, stats_a = _coverage(suite_a)

    # --- B. dedicated staring radar, same single site ---------------------
    suite_b = build_suite_at_sites(
        [best_mast], rcs_m2, target_alt_m, atmosphere, scenario.sea_state,
        radar_cfg_factory=rad.RadarConfig.cuas_staring,
        with_rf=False, with_eo=False, with_acoustic=False,
    )
    cov_b, stats_b = _coverage(suite_b)

    # --- C. optimised multi-site layered suite ---------------------------
    siting = optimise_radar_siting(
        scenario, rcs_m2, target_alt_m, atmosphere, pd_threshold,
        n_select=3, grid_n=grid_n,
    )
    chosen = siting["selected_sites"]
    suite_c = build_suite_at_sites(
        chosen, rcs_m2, target_alt_m, atmosphere, scenario.sea_state,
        radar_cfg_factory=rad.RadarConfig.cuas_staring,
    )
    cov_c, stats_c = _coverage(suite_c)

    return {
        "area": area,
        "best_mast": best_mast,
        "A_baseline": {"label": "A - existing surveillance radar (1 site)",
                       "coverage": cov_a, "stats": stats_a,
                       "assets": cov_a.asset_stats(pd_threshold)},
        "B_dedicated_single": {"label": "B - dedicated C-UAS radar (1 site)",
                               "coverage": cov_b, "stats": stats_b,
                               "assets": cov_b.asset_stats(pd_threshold)},
        "C_layered_multi": {"label": f"C - layered suite ({len(chosen)} sites)",
                            "coverage": cov_c, "stats": stats_c,
                            "assets": cov_c.asset_stats(pd_threshold),
                            "sites": chosen},
        "siting": siting,
    }


def optimise_radar_siting(
    scenario: PortScenario,
    rcs_m2: float = 0.01,
    target_alt_m: float = 60.0,
    atmosphere: prop.Atmosphere | None = None,
    pd_threshold: float = 0.9,
    n_select: int = 3,
    grid_n: int | None = None,
) -> dict:
    """Greedy selection of radar masts from the scenario's candidate list.

    Each candidate carries its own mast height, so the objective genuinely
    trades off height (horizon, lobe structure) against position (geometry).
    """
    atmosphere = atmosphere or prop.Atmosphere()
    area = scenario.protected_area(grid_n)
    sea = prop.SeaState.from_state(scenario.sea_state)
    xx, yy = area.grid()
    inside = area.sector_mask(xx, yy)
    ring = area.keepout_mask(xx, yy)

    def grid_for(site: SiteOption) -> np.ndarray:
        cfg = rad.RadarConfig.cuas_staring()
        cfg.antenna_height_m = site.height_m
        s = sysmod.make_radar_sensor(
            cfg, rcs_m2, target_alt_m, atmosphere, sea,
            position_m=site.position_m,
        )
        return s.pd_on_grid(xx, yy)

    grids = {s.name: grid_for(s) for s in scenario.candidate_sites}

    selected: list[SiteOption] = []
    accumulated: list[np.ndarray] = []
    history: list[dict] = []
    remaining = list(scenario.candidate_sites)

    for step in range(min(n_select, len(remaining))):
        best, best_score, best_ring = None, -1.0, 0.0
        for site in remaining:
            fused = sysmod.fused_pd(accumulated + [grids[site.name]])
            score = float((fused[inside] >= pd_threshold).mean())
            ring_min = float(fused[ring].min()) if ring.any() else 0.0
            # Primary objective is sector coverage; asset stand-off rings
            # break ties, since a covered average with an exposed asset is
            # not an acceptable answer.
            if (score, ring_min) > (best_score, best_ring):
                best, best_score, best_ring = site, score, ring_min
        if best is None:
            break
        accumulated.append(grids[best.name])
        selected.append(best)
        remaining.remove(best)
        history.append(
            {
                "step": step + 1,
                "site": best.name,
                "position_m": best.position_m,
                "height_m": best.height_m,
                "covered_fraction": best_score,
                "min_pd_on_asset_rings": best_ring,
            }
        )

    return {"selected_sites": selected, "history": history}
