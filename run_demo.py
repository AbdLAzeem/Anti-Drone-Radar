"""
Reference demonstration - the live run for the presentation.

Usage:
    python run_demo.py                 # full run (~3-5 min), figures to reports/
    python run_demo.py --quick         # coarse grid, small dataset (~1 min)
    python run_demo.py --rain 16 --sea-state 4    # degraded conditions

The narrative it produces, in order:

  1. A port's existing surveillance radar reaches ~3 km against a 0.01 m2
     target. That is the problem, quantified.
  2. A dedicated staring C-UAS radar reaches ~8.5 km - a 2.9x gain, from
     ~20 dB of SNR, because range only grows as SNR^(1/4).
  3. Micro-Doppler separates UAS from birds at 0% bird false-alarm rate,
     and still does so with the speed feature removed.
  4. An IMM tracker survives the manoeuvre a single-model filter cannot.
  5. Even the dedicated radar on the best single mast does not cover the
     port. Three optimally sited layered nodes do far better. That is the
     recommendation, and it comes out of the model rather than out of a
     brochure.

Every printed number is computed here. Figures and results.json land in
reports/ next to this file.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from cuas import classify as cl
from cuas import microdoppler as md
from cuas import propagation as prop
from cuas import radar as rad
from cuas import scenarios as sc
from cuas import system as sysmod
from cuas import tracking as trk

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
RULE = "=" * 72


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="C-UAS layered sensing demonstration")
    p.add_argument("--rain", type=float, default=0.0, help="rain rate mm/h")
    p.add_argument("--sea-state", type=int, default=3, help="Douglas sea state 0-5")
    p.add_argument("--rcs", type=float, default=0.01, help="target RCS m^2")
    p.add_argument("--alt", type=float, default=60.0, help="target altitude m")
    p.add_argument("--pd", type=float, default=0.9, help="required Pd")
    p.add_argument("--mc-runs", type=int, default=200, help="tracking Monte-Carlo runs")
    p.add_argument("--n-per-class", type=int, default=50, help="classifier samples/class")
    p.add_argument("--grid", type=int, default=161, help="coverage grid resolution")
    p.add_argument("--quick", action="store_true", help="fast reduced-fidelity run")
    a = p.parse_args()
    if a.quick:
        a.mc_runs, a.n_per_class, a.grid = 25, 20, 81
    return a


def header(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


# ------------------------------------------------------------------ layer 1
def layer1(args, atmos: prop.Atmosphere) -> dict:
    header("LAYER 1 - DETECTION: what the low-RCS problem actually costs")
    baseline = rad.RadarConfig.generic_surveillance()
    dedicated = rad.RadarConfig.cuas_staring()
    out = {}

    for tag, cfg in (("baseline", baseline), ("dedicated", dedicated)):
        atten = atmos.one_way_db_per_km(cfg.freq_Hz)
        rows = rad.RangeBudget(cfg=cfg, pd_target=args.pd,
                               atten_dB_per_km=atten).table()
        snr_req = rad.albersheim_required_snr_db(args.pd, cfg.pfa, cfg.n_pulses)
        out[tag] = {"cfg": cfg, "rows": rows, "snr_req_db": snr_req,
                    "atten_db_km": atten}
        print(f"\n  {cfg.name}")
        print(f"    gain {cfg.gain_dBi:.0f} dBi | {cfg.n_pulses} pulses | "
              f"noise {rad.lin2db(cfg.noise_power_W*1e3):.1f} dBm | "
              f"required SNR {snr_req:+.2f} dB")
        for r in rows:
            if r["rcs_m2"] in (0.01, 0.1, 1.0):
                print(f"    {r['target']:38s} sigma={r['rcs_m2']:5.2f} m2 "
                      f"-> {r['range_with_atten_km']:6.2f} km")

    r_base = rad.max_detection_range(baseline, args.rcs, args.pd)
    r_ded = rad.max_detection_range(dedicated, args.rcs, args.pd)
    r_check = rad.max_range_classic(
        baseline, args.rcs, float(rad.db2lin(out["baseline"]["snr_req_db"]))
    )
    snr_gain = 40.0 * np.log10(r_ded / r_base)

    print(f"\n  At sigma = {args.rcs} m2:")
    print(f"    existing surveillance radar : {r_base/1000:5.2f} km")
    print(f"    dedicated C-UAS radar       : {r_ded/1000:5.2f} km  "
          f"({r_ded/r_base:.2f}x)")
    print(f"    that {r_ded/r_base:.2f}x in range costs {snr_gain:.1f} dB of SNR "
          f"- because R grows only as SNR^(1/4)")
    print(f"    validation: closed-form range equation gives "
          f"{r_check/1000:.2f} km vs {r_base/1000:.2f} km from the exact Pd "
          f"solve ({abs(r_check-r_base)/r_base*100:.1f}% agreement)")

    out["comparison"] = {
        "rcs_m2": args.rcs,
        "baseline_km": r_base / 1000, "dedicated_km": r_ded / 1000,
        "range_ratio": r_ded / r_base, "snr_gain_db": float(snr_gain),
        "closed_form_check_km": r_check / 1000,
    }
    return out


# ------------------------------------------------------------------ layer 2
def layer2(args) -> dict:
    header("LAYER 2 - CLASSIFICATION: micro-Doppler, UAS vs bird")
    rng = np.random.default_rng(11)
    fs, dur = 20_000.0, 0.5
    quad = md.RotorTarget(label="quadcopter", n_rotors=4, n_blades=2,
                          blade_len_m=0.12, rpm=6000.0)
    bird = md.BirdTarget(label="bird", flap_rate_hz=4.0)
    _t, sig_q = md.synth_rotor(quad, fs=fs, duration_s=dur, snr_db=20.0, rng=rng)
    _t, sig_b = md.synth_bird(bird, fs=fs, duration_s=dur, snr_db=20.0, rng=rng)
    feat_q, feat_b = md.extract_features(sig_q, fs), md.extract_features(sig_b, fs)
    tip = md.theoretical_tip_doppler_hz(quad)

    print(f"\n  Analytic check on the synthesis:")
    print(f"    blade-tip Doppler   : {tip:.0f} Hz analytic -> expect ~"
          f"{2*tip:.0f} Hz two-sided extent, measured {feat_q['bw_99']:.0f} Hz "
          f"({feat_q['bw_99']/(2*tip)*100:.0f}% - the 99%-energy cut trims the "
          f"weakest tip returns)")
    print(f"    blade-passage rate  : {quad.blade_rate_hz:.0f} Hz analytic - "
          f"NOT recovered as a measured quantity; see limitations. The "
          f"envelope\n                          modulation line "
          f"({feat_q['env_mod_peak_hz']:.0f} Hz for the quad vs "
          f"{feat_b['env_mod_peak_hz']:.0f} Hz for the bird) is used as a "
          f"descriptor instead.")
    print(f"\n  {'feature':20s} {'quadcopter':>13s} {'bird':>13s} {'ratio':>9s}")
    for k in md.FEATURE_NAMES:
        ratio = feat_q[k] / feat_b[k] if abs(feat_b[k]) > 1e-9 else float("inf")
        print(f"  {k:20s} {feat_q[k]:13.3f} {feat_b[k]:13.3f} {ratio:9.2f}")

    print(f"\n  Training a classifier on {args.n_per_class} randomised samples "
          f"per class, SNR 8-30 dB ...")
    t0 = time.time()
    ds = cl.build_dataset(n_per_class=args.n_per_class, seed=1)
    reps = cl.evaluate_with_ablation(ds)
    imp = cl.feature_importance(ds)
    print(f"  dataset {ds.X.shape[0]} samples x {ds.X.shape[1]} features "
          f"({time.time()-t0:.0f} s)")

    for tag, r in reps.items():
        note = ("all features" if not r.excluded_features
                else f"speed feature removed: {', '.join(r.excluded_features)}")
        print(f"\n  --- {tag}  ({note})")
        print(f"    {r.n_folds}-fold cross-validated accuracy : {r.accuracy*100:.1f}%")
        print(f"    UAS-vs-bird AUC                     : {r.uas_vs_bird_auc:.4f}")
        op = r.operating_point
        print(f"    at {op['achieved_detection_rate']*100:.0f}% UAS detection, "
              f"bird false-alarm rate = {op['false_alarm_rate_on_birds']*100:.1f}%")
        print(f"    per-class recall : "
              + ", ".join(f"{k} {v*100:.0f}%" for k, v in r.per_class_recall.items()))

    print(f"\n  Permutation importance (what carries the decision):")
    for r in imp:
        print(f"    {r['feature']:20s} {r['importance']:+.4f}")
    drop = (reps["all_features"].accuracy
            - reps["signature_only"].accuracy) * 100.0
    print(f"\n  The top feature is a rotor-modulation descriptor, not bulk "
          f"speed, and removing\n  the speed feature costs only {drop:.1f} "
          f"accuracy points - so the result rests on\n  the micro-Doppler "
          f"signature rather than on how fast the target happens to fly.")

    return {"sig_quad": sig_q, "sig_bird": sig_b, "fs": fs,
            "feat_quad": feat_q, "feat_bird": feat_b, "tip_doppler_hz": tip,
            "blade_rate_hz": quad.blade_rate_hz, "reports": reps,
            "importance": imp, "dataset": ds}


# ------------------------------------------------------------------ layer 3
def layer3(args) -> dict:
    header("LAYER 3 - TRACKING: filter consistency under manoeuvre")
    dt, sigma = 0.1, 4.0
    truth = trk.manoeuvring_track(dt=dt)
    rng = np.random.default_rng(3)
    meas = trk.add_measurement_noise(truth["pos"], sigma, rng)
    kf_x, kf_p = trk.KalmanFilterCV(dt=dt, sigma_meas=sigma).run(meas)
    imm = trk.IMMFilter(dt=dt, sigma_meas=sigma).run(meas)
    summary = trk.monte_carlo_compare(n_runs=args.mc_runs, sigma_meas=sigma, dt=dt)

    print(f"\n  scenario: 18 m/s transit, 25 deg/s turn at t = 15-22 s")
    print(f"  measurement sigma {sigma:.1f} m, dt {dt:.2f} s, "
          f"{args.mc_runs} Monte-Carlo runs\n")
    print(f"  {'filter':10s} {'position RMSE':>20s} {'mean NEES':>11s} "
          f"{'target':>8s} {'verdict':>14s}")
    for name, s in summary.items():
        ok = "consistent" if s["nees_mean"] < 2.5 * s["nees_target"] else "OVER-CONFIDENT"
        print(f"  {name:10s} {s['rmse_mean_m']:11.2f} +/- {s['rmse_std_m']:4.2f} m "
              f"{s['nees_mean']:11.2f} {s['nees_target']:8.1f} {ok:>14s}")
    gain = ((summary["KF-CV"]["rmse_mean_m"] - summary["IMM"]["rmse_mean_m"])
            / summary["KF-CV"]["rmse_mean_m"] * 100.0)
    ratio = summary["KF-CV"]["nees_mean"] / summary["KF-CV"]["nees_target"]
    print(f"\n  IMM cuts position RMSE by {gain:.1f}%. The NEES column matters "
          f"more: the\n  single-model filter is ~{ratio:.0f}x over-confident during "
          f"the turn - it reports a\n  covariance far smaller than its real error, "
          f"which is how trackers lose targets.")
    return {"truth": truth, "meas": meas, "kf_x": kf_x, "kf_p": kf_p,
            "imm": imm, "summary": summary, "gain_pct": gain,
            "nees_ratio": float(ratio)}


# ------------------------------------------------------------------ layer 4
def layer4(args, atmos: prop.Atmosphere) -> dict:
    header("LAYER 4 - SYSTEM: can the port actually be covered?")
    scenario = sc.damietta_style_port(sea_state=args.sea_state)
    print(f"\n  {scenario.name}")
    print(f"  {scenario.description}")
    print(f"  threat sector {scenario.threat_sector_deg[0]:.0f}-"
          f"{scenario.threat_sector_deg[1]:.0f} deg (seaward), "
          f"{len(scenario.assets)} critical assets, "
          f"{len(scenario.candidate_sites)} candidate masts")
    print(f"  conditions: sea state {args.sea_state}, {atmos.name}, "
          f"sigma {args.rcs} m2 at {args.alt:.0f} m\n  computing ...")

    t0 = time.time()
    comp = sc.baseline_vs_dedicated(
        scenario, rcs_m2=args.rcs, target_alt_m=args.alt, atmosphere=atmos,
        pd_threshold=args.pd, grid_n=args.grid,
    )
    print(f"  ({time.time()-t0:.0f} s, {args.grid}x{args.grid} grid)\n")

    print(f"  {'configuration':42s} {'sector covered':>14s} {'gap area':>12s} "
          f"{'assets held':>12s}")
    for key in ("A_baseline", "B_dedicated_single", "C_layered_multi"):
        blk = comp[key]
        held = sum(1 for a in blk["assets"] if a["meets_requirement"])
        print(f"  {blk['label']:42s} {blk['stats']['covered_fraction']*100:13.1f}% "
              f"{blk['stats']['gap_area_km2']:8.0f} km2 "
              f"{held:8d}/{len(blk['assets'])}")

    print(f"\n  Greedy mast selection (each step adds the site that gains most "
          f"coverage):")
    for h in comp["siting"]["history"]:
        print(f"    {h['step']}. {h['site']:26s} h={h['height_m']:4.0f} m  "
              f"-> {h['covered_fraction']*100:5.1f}% covered, "
              f"min Pd on asset rings {h['min_pd_on_asset_rings']:.3f}")
    hist = comp["siting"]["history"]
    if len(hist) >= 2:
        gains = [hist[0]["covered_fraction"]] + [
            hist[i]["covered_fraction"] - hist[i - 1]["covered_fraction"]
            for i in range(1, len(hist))
        ]
        print(f"    marginal gains: "
              + " -> ".join(f"{g*100:+.1f}%" for g in gains)
              + "  (diminishing, as maximum-coverage submodularity predicts)")

    print(f"\n  Per-asset verdict for the recommended layout:")
    for a in comp["C_layered_multi"]["assets"]:
        flag = "OK " if a["meets_requirement"] else "GAP"
        print(f"    [{flag}] {a['asset']:22s} min Pd over its "
              f"{a['keepout_radius_m']/1000:.1f} km ring = {a['min_pd']:.3f}")

    return {"scenario": scenario, "comparison": comp}


# ------------------------------------------------------------------ figures
def fig_layers(args, l1, l2, l3) -> Path:
    cfg = l1["dedicated"]["cfg"]
    sea = prop.SeaState.from_state(args.sea_state)
    fig = plt.figure(figsize=(16, 13))
    fig.suptitle(
        f"C-UAS layered sensing - physics-derived performance  "
        f"($\\sigma$={args.rcs} m$^2$, alt {args.alt:.0f} m, "
        f"sea state {args.sea_state})",
        fontsize=13, fontweight="bold",
    )

    # 1. baseline vs dedicated Pd(r)
    ax = fig.add_subplot(3, 2, 1)
    r = np.linspace(100.0, 20_000.0, 800)
    for tag, colour in (("baseline", "#c0392b"), ("dedicated", "#1f4e79")):
        c = l1[tag]["cfg"]
        f_mp = prop.two_ray_propagation_factor(
            r, c.antenna_height_m, args.alt, c.wavelength_m, sea, c.polarization)
        snr = rad.snr_single_pulse(c, args.rcs, r, f_mp,
                                  l1[tag]["atten_db_km"] * r / 1000.0)
        ax.plot(r / 1000, rad.probability_of_detection(snr, c.pfa, c.n_pulses),
                lw=2.0, color=colour,
                label=f"{'existing surveillance' if tag=='baseline' else 'dedicated C-UAS'}"
                      f"  ({l1['comparison'][tag+'_km']:.1f} km)")
    ax.axhline(args.pd, color="grey", lw=0.9, ls="-.", label=f"required $P_d$={args.pd}")
    ax.set_xlabel("Range (km)"); ax.set_ylabel("$P_d$")
    ax.set_title(f"Layer 1 - the low-RCS problem\n"
                 f"{l1['comparison']['range_ratio']:.1f}x range needs "
                 f"{l1['comparison']['snr_gain_db']:.0f} dB, since "
                 f"$R\\propto$SNR$^{{1/4}}$", fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.set_ylim(-0.02, 1.05)

    # 2. multipath
    ax = fig.add_subplot(3, 2, 2)
    for alt in (30.0, 60.0, 120.0):
        f_mp = prop.two_ray_propagation_factor(
            r, cfg.antenna_height_m, alt, cfg.wavelength_m, sea, cfg.polarization)
        ax.plot(r / 1000, 40 * np.log10(np.maximum(f_mp, 1e-3)), lw=1.4,
                label=f"target alt {alt:.0f} m")
    ax.axhline(0.0, color="k", lw=0.9, ls="--", label="free space")
    ax.set_xlabel("Range (km)"); ax.set_ylabel("$F^4$ (dB, two-way)")
    ax.set_title(f"Maritime propagation, {sea.name}\n"
                 "sea multipath makes low-altitude detection non-monotonic",
                 fontsize=10)
    ax.set_ylim(-40, 15); ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # 3/4. spectrograms, common clipped dB scale
    lim = min(6000.0, l2["tip_doppler_hz"] * 1.6)
    specs = {}
    for key, sig in (("quad", l2["sig_quad"]), ("bird", l2["sig_bird"])):
        f_sp, t_sp, s_db = md.stft_spectrogram(sig, l2["fs"], nperseg=512)
        m = np.abs(f_sp) <= lim
        specs[key] = (t_sp, f_sp[m], s_db[m, :])
    vmax = max(s.max() for _, _, s in specs.values())
    vmin = vmax - 45.0
    for idx, (key, title) in enumerate(
        (("quad", f"Layer 2 - quadcopter: blade rate {l2['blade_rate_hz']:.0f} Hz, "
                  f"tip Doppler {l2['tip_doppler_hz']:.0f} Hz"),
         ("bird", f"Layer 2 - bird: Doppler extent "
                  f"{l2['feat_bird']['bw_99']:.0f} Hz vs "
                  f"{l2['feat_quad']['bw_99']:.0f} Hz for the quad")), start=3
    ):
        ax = fig.add_subplot(3, 2, idx)
        t_sp, f_c, s_c = specs[key]
        ax.pcolormesh(t_sp, f_c, s_c, shading="auto", cmap="turbo",
                      vmin=vmin, vmax=vmax)
        ax.set_xlabel("Time (s)"); ax.set_ylabel("Doppler (Hz)")
        ax.set_title(title, fontsize=10)

    # 5. tracking
    ax = fig.add_subplot(3, 2, 5)
    truth, meas = l3["truth"], l3["meas"]
    ax.scatter(meas[:, 0], meas[:, 1], s=6, alpha=0.3, color="grey",
               label="measurements")
    ax.plot(truth["pos"][:, 0], truth["pos"][:, 1], "--", color="green", lw=1.6,
            label="ground truth")
    ax.plot(l3["kf_x"][:, 0], l3["kf_x"][:, 3], color="#c0392b", lw=1.4,
            label=f"KF-CV  RMSE {l3['summary']['KF-CV']['rmse_mean_m']:.1f} m, "
                  f"NEES {l3['summary']['KF-CV']['nees_mean']:.0f}")
    ax.plot(l3["imm"]["x"][:, 0], l3["imm"]["x"][:, 3], color="#1f4e79", lw=1.8,
            label=f"IMM    RMSE {l3['summary']['IMM']['rmse_mean_m']:.1f} m, "
                  f"NEES {l3['summary']['IMM']['nees_mean']:.1f}")
    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")
    ax.set_title(f"Layer 3 - manoeuvring target: IMM cuts RMSE "
                 f"{l3['gain_pct']:.0f}%, and stays consistent", fontsize=10)
    ax.legend(fontsize=7); ax.grid(alpha=0.3); ax.set_aspect("equal", "datalim")

    # 6. IMM mode probabilities - the manoeuvre detector
    ax = fig.add_subplot(3, 2, 6)
    t = truth["t"]
    mp = l3["imm"]["mode_prob"]
    ax.plot(t, mp[:, 0], lw=1.6, label="P(constant velocity)")
    ax.plot(t, mp[:, 1], lw=1.6, label="P(accelerating)")
    ax.axvspan(15.0, 22.0, color="orange", alpha=0.18, label="actual turn")
    ax.set_xlabel("Time (s)"); ax.set_ylabel("mode probability")
    ax.set_title("IMM mode probabilities - a usable manoeuvre alarm,\n"
                 "not just a smoother track", fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.set_ylim(-0.02, 1.05)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    p = REPORTS / "layers_overview.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_classifier(l2) -> Path:
    reps, imp = l2["reports"], l2["importance"]
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.2))
    fig.suptitle("Layer 2 - trained classifier, cross-validated "
                 "(no number from training data)", fontsize=12,
                 fontweight="bold")

    r = reps["signature_only"]
    ax = axes[0]
    cm = r.confusion
    cmn = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    im = ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(r.class_names)), r.class_names, rotation=20)
    ax.set_yticks(range(len(r.class_names)), r.class_names)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, f"{cm[i,j]}\n{cmn[i,j]*100:.0f}%", ha="center",
                    va="center", fontsize=9,
                    color="white" if cmn[i, j] > 0.55 else "black")
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Confusion matrix, signature features only\n"
                 f"accuracy {r.accuracy*100:.1f}%  "
                 f"(bird recall {r.per_class_recall['bird']*100:.0f}%)",
                 fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046)

    ax = axes[1]
    for tag, style in (("all_features", "-"), ("signature_only", "--")):
        rr = reps[tag]
        ax.plot(rr.roc_fpr, rr.roc_tpr, style, lw=2.0,
                label=f"{tag.replace('_',' ')}  AUC {rr.uas_vs_bird_auc:.4f}")
    op = reps["signature_only"].operating_point
    ax.scatter([op["false_alarm_rate_on_birds"]], [op["achieved_detection_rate"]],
               s=110, color="red", zorder=5, marker="o",
               label=f"operating point: {op['achieved_detection_rate']*100:.0f}% "
                     f"detection @ {op['false_alarm_rate_on_birds']*100:.1f}% "
                     f"bird FAR")
    ax.plot([0, 1], [0, 1], ":", color="grey", lw=1.0)
    ax.set_xlabel("false-alarm rate on birds"); ax.set_ylabel("UAS detection rate")
    ax.set_title("ROC - the question that matters:\nUAS vs bird", fontsize=10)
    ax.legend(fontsize=8, loc="lower right"); ax.grid(alpha=0.3)

    ax = axes[2]
    names = [d["feature"] for d in imp][::-1]
    vals = [d["importance"] for d in imp][::-1]
    errs = [d["std"] for d in imp][::-1]
    colours = ["#c0392b" if n in cl.SPEED_FEATURES else "#1f4e79" for n in names]
    ax.barh(names, vals, xerr=errs, color=colours)
    ax.set_xlabel("permutation importance (accuracy drop)")
    ax.set_title("What carries the decision\n"
                 "red = bulk speed, blue = signature", fontsize=10)
    ax.grid(alpha=0.3, axis="x")

    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = REPORTS / "classifier.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_coverage(args, l4) -> Path:
    comp, scenario = l4["comparison"], l4["scenario"]
    area = comp["area"]
    keys = ("A_baseline", "B_dedicated_single", "C_layered_multi")
    fig, axes = plt.subplots(1, 3, figsize=(18.5, 6.4))
    fig.suptitle(f"{scenario.name}  -  fused $P_d$ over the seaward approach "
                 f"($\\sigma$={args.rcs} m$^2$, alt {args.alt:.0f} m, "
                 f"sea state {args.sea_state})",
                 fontsize=12, fontweight="bold")

    for ax, key in zip(axes, keys):
        blk = comp[key]
        cov = blk["coverage"]
        pm = ax.pcolormesh(cov.xx / 1000, cov.yy / 1000, cov.fused,
                           shading="auto", cmap="viridis", vmin=0, vmax=1)
        ax.contour(cov.xx / 1000, cov.yy / 1000, cov.fused, levels=[args.pd],
                   colors="red", linewidths=1.8)
        ax.axhline(scenario.coastline_y_m / 1000, color="white", lw=1.2, ls="-",
                   alpha=0.7)
        for a in area.assets:
            th = np.linspace(0, 2 * np.pi, 120)
            ax.plot(a.position_m[0] / 1000 + a.keepout_radius_m / 1000 * np.cos(th),
                    a.position_m[1] / 1000 + a.keepout_radius_m / 1000 * np.sin(th),
                    "w--", lw=1.0, alpha=0.85)
            ax.scatter([a.position_m[0] / 1000], [a.position_m[1] / 1000],
                       marker="*", s=110, color="white", edgecolor="black",
                       zorder=5)
        sites = blk.get("sites") or [comp["best_mast"]]
        for i, s in enumerate(sites):
            ax.scatter([s.position_m[0] / 1000], [s.position_m[1] / 1000],
                       marker="^", s=150, color="#ff7f0e", edgecolor="black",
                       zorder=6, label="sensor site" if i == 0 else None)
        held = sum(1 for a in blk["assets"] if a["meets_requirement"])
        ax.set_title(f"{blk['label']}\n"
                     f"{blk['stats']['covered_fraction']*100:.1f}% of sector at "
                     f"$P_d\\geq${args.pd} | {held}/{len(blk['assets'])} assets held",
                     fontsize=10)
        ax.set_xlabel("East (km)")
        ax.set_aspect("equal")
        ax.legend(fontsize=8, loc="lower right")
    axes[0].set_ylabel("North (km)   ->  open sea")
    fig.colorbar(pm, ax=axes, label="fused $P_d$", fraction=0.02, pad=0.01)

    p = REPORTS / "coverage_comparison.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


# ------------------------------------------------------------------ main
def main() -> None:
    args = parse_args()
    t_start = time.time()
    atmos = prop.Atmosphere(
        rain_rate_mm_h=args.rain,
        name="clear air" if args.rain <= 0 else f"rain {args.rain:.0f} mm/h",
    )
    REPORTS.mkdir(parents=True, exist_ok=True)

    l1 = layer1(args, atmos)
    l2 = layer2(args)
    l3 = layer3(args)
    l4 = layer4(args, atmos)

    figs = [fig_layers(args, l1, l2, l3), fig_classifier(l2),
            fig_coverage(args, l4)]

    comp = l4["comparison"]
    results = {
        "conditions": {"rcs_m2": args.rcs, "altitude_m": args.alt,
                       "sea_state": args.sea_state, "rain_mm_h": args.rain,
                       "required_pd": args.pd},
        "layer1_detection": {
            "comparison": l1["comparison"],
            "baseline_config": l1["baseline"]["cfg"].summary(),
            "dedicated_config": l1["dedicated"]["cfg"].summary(),
            "baseline_range_table": l1["baseline"]["rows"],
            "dedicated_range_table": l1["dedicated"]["rows"],
        },
        "layer2_classification": {
            "blade_rate_hz": l2["blade_rate_hz"],
            "tip_doppler_hz": l2["tip_doppler_hz"],
            "features_quad": l2["feat_quad"],
            "features_bird": l2["feat_bird"],
            "importance": l2["importance"],
            **{
                tag: {
                    "accuracy": r.accuracy,
                    "auc_uas_vs_bird": r.uas_vs_bird_auc,
                    "per_class_recall": r.per_class_recall,
                    "operating_point": r.operating_point,
                    "accuracy_by_snr": r.accuracy_by_snr,
                    "confusion": r.confusion.tolist(),
                    "excluded_features": list(r.excluded_features),
                    "n_samples": r.n_samples,
                }
                for tag, r in l2["reports"].items()
            },
        },
        "layer3_tracking": {**l3["summary"],
                            "imm_rmse_gain_pct": l3["gain_pct"],
                            "kf_nees_overconfidence_ratio": l3["nees_ratio"]},
        "layer4_system": {
            "scenario": l4["scenario"].name,
            "configurations": {
                k: {"label": comp[k]["label"], "stats": comp[k]["stats"],
                    "assets": comp[k]["assets"]}
                for k in ("A_baseline", "B_dedicated_single", "C_layered_multi")
            },
            "siting_history": comp["siting"]["history"],
            "recommended_sites": [
                {"name": s.name, "position_m": s.position_m,
                 "height_m": s.height_m, "notes": s.notes}
                for s in comp["C_layered_multi"]["sites"]
            ],
        },
    }
    jpath = REPORTS / "results.json"
    jpath.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    header("ARTEFACTS")
    for p in figs + [jpath]:
        print(f"  {p}")
    print(f"\n  total runtime {time.time()-t_start:.0f} s\n")


if __name__ == "__main__":
    main()
