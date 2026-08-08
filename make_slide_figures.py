"""
Slide-specific figures for the pitch deck.

Separate from run_demo.py on purpose: the demo figures are dense analysis
panels, while these are single-message graphics sized for a 13.3 x 7.5 in
slide. Both draw the numbers from the same modules, so they cannot disagree.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from cuas import microdoppler as md
from cuas import propagation as prop
from cuas import radar as rad
from cuas import scenarios as sc
from cuas import tracking as trk

HERE = Path(__file__).resolve().parent
OUT = HERE / "reports" / "slides"

INK = "#12263A"
DEEP = "#065A82"
TEAL = "#1C7293"
AMBER = "#E8871E"
RED = "#B23A48"
GREY = "#8899A6"

RCS = 0.01
ALT = 60.0
PD = 0.9
SEA_STATE = 3


def style(ax, title=None, xlabel=None, ylabel=None):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GREY)
    ax.tick_params(colors=INK, labelsize=11)
    ax.grid(alpha=0.22, color=GREY, lw=0.7)
    if title:
        ax.set_title(title, fontsize=14, color=INK, fontweight="bold", pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=12, color=INK)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=12, color=INK)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.savefig(p, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {p}")
    return p


# ------------------------------------------------------------------ 1
def fig_range_vs_rcs():
    """R proportional to sigma^(1/4): why low RCS is the whole problem."""
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    rcs = np.logspace(-3, 0.3, 160)
    marks = {}
    for f, colour, label in (
        (rad.RadarConfig.generic_surveillance, RED, "Existing coastal surveillance radar"),
        (rad.RadarConfig.cuas_staring, DEEP, "Dedicated C-UAS staring array"),
    ):
        cfg = f()
        r = np.array([rad.max_detection_range(cfg, s, PD) for s in rcs]) / 1000.0
        ax.loglog(rcs, r, lw=2.6, color=colour, label=label)
        marks[label] = (colour,
                        rad.max_detection_range(cfg, 0.01, PD) / 1000.0)

    ax.set_xlim(1e-3, 2.0)
    ax.set_ylim(1.0, 45.0)

    # Target-class markers along the top edge, clear of the curves.
    for s, name in ((0.01, "small quad"), (0.1, "large multirotor"),
                    (1.0, "tactical UAS")):
        ax.axvline(s, color=GREY, lw=0.8, ls=":")
        ax.annotate(f"{name}\n{s:g} m$^2$", (s, 42.0), fontsize=9.5,
                    color=GREY, ha="center", va="top")

    # Call out the driving case on both curves.
    for label, (colour, km) in marks.items():
        ax.scatter([0.01], [km], s=70, color=colour, zorder=5,
                   edgecolor="white", linewidth=1.4)
        ax.annotate(f"{km:.2f} km", (0.01, km), textcoords="offset points",
                    xytext=(12, -3), fontsize=12, color=colour,
                    fontweight="bold")

    style(ax, "Detection range scales only as $\\sigma^{1/4}$",
          "Radar cross section $\\sigma$ (m$^2$)",
          "Max range at $P_d$ = 0.9 (km)")
    ax.legend(fontsize=11, loc="lower right", frameon=False)
    ax.text(0.03, 0.04,
            "2.9x more range for the same target\ncosts 18.5 dB of SNR.",
            transform=ax.transAxes, fontsize=11.5, color=INK, va="bottom",
            bbox=dict(boxstyle="round,pad=0.5", fc="#EEF4F8", ec="none"))
    return save(fig, "range_vs_rcs.png")


# ------------------------------------------------------------------ 2
def fig_multipath():
    """Sea-surface multipath: the maritime-specific effect."""
    cfg = rad.RadarConfig.cuas_staring()
    sea = prop.SeaState.from_state(SEA_STATE)
    r = np.linspace(200.0, 16_000.0, 1400)
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    for alt, colour in ((30.0, AMBER), (60.0, DEEP), (120.0, TEAL)):
        f = prop.two_ray_propagation_factor(
            r, cfg.antenna_height_m, alt, cfg.wavelength_m, sea, cfg.polarization)
        ax.plot(r / 1000, 40 * np.log10(np.maximum(f, 1e-3)), lw=2.0,
                color=colour, label=f"target altitude {alt:.0f} m")
    ax.axhline(0.0, color=INK, lw=1.4, ls="--", label="free-space model (no multipath)")
    ax.set_ylim(-32, 14)
    ax.set_xlim(0, 16)
    style(ax, f"Sea-surface multipath, {sea.name}",
          "Range (km)", "Two-way propagation factor $F^4$ (dB)")
    ax.legend(fontsize=11, loc="lower right", frameon=False)
    # Annotation goes top-left: at short range F^4 is deep in the nulls, so
    # that corner is empty, and it stays clear of the lower-right legend.
    ax.text(0.02, 0.97,
            "Up to +12 dB at a lobe peak, -20 dB in a null.\n"
            "Low-altitude detection is not monotonic in range —\n"
            "a free-space budget cannot represent this at all.",
            transform=ax.transAxes, fontsize=11, color=INK, va="top",
            bbox=dict(boxstyle="round,pad=0.5", fc="#FDF1E3", ec="none"))
    return save(fig, "multipath.png")


# ------------------------------------------------------------------ 3
def fig_signatures():
    """Quad vs bird spectrograms, common clipped scale."""
    rng = np.random.default_rng(11)
    fs, dur = 20_000.0, 0.5
    quad = md.RotorTarget(n_rotors=4, n_blades=2, blade_len_m=0.12, rpm=6000.0)
    bird = md.BirdTarget(flap_rate_hz=4.0)
    _t, sq = md.synth_rotor(quad, fs=fs, duration_s=dur, snr_db=20.0, rng=rng)
    _t, sb = md.synth_bird(bird, fs=fs, duration_s=dur, snr_db=20.0, rng=rng)
    tip = md.theoretical_tip_doppler_hz(quad)
    lim = tip * 1.6

    specs = {}
    for k, s in (("quad", sq), ("bird", sb)):
        f, t, sdb = md.stft_spectrogram(s, fs, nperseg=512)
        m = np.abs(f) <= lim
        specs[k] = (t, f[m], sdb[m, :])
    vmax = max(s.max() for _, _, s in specs.values())

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharey=True)
    titles = (
        f"Quadcopter — rotor sidebands to $\\pm${tip:.0f} Hz",
        "Bird — narrow body line only",
    )
    for ax, key, title in zip(axes, ("quad", "bird"), titles):
        t, f, sdb = specs[key]
        ax.pcolormesh(t, f, sdb, shading="auto", cmap="turbo",
                      vmin=vmax - 45, vmax=vmax)
        ax.set_title(title, fontsize=13, color=INK, fontweight="bold", pad=10)
        ax.set_xlabel("Time (s)", fontsize=11, color=INK)
        ax.tick_params(colors=INK, labelsize=10)
    axes[0].set_ylabel("Doppler frequency (Hz)", fontsize=11, color=INK)
    fig.suptitle("Micro-Doppler is the discriminator: 23x difference in "
                 "Doppler extent",
                 fontsize=14, color=INK, fontweight="bold", y=1.03)
    fig.tight_layout()
    return save(fig, "signatures.png")


# ------------------------------------------------------------------ 4
def fig_tracking():
    """IMM vs single-model KF: track plus mode probabilities."""
    dt, sigma = 0.1, 4.0
    truth = trk.manoeuvring_track(dt=dt)
    rng = np.random.default_rng(3)
    meas = trk.add_measurement_noise(truth["pos"], sigma, rng)
    kf_x, _ = trk.KalmanFilterCV(dt=dt, sigma_meas=sigma).run(meas)
    imm = trk.IMMFilter(dt=dt, sigma_meas=sigma).run(meas)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    ax = axes[0]
    ax.scatter(meas[:, 0], meas[:, 1], s=7, alpha=0.28, color=GREY,
               label="noisy measurements")
    ax.plot(truth["pos"][:, 0], truth["pos"][:, 1], "--", color="#2C5F2D",
            lw=1.8, label="ground truth")
    ax.plot(kf_x[:, 0], kf_x[:, 3], color=RED, lw=1.8,
            label="single-model KF")
    ax.plot(imm["x"][:, 0], imm["x"][:, 3], color=DEEP, lw=2.2, label="IMM")
    style(ax, "Manoeuvring UAS track", "X (m)", "Y (m)")
    ax.legend(fontsize=10, frameon=False, loc="lower left")
    ax.set_aspect("equal", "datalim")

    ax = axes[1]
    ax.plot(truth["t"], imm["mode_prob"][:, 0], lw=2.2, color=TEAL,
            label="P(constant velocity)")
    ax.plot(truth["t"], imm["mode_prob"][:, 1], lw=2.2, color=AMBER,
            label="P(accelerating)")
    ax.axvspan(15.0, 22.0, color=AMBER, alpha=0.16, label="actual turn")
    # Headroom above P = 1 so the legend sits in empty space instead of on
    # top of the traces, which span the full 0..1 range.
    ax.set_ylim(-0.03, 1.42)
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    style(ax, "IMM mode probabilities = manoeuvre alarm",
          "Time (s)", "Mode probability")
    ax.legend(fontsize=9.5, frameon=False, loc="upper center", ncol=3,
              columnspacing=1.0, handlelength=1.5)
    fig.tight_layout()
    return save(fig, "tracking.png")


# ------------------------------------------------------------------ 5
#: Short axis labels for the candidate masts, so tick text does not collide.
_SITE_SHORT = {
    "Channel entrance mast": "Channel\nentrance",
    "Breakwater head (east)": "Breakwater\neast",
    "Breakwater head (west)": "Breakwater\nwest",
    "West perimeter": "West\nperimeter",
    "East perimeter": "East\nperimeter",
    "VTS tower": "VTS\ntower",
    "Container crane rail": "Crane\nrail",
    "LNG jetty mast": "LNG\njetty",
    "Silo roof": "Silo\nroof",
}


def fig_siting_gain(grid_n: int = 161):
    """Marginal coverage gain per added site - diminishing returns."""
    scenario = sc.damietta_style_port(sea_state=SEA_STATE)
    res = sc.optimise_radar_siting(scenario, rcs_m2=RCS, target_alt_m=ALT,
                                   pd_threshold=PD, n_select=5, grid_n=grid_n)
    hist = res["history"]
    cov = [h["covered_fraction"] * 100 for h in hist]
    marginal = [cov[0]] + [cov[i] - cov[i - 1] for i in range(1, len(cov))]

    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    x = np.arange(len(hist))
    ax.bar(x, marginal, color=[DEEP] + [TEAL] * (len(hist) - 1), width=0.6,
           label="marginal gain from this site")
    ax.plot(x, cov, "-o", color=AMBER, lw=2.4, ms=8,
            label="cumulative sector coverage")

    top = max(cov) * 1.30
    for i, (m, c) in enumerate(zip(marginal, cov)):
        # Marginal label inside the bar when it is tall enough to hold text,
        # just above it otherwise - avoids colliding with the cumulative line.
        if m > top * 0.10:
            ax.text(i, m * 0.5, f"+{m:.1f}", ha="center", va="center",
                    fontsize=11.5, color="white", fontweight="bold")
        else:
            ax.text(i, m + top * 0.015, f"+{m:.1f}", ha="center", va="bottom",
                    fontsize=10.5, color=INK, fontweight="bold")
        ax.annotate(f"{c:.1f}%", (i, c), textcoords="offset points",
                    xytext=(0, 11), ha="center", fontsize=11, color=AMBER,
                    fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([_SITE_SHORT.get(h["site"], h["site"]) for h in hist],
                       fontsize=10.5)
    style(ax, "Greedy mast selection: where the next sensor should go",
          None, "Sector coverage at $P_d \\geq$ 0.9 (%)")
    ax.legend(fontsize=11, frameon=False, loc="upper left",
              bbox_to_anchor=(0.0, 1.0))
    ax.set_ylim(0, top)
    return save(fig, "siting_gain.png"), hist


def main():
    print("writing slide figures:")
    fig_range_vs_rcs()
    fig_multipath()
    fig_signatures()
    fig_tracking()
    # grid_n matches run_demo.py's default so the deck and the demo log quote
    # identical coverage percentages.
    _p, hist = fig_siting_gain(grid_n=161)
    (OUT / "siting_sweep.json").write_text(
        json.dumps(hist, indent=2), encoding="utf-8")
    print(f"  {OUT / 'siting_sweep.json'}")


if __name__ == "__main__":
    main()
