# Development plan — weeks 2–3

Week 1 delivered a working, validated framework and a pitch. This is the
plan for the harder work, written so each item has a **definition of done**
that can be checked rather than asserted.

Items are ordered by *credibility gained per day*, not by difficulty. Two of
them (W1, W6) close limitations that are stated openly in the deck, so they
carry the most weight in front of a technical audience.

---

## Week 2 — close the stated gaps

### W1. Recover the blade-passage rate as a measured quantity
**Priority: highest.** This is the one limitation named on the "stated
limits" slide, so it will be the first thing a reviewer asks about.

Week 1 built and rejected two estimators:

| Attempt | Failure mode |
|---|---|
| Harmonic product spectrum on the envelope | Lands on integer multiples — 3× for the 2-blade rotor, 4× for the bird (classic HPS octave error) |
| Autocorrelation of the Doppler spectrum (HERM-line spacing) | Correct for a 3-blade rotor (230 Hz measured vs 225 Hz analytic) but off ~2.7× for 2-blade rotors |

The 3-blade success and the 2-blade failure point at the cause: for a
symmetric 2-blade rotor the flash pattern repeats twice per revolution, so
the spectral line structure is not simply spaced at the blade rate. Work:

- Derive the expected HERM line spacing analytically for `n_blades` = 2, 3, 4
  and check which physical period the spectrum actually carries.
- Lengthen the coherent record (0.5 s → 2 s) so the envelope spectrum
  resolves a 4 Hz fundamental with more than two periods.
- Replace argmax with a cepstral estimator plus a sub-harmonic penalty, or
  fit the whole comb rather than picking a peak.

**Done when:** estimated blade rate is within 10 % of analytic across
`n_blades` ∈ {2,3,4} and rpm ∈ [3000, 9000], as a `pytest` case with a
tolerance — not a printed number.

---

### W2. CNN benchmark against the feature SVM
The deck claims the classical pipeline is the right choice for synthetic
data. That claim needs a measured comparison, not an assertion.

- Small CNN on log-spectrogram patches, **identical cross-validation folds**
  as the SVM so the comparison is fair.
- Report both on the same axes, including accuracy-vs-SNR.
- Grad-CAM or occlusion on a few examples: if the CNN is attending to the
  sideband region, that supports the feature choice; if it is attending to
  the noise floor, the dataset has an artefact worth finding.

**Done when:** one figure and one table comparing SVM and CNN on the same
folds, with an explicit statement of which wins and why.

Expected result, stated in advance so it cannot be rationalised afterwards:
the CNN will match or slightly beat the SVM on synthetic data, and the
interesting finding will be whichever features the occlusion study
contradicts.

---

### W3. Sea clutter, false alarms and data association
The tracking layer currently receives one measurement per scan with no
clutter. That is the least realistic assumption in the whole framework.

- K-distributed sea clutter amplitude, with the CFAR threshold that follows
  from it; false alarms drawn at the resulting rate.
- Nearest-neighbour association with chi-square gating; then compare against
  probabilistic data association (PDA) under heavy clutter.
- New metrics: track purity, track continuity, time-to-first-confirmed-track,
  and false-track rate per hour.

**Done when:** RMSE and NEES are reported as a function of false-alarm
density, and the density at which the plain nearest-neighbour tracker breaks
down is identified numerically.

---

### W4. Unit tests and CI on every closed-form path
Currently correctness rests on cross-checks printed by the demo. Those
should be assertions that fail loudly.

- `radar.py`: closed-form vs numeric range solve agreement; Albersheim
  against exact Marcum Pd over a Pd/Pfa/N grid; Pd monotonic in SNR;
  saturation guard returns exactly 1.0 where the exact call would overflow.
- `propagation.py`: two-ray F against the analytic small-angle limit; horizon
  against hand-computed values; rain attenuation against ITU-R table points.
- `microdoppler.py`: measured Doppler extent vs analytic tip Doppler within
  tolerance; noise-floor subtraction actually invariant to added noise.
- `tracking.py`: KF reduces to the analytic steady state on a linear track;
  NEES of a correctly-tuned filter within the chi-square confidence band.
- `system.py`: fused Pd bounds (≥ max single sensor, ≤ 1); greedy siting
  coverage non-decreasing per step.

**Done when:** `pytest` green, and the demo's printed cross-checks are
replaced by test assertions.

---

## Week 3 — extend the scenario

### W5. Multi-target and degraded-weather scenarios as first-class cases
Currently weather is a command-line flag and there is one target.

- Swarm (N simultaneous), and a decoy-plus-penetrator case where a loud
  target masks a quiet one.
- Coverage recomputed per weather state, reported as a table of
  `covered_fraction` across clear / light rain / moderate rain / heavy rain
  × sea state 1–5, rather than one nominal figure.
- Correlated-degradation study: fog suppresses EO/IR while rain suppresses
  radar, so the independence assumption in the fusion is worst exactly when
  it matters. Quantify the gap between `fused_pd` and
  `fused_pd_correlated(ρ)` over that grid.

**Done when:** a single figure shows how the recommended 3-site layout
degrades across the weather grid, and the worst-case cell is named.

---

### W6. Real-data validation path
The framework has never seen a real radar recording, and no amount of
simulation fixes that. Even a *small* real dataset changes the character of
every claim.

Cheapest routes, in order of accessibility:

1. Public micro-Doppler datasets (several university radar groups publish
   drone/bird recordings) — feed them straight through
   `extract_features` and re-run the same cross-validation.
2. A low-cost 24 GHz CW radar module against a hobby drone: enough to test
   the micro-Doppler chain end to end, even if the range budget is not
   comparable.
3. Supervisor/company access to X-band recordings — the ideal, and the
   specific ask on the closing slide.

**Done when:** the confusion matrix is reported on real data alongside the
synthetic one, however much worse it looks. A worse number here is more
valuable than a better synthetic one.

---

### W7. Literature positioning
Needed for both the thesis and the pitch: the framework must be placed
against published work.

- Layered C-UAS coverage and sensor-placement studies.
- Micro-Doppler UAS classification benchmarks — record their reported
  accuracies and, more importantly, their dataset sizes and whether they
  cross-validate.
- Maritime propagation for low-altitude detection.

**Done when:** a comparison table showing where this work sits, including at
least two places where published results disagree with each other.

---

## Deliberately *not* in weeks 2–3

Stated so scope does not drift:

- **3-D / elevation coverage volumes** — a real gap, but it multiplies
  compute cost and every current conclusion holds at a fixed altitude slice.
- **Cost modelling alongside coverage** — high commercial value, but it needs
  price inputs only the company has.
- **Evaporation-duct propagation** — genuinely important over warm sea and
  genuinely hard; needs refractivity profile data.
- **Bistatic / passive geometries** — favour low-RCS detection and would be a
  strong research contribution, but they are a new detection model, not an
  extension of this one.
- **Any effector, jamming or intercept modelling** — outside the scope
  boundary held throughout, and not needed for a sensing coverage study.

---

## How progress will be reported

Same discipline as week 1: every claim traceable to a command.

- `python run_demo.py` stays the single entry point and must keep working.
- `pytest` must stay green.
- Each item above lands as a section in the README with its numbers, and any
  estimator that fails gets documented as a rejected attempt (as W1's two
  failures already are) rather than quietly dropped.

The rule that produced week 1's useful results: **a number that cannot be
checked against either an analytic limit or held-out data does not go in the
report.**
