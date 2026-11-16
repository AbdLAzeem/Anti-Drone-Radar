# C-UAS Project: Resume Brief

> Load this file to continue. It carries the full context in compact form.
> Last updated: 2026-08-03 (end of week 1).

## Context
- **User**: bachelor grad project + PhD, Egyptian Military Technical College
  (المشروع أكاديمي عسكري رسمي). Also presenting this to a company.
- **Topic**: layered Counter-UAS concept protecting maritime ports (Damietta
  as the motivating case).
- **Company framing** (user's decision): pitch it as (a) a sellable engineering
  tool, (b) proof of technical competence, and (c) an ask for sponsorship /
  lab access. Demo delivered in week 1; weeks 2–3 plan in `docs/ROADMAP.md`.
- **Assistant boundary (keep respecting)**: educational / simulation level.
  Generic textbook parameters, physics, math, thesis structure. NO operational
  weapon specs: real jamming frequencies or waveforms, targeting or intercept
  timings, counter-countermeasure parameters. Those come from the supervisor /
  classified college labs. This boundary holds regardless of stated context;
  the artefact is what matters, not intent. It has not constrained the work:
  a sensing coverage study needs none of it.

## Current state: this is no longer one script

The original `cuas_sim.py` (7 KB, 4 equations) has been replaced by a package.

```
cuas/radar.py         Layer 1: noise budget, exact Pd (Marcum/Swerling),
                      Albersheim, range budgets, 2 radar presets
cuas/propagation.py   Sea-surface two-ray multipath, ITU-R gas + rain
                      attenuation, 4/3-Earth horizon
cuas/microdoppler.py  Layer 2: scatterer-based rotor + bird synthesis,
                      spectrogram features
cuas/classify.py      Layer 2b: dataset, SVM, cross-validated ROC/confusion,
                      speed-feature ablation, permutation importance
cuas/tracking.py      Layer 3: KF + IMM (CV/CA), RMSE + NEES, Monte-Carlo
cuas/system.py        Layer 4: physical per-sensor Pd, fusion, coverage maps,
                      greedy siting
cuas/scenarios.py     Port geometry, candidate masts, A/B/C comparison
run_demo.py           Single entry point, 114 s, writes reports/
make_slide_figures.py Slide-sized figures
make_deck.js          Pitch deck generator (pptxgenjs)
qa_deck.py            Deck geometry checks + PowerPoint render export
README.md             Repo front page - results, architecture, limits
docs/ENGINEERING_NOTES.md  What changed from the prototype, and why
docs/ROADMAP.md       Weeks 2–3 plan with definitions of done
CUAS_Layered_Sensing_Pitch.pptx    14-slide deck, speaker notes included
```

## Headline numbers (σ = 0.01 m², 60 m alt, sea state 3, clear air, Pd = 0.9)

| Layer | Result |
|---|---|
| 1 | Existing surveillance radar **2.95 km**; dedicated staring array **8.55 km**. The 2.89× costs **18.5 dB**: R ∝ SNR^(1/4). Closed form vs exact solve agree 1.2 %. |
| 2 | **94.0 %** CV accuracy; **93.3 %** with the speed feature removed; UAS-vs-bird AUC **0.9996**; **0 %** bird false alarms at 98 % detection; bird recall **100 %**. |
| 3 | KF-CV RMSE 4.57 m, mean NEES **106.8** vs target 6 → ~18× over-confident. IMM RMSE **2.94 m**, NEES **3.21**, consistent. |
| 4 | Sector covered at Pd ≥ 0.9: **A** 4.9 % (2/4 assets), **B** 30.3 % (4/4), **C** 54.5 % (4/4, 3 sites). Marginal siting gains +36.3 → +9.3 → +8.8 → +1.7 → +1.7. |

## Bugs found and fixed in week 1 (the credibility story)
1. `Pmin = 1e-13 W` was an assumed constant → replaced by `kTsB·F·L` with Pd
   from the exact detector distribution.
2. Micro-Doppler phase term short by **2π** → spectrogram was static lines.
   Replaced by a scatterer-based rotor model.
3. `bw_99` measured the **noise floor** at low SNR → robust median floor now
   subtracted first.
4. Modulation-rate feature **aliased** above ~130 Hz by the STFT hop, while
   multirotor blade rates are 130–450 Hz → now from the full-rate envelope.
5. No validation anywhere → Monte-Carlo RMSE + NEES, cross-validated
   classification with ablation.
6. hard-coded absolute Linux output path → the original
   script could not run on the user's machine at all.

Fixing 3 and 4 moved accuracy 88 % → 94 % and bird false-alarm rate at 95 %
detection 64 % → 0 %.

Also hit and worked around: `scipy.stats.ncx2` **segfaults** at large
non-centrality (short range, high SNR). `probability_of_detection` saturates
those cells to 1.0, which is exact to well beyond double precision.

## Open limitation to lead with
**Blade-passage rate is not measured as a physical quantity.** Two estimators
were built and rejected rather than shipped: harmonic product spectrum (lands
on integer multiples) and Doppler-spectrum autocorrelation (right for 3-blade,
~2.7× off for 2-blade). The classifier uses an honestly-named descriptor,
`env_mod_peak_hz`. This is roadmap item W1.

Other stated limits: synthetic data only; plausible not surveyed geometry;
independence assumed in fusion; no clutter or data association; no ducting.

## Environment notes
- Python **3.8.2** on Windows: the code uses `from __future__ import
  annotations` so PEP 604 style annotations work. Do not assume 3.10+.
- `numpy 1.23.5`, `scipy 1.10.1`, `matplotlib 3.6.0`, `sklearn 1.2.2`.
- No LibreOffice; **PowerPoint is installed**, so `qa_deck.py` exports slide
  PNGs via COM for visual QA.
- `pptxgenjs` installed locally via npm for the deck.

## To resume
"Continue the C-UAS project, here is the brief" + attach this file
(`docs/project_brief.md`). Then pick
an item from `docs/ROADMAP.md`; W1 (blade rate) and W6 (real data) carry the most
weight.
