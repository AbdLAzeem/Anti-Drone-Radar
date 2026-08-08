# Engineering notes

Design decisions, corrections and validation detail behind the framework.
The front page is [../README.md](../README.md); this document is the record of
*why* the code looks the way it does and what was found wrong along the way.

**Scope boundary.** This package models *sensing* only — detection,
classification and tracking performance. It contains no effector, jamming or
intercept parameters, by design.

---

## What changed from the first prototype

It was a single 7 KB script demonstrating four equations. It has been replaced for five substantive reasons.

**1. The detection threshold was an assumed constant.**
`Pmin = 1e-13 W` had no derivation. It is now a receiver noise budget,
`kT_sB·F·L`, and detection probability comes from the exact distribution of
the square-law detector output rather than being assumed:

```
SNR(R) = Pt·G²·λ²·σ·F⁴ / ((4π)³·R⁴·kT_sB·F_n·L·L_atm(R))
Pd     = ncx2.sf(threshold, 2N, 2N·SNR)          # Swerling 0, exact
```

Cross-check on the current configuration: the closed-form range equation
gives **2.99 km** at σ = 0.01 m², the exact Pd solve gives **2.94 km** — a 2 %
agreement that validates both paths.

**2. The micro-Doppler model was physically wrong.**
The phase-modulation term was short by a factor of 2π, which collapsed the
spectrogram into static horizontal lines. The rotor is now built from
distributed point scatterers:

```
R_m,b(t) = R₀ + v_body·t + r_m·sin(ωt + φ_b)·cos(θ_el)
s(t)     = Σ_b Σ_m w_m · flash(t) · exp(−j4πR_m,b(t)/λ)
```

Validation: measured 99 %-energy Doppler extent **8320 Hz** against an
analytic blade-tip Doppler of **4616 Hz** — 90 % of the expected 2× two-sided
spread, the shortfall being the 99 %-energy cut trimming the weakest tip
returns. Bird extent is **352 Hz**, a **23.7×** separation.

Two further feature bugs were found and fixed while building the classifier,
both of which were suppressing real class separation:

- `bw_99` was computed on the raw mean spectrum, so at low SNR it measured
  the width of the **noise floor** (the whole band) rather than the signal.
  A robust median floor is now subtracted first.
- The modulation-rate feature was estimated from the spectrogram frame
  sequence, whose hop rate (~260 Hz) **aliases** any rate above ~130 Hz — and
  multirotor blade rates are 130–450 Hz. It is now taken from the full-rate
  amplitude envelope.

Fixing these moved cross-validated accuracy from 88 % to 94 % and the bird
false-alarm rate at 95 % detection from 64 % to 0 %.

**3. The layered Pd curves were hand-picked logistics.**
Each sensor's Pd(r) is now derived from a stated mechanism — radar from the
full chain above, RF from a downlink link budget, EO/IR from an
angular-resolution limit, acoustic from narrowband array processing against
ambient. The acoustic model in particular required array gain and analysis
bandwidth to be explicit; a naive broadband level-vs-ambient comparison
yields a 4 m detection range, which is simply the wrong model.

**4. There was no validation.**
One Kalman track on one noise realisation proves nothing. The tracking layer
now runs Monte-Carlo and reports filter consistency (results table in
[../README.md](../README.md#layer-3--fusion)).

The NEES column is the important one. A NEES of 107 against a target of 6
means the single-model filter is roughly 18× over-confident during the
manoeuvre — it reports a covariance far smaller than its actual error, which
is the standard mechanism by which real trackers lose targets. The IMM is
consistent and cuts RMSE 36 %.

Classification is likewise cross-validated (`cross_val_predict`), so every
prediction comes from a model that did not see that sample. No training-set
accuracy is reported anywhere.

**5. Maritime propagation was absent entirely.**
For a *port* study this was the largest omission. Sea-surface multipath
produces a lobed vertical coverage pattern worth roughly **+12 dB at a lobe
peak and −20 dB in a null** (two-way) — it makes low-altitude detection
non-monotonic in range. A free-space model cannot represent this, and it is
the dominant effect for a low-flying target over water.

Also fixed: the prototype wrote figures to a hard-coded absolute Linux path
and could not run on the target platform.

---

## Known limitations (stated, not hidden)

- **Fusion independence.** `Pd_sys = 1 − Π(1 − Pd_i)` assumes independent
  sensors. `fused_pd_correlated(ρ)` provides a conservative bound; weather
  presets handle common-mode degradation.
- **Swerling 1/3/4** are not implemented rather than approximated. Swerling 0
  and 2 bracket the realistic range for small UAS.
- **No ducting.** Evaporation ducts over warm sea can extend detection well
  beyond the 4/3-Earth horizon. Not modelled.
- **Blade-passage rate is not measured.** This one is worth stating plainly:
  no feature here recovers the blade rate as a physical quantity. Two
  estimators were built and **rejected rather than shipped** —
  a harmonic product spectrum (lands on integer multiples: 3× for a 2-blade
  rotor, 4× for the bird — the classic HPS octave error) and
  autocorrelation of the Doppler spectrum for HERM-line spacing (correct for
  a 3-blade rotor, 230 Hz measured vs 225 Hz analytic, but off by ~2.7× for
  2-blade rotors). The classifier therefore uses an honestly-named
  modulation descriptor, `env_mod_peak_hz`, which is strongly discriminative
  (1400 Hz vs 80 Hz) without asserting a rotor parameter. Recovering the
  blade rate properly needs a longer coherent record and is open work.
- **Geometry is plausible, not surveyed.** Asset and mast positions are a
  generic Mediterranean container-port layout at Damietta scale. Substituting
  surveyed positions is a data change, not a code change.
- **RCS values** are open-literature orders of magnitude. Real RCS is
  strongly aspect- and frequency-dependent.
- **Classifier is trained on synthetic data only.** Accuracy against real
  radar recordings is unknown and will be lower. The randomised-parameter,
  randomised-SNR dataset guards against fitting one fixed signature, but it
  cannot substitute for measured data.
- **No clutter, no false alarms, no data association** in the tracking layer.
  Sea clutter and multi-target association are the next realism step.

---

## References

Skolnik, *Introduction to Radar Systems*, 3rd ed. ·
Mahafza, *Radar Systems Analysis and Design Using MATLAB* ·
Blake, *Radar Range-Performance Analysis* ·
Albersheim, *Proc. IEEE* 69(7), 1981 ·
Bar-Shalom, Li & Kirubarajan, *Estimation with Applications to Tracking and
Navigation* ·
ITU-R P.676 (gaseous attenuation), ITU-R P.838-3 (rain)
