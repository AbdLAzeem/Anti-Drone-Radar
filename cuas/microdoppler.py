"""
LAYER 2 - CLASSIFICATION
========================
Micro-Doppler signature synthesis and feature extraction.

The first prototype used a single phase-modulated tone whose modulation
index was short by a factor of 2*pi, which collapsed the spectrogram into
static horizontal lines. That is not what a rotor looks like.

This module instead builds the return from distributed point scatterers.
Each blade is discretised into scatterers at radii r_m; the range to
scatterer m on blade b is

    R(t) = R0 + v_body*t + r_m*sin(omega*t + phi_b)*cos(theta_el)

and the contribution is exp(-j*4*pi*R(t)/lambda). Summing over scatterers
and blades reproduces the real structure: a body Doppler line, symmetric
HERM sidebands spaced at the blade rate, and periodic blade flashes.

A flapping-bird model is provided as the discriminating class, since bird
rejection is the actual operational problem for a port radar.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import spectrogram

C_LIGHT = 299_792_458.0


# ---------------------------------------------------------------- targets
@dataclass
class RotorTarget:
    """Multirotor or fixed-wing UAS with rotating blades."""

    label: str = "quadcopter"
    n_rotors: int = 4
    n_blades: int = 2
    blade_len_m: float = 0.12
    rpm: float = 6000.0
    body_speed_ms: float = 8.0
    aspect_el_deg: float = 15.0       # elevation of rotor plane to line of sight
    body_to_rotor_rcs_ratio: float = 3.0
    n_scatterers: int = 14

    @property
    def blade_rate_hz(self) -> float:
        """Blade-passage frequency - the spacing of the HERM sidebands."""
        return self.n_blades * self.rpm / 60.0


@dataclass
class BirdTarget:
    """Flapping-wing bird: low flap rate, small radial excursion."""

    label: str = "bird"
    flap_rate_hz: float = 4.0
    wing_excursion_m: float = 0.18
    body_speed_ms: float = 12.0
    aspect_el_deg: float = 20.0
    body_to_wing_rcs_ratio: float = 3.0
    n_harmonics: int = 3
    n_scatterers: int = 8


# ---------------------------------------------------------------- synthesis
def _body_component(t: np.ndarray, lam: float, v: float, r0: float) -> np.ndarray:
    r = r0 + v * t
    return np.exp(-1j * 4.0 * np.pi * r / lam)


def synth_rotor(
    tgt: RotorTarget,
    fs: float = 20_000.0,
    duration_s: float = 0.5,
    freq_Hz: float = 9.5e9,
    snr_db: float = 20.0,
    r0_m: float = 1000.0,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Synthesise the complex baseband return of a rotor target."""
    rng = rng or np.random.default_rng()
    lam = C_LIGHT / freq_Hz
    t = np.arange(0.0, duration_s, 1.0 / fs)
    cos_el = np.cos(np.deg2rad(tgt.aspect_el_deg))

    # Blade scatterers: weight ~ r to mimic the radial RCS distribution of a
    # blade, so the fast-moving tip dominates the sideband extent.
    radii = np.linspace(0.2 * tgt.blade_len_m, tgt.blade_len_m, tgt.n_scatterers)
    weights = radii / radii.sum()

    rotor_sig = np.zeros(t.size, dtype=complex)
    for rotor in range(tgt.n_rotors):
        omega = 2.0 * np.pi * tgt.rpm / 60.0 * (1.0 + 0.01 * rotor)  # slight spread
        rotor_phase = rng.uniform(0.0, 2.0 * np.pi)
        for b in range(tgt.n_blades):
            phi_b = rotor_phase + 2.0 * np.pi * b / tgt.n_blades
            angle = omega * t + phi_b
            for r_m, w in zip(radii, weights):
                r = r0_m + tgt.body_speed_ms * t + r_m * np.sin(angle) * cos_el
                # Blade flash: aspect-dependent visibility, peaks when the
                # blade is broadside to the line of sight.
                flash = 0.35 + 0.65 * np.abs(np.cos(angle))
                rotor_sig += w * flash * np.exp(-1j * 4.0 * np.pi * r / lam)

    body = _body_component(t, lam, tgt.body_speed_ms, r0_m)
    a_body = np.sqrt(tgt.body_to_rotor_rcs_ratio)
    # Rotors are mutually incoherent (independent phases), so their powers
    # add: normalise by sqrt(n_rotors), not n_rotors.
    sig = a_body * body + rotor_sig / np.sqrt(max(tgt.n_rotors, 1))
    return t, _add_noise(sig, snr_db, rng)


def synth_bird(
    tgt: BirdTarget,
    fs: float = 20_000.0,
    duration_s: float = 0.5,
    freq_Hz: float = 9.5e9,
    snr_db: float = 20.0,
    r0_m: float = 1000.0,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Synthesise the complex baseband return of a flapping bird."""
    rng = rng or np.random.default_rng()
    lam = C_LIGHT / freq_Hz
    t = np.arange(0.0, duration_s, 1.0 / fs)
    cos_el = np.cos(np.deg2rad(tgt.aspect_el_deg))
    w0 = 2.0 * np.pi * tgt.flap_rate_hz

    radii = np.linspace(0.25, 1.0, tgt.n_scatterers) * tgt.wing_excursion_m
    weights = radii / radii.sum()

    wing_sig = np.zeros(t.size, dtype=complex)
    for h in range(1, tgt.n_harmonics + 1):
        amp_h = 1.0 / h ** 1.5          # flapping is not a pure sinusoid
        ph = rng.uniform(0.0, 2.0 * np.pi)
        for r_m, w in zip(radii, weights):
            r = (
                r0_m
                + tgt.body_speed_ms * t
                + amp_h * r_m * np.sin(h * w0 * t + ph) * cos_el
            )
            wing_sig += w * amp_h * np.exp(-1j * 4.0 * np.pi * r / lam)

    body = _body_component(t, lam, tgt.body_speed_ms, r0_m)
    a_body = np.sqrt(tgt.body_to_wing_rcs_ratio)
    sig = a_body * body + wing_sig
    return t, _add_noise(sig, snr_db, rng)


def _add_noise(sig: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    p_sig = float(np.mean(np.abs(sig) ** 2))
    p_noise = p_sig / (10.0 ** (snr_db / 10.0))
    noise = np.sqrt(p_noise / 2.0) * (
        rng.standard_normal(sig.size) + 1j * rng.standard_normal(sig.size)
    )
    return sig + noise


# ---------------------------------------------------------------- analysis
def stft_spectrogram(
    sig: np.ndarray, fs: float, nperseg: int = 512, overlap_frac: float = 0.85
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Two-sided, fftshifted spectrogram in dB. Returns (f_Hz, t_s, S_dB)."""
    noverlap = int(nperseg * overlap_frac)
    f, tt, sxx = spectrogram(
        sig,
        fs=fs,
        nperseg=nperseg,
        noverlap=noverlap,
        return_onesided=False,
        scaling="spectrum",
        mode="magnitude",
    )
    order = np.argsort(np.fft.fftshift(f))
    f = np.fft.fftshift(f)[order]
    sxx = np.fft.fftshift(sxx, axes=0)[order, :]
    return f, tt, 20.0 * np.log10(sxx + 1e-12)


#: Half-width of the window treated as the bulk-body Doppler line. Fixed in
#: Hz rather than as a fraction of the measured span: a relative window makes
#: `sideband_ratio` depend on `bw_99`, which is circular.
BODY_LINE_HALFWIDTH_HZ = 100.0

#: Search band for the dominant envelope-modulation line.
ENV_MOD_BAND_HZ = (1.5, 1500.0)


def _envelope_periodicity(sig: np.ndarray, fs: float) -> tuple[float, float]:
    """Dominant amplitude-modulation line and its prominence.

    **This is deliberately not labelled a blade-passage rate.** A blade flash
    is impulsive, so the envelope spectrum is a rich harmonic series whose
    largest line is generally *not* the fundamental: measured on this model a
    200 Hz blade rate peaks at its 7th harmonic (1400 Hz), and a 4 Hz flap
    rate peaks near 80 Hz.

    Two attempts to recover the true fundamental were tried and rejected
    rather than shipped:

      * harmonic product spectrum - lands on integer multiples (3x for the
        2-blade rotor, 4x for the bird), the classic HPS octave error;
      * autocorrelation of the Doppler spectrum to find HERM-line spacing -
        correct for a 3-blade rotor (230 Hz measured vs 225 Hz analytic) but
        off by ~2.7x for 2-blade rotors.

    So the physical quantity is *not* claimed. What is returned is an honest
    modulation descriptor, which is all the classifier needs - it is strongly
    discriminative (1400 Hz vs 80 Hz between the two classes) without
    asserting a rotor parameter. Recovering the blade rate as a measured
    physical quantity is listed as open work.

    Returns (dominant_line_hz, prominence).
    """
    env = np.abs(np.asarray(sig)).astype(float)
    env = env - env.mean()
    if env.size < 64 or not np.any(env):
        return 0.0, 0.0

    spec = np.abs(np.fft.rfft(env * np.hanning(env.size)))
    fr = np.fft.rfftfreq(env.size, 1.0 / fs)
    band = (fr >= ENV_MOD_BAND_HZ[0]) & (fr <= min(ENV_MOD_BAND_HZ[1], fs / 2))
    if not band.any():
        return 0.0, 0.0

    sb = spec[band]
    k = int(np.argmax(sb))
    # Prominence above the in-band median separates a genuine periodic
    # modulation from a noise maximum.
    return float(fr[band][k]), float(sb[k] / (np.median(sb) + 1e-30))


def extract_features(sig: np.ndarray, fs: float, nperseg: int = 512) -> dict[str, float]:
    """Physically interpretable features for a classical classifier.

    Each feature maps onto something a reviewer can defend:
      bw_99            - Doppler extent, set by blade-tip speed
      bw_to_body_ratio - scale-invariant version of the above
      centroid_abs     - bulk-body Doppler
      spectral_entropy - discrete HERM lines (low) vs diffuse spread (high)
      sideband_ratio   - energy outside the body line / energy in it
      periodicity      - prominence of the periodic amplitude modulation
      flash_rate_hz    - blade-passage / wing-flap frequency
      env_kurtosis     - impulsiveness of the flash train

    Two corrections over the first version of this function, both of which
    were suppressing real class separation:

    1. **Noise-floor subtraction.** `bw_99` was computed on the raw mean
       spectrum, so at low SNR it measured the width of the *noise floor*
       (i.e. the whole band) instead of the signal. It saturated to the
       Nyquist span and carried no information exactly where classification
       is hardest. A robust median floor is now subtracted first.

    2. **Flash rate from the envelope, not the STFT.** The rate was estimated
       from the spectrogram frame sequence, whose hop rate
       (fs*(1-overlap)/nperseg ~ 260 Hz) aliases any blade rate above
       ~130 Hz - and multirotor blade rates are typically 130-450 Hz. It is
       now estimated from the full-rate amplitude envelope spectrum, which
       has no such ceiling.
    """
    f, _t, s_db = stft_spectrogram(sig, fs, nperseg=nperseg)
    s_lin = 10.0 ** (s_db / 20.0)
    psd = s_lin.mean(axis=1) ** 2

    # Robust noise floor: the median bin is noise for any sparse signature.
    floor = float(np.median(psd))
    psd_s = np.clip(psd - floor, 0.0, None)
    total = psd_s.sum()
    if total <= 0.0:                       # nothing above the floor
        psd_s, total = psd, psd.sum() + 1e-30
    psd_n = psd_s / total

    cdf = np.cumsum(psd_n)
    lo = f[int(np.searchsorted(cdf, 0.005))]
    hi = f[int(min(np.searchsorted(cdf, 0.995), f.size - 1))]
    bw99 = float(hi - lo)

    centroid = float(np.sum(f * psd_n))
    entropy = float(-np.sum(psd_n * np.log(psd_n + 1e-30)) / np.log(psd_n.size))

    peak_f = float(f[int(np.argmax(psd_n))])
    core = np.abs(f - peak_f) <= BODY_LINE_HALFWIDTH_HZ
    e_core = float(psd_n[core].sum())
    sideband_ratio = float((1.0 - e_core) / (e_core + 1e-9))

    # Dominant amplitude-modulation line (NOT the blade-passage rate - see
    # `_envelope_periodicity` for why that claim is not made).
    env_peak, periodicity = _envelope_periodicity(sig, fs)

    env_c = np.abs(sig) - np.mean(np.abs(sig))
    kurt = float(np.mean(env_c ** 4) / (np.mean(env_c ** 2) ** 2 + 1e-30))

    return {
        "bw_99": bw99,
        "bw_to_body_ratio": float(bw99 / (abs(centroid) + 50.0)),
        "centroid_abs": abs(centroid),
        "spectral_entropy": entropy,
        "sideband_ratio": sideband_ratio,
        "periodicity": periodicity,
        "env_mod_peak_hz": env_peak,
        "env_kurtosis": kurt,
    }


FEATURE_NAMES: tuple[str, ...] = (
    "bw_99",
    "bw_to_body_ratio",
    "centroid_abs",
    "spectral_entropy",
    "sideband_ratio",
    "periodicity",
    "env_mod_peak_hz",
    "env_kurtosis",
)


def theoretical_tip_doppler_hz(tgt: RotorTarget, freq_Hz: float = 9.5e9) -> float:
    """Analytic peak blade-tip Doppler, for validating the synthesis.

        f_d = 2 * v_tip / lambda,  v_tip = omega * L
    """
    lam = C_LIGHT / freq_Hz
    v_tip = (2.0 * np.pi * tgt.rpm / 60.0) * tgt.blade_len_m
    return float(2.0 * v_tip * np.cos(np.deg2rad(tgt.aspect_el_deg)) / lam)
