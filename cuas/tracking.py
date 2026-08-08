"""
LAYER 3 - FUSION / TRACKING
===========================
Kalman and IMM estimators, plus the validation metrics the first prototype
was missing.

The original script produced one Kalman track on one noise realisation and
plotted it. That demonstrates the equations but proves nothing: there is no
error statistic and no filter-consistency check.

Added here:
  * shared 6-state model [x, vx, ax, y, vy, ay] so CV and CA can be mixed
    in an IMM without state augmentation
  * IMM (constant-velocity + constant-acceleration) for manoeuvring UAS
  * NEES - normalised estimation error squared, the standard consistency
    test. A correctly tuned filter gives E[NEES] = state dimension; a value
    well above that means the filter is over-confident (covariance too
    small), which is what causes real trackers to drop targets.
  * position / velocity RMSE from Monte-Carlo repetition
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

STATE_DIM = 6           # [x, vx, ax, y, vy, ay]
MEAS_DIM = 2            # [x, y]


# ---------------------------------------------------------------- models
def transition_matrix(dt: float) -> np.ndarray:
    """Constant-acceleration state transition (block-diagonal per axis)."""
    a = np.array([[1.0, dt, 0.5 * dt ** 2], [0.0, 1.0, dt], [0.0, 0.0, 1.0]])
    f = np.zeros((STATE_DIM, STATE_DIM))
    f[:3, :3] = a
    f[3:, 3:] = a
    return f


def measurement_matrix() -> np.ndarray:
    h = np.zeros((MEAS_DIM, STATE_DIM))
    h[0, 0] = 1.0
    h[1, 3] = 1.0
    return h


def process_noise(dt: float, sigma_jerk: float) -> np.ndarray:
    """Discrete white-noise jerk model - continuous jerk driving each axis."""
    q1 = np.array(
        [
            [dt ** 5 / 20.0, dt ** 4 / 8.0, dt ** 3 / 6.0],
            [dt ** 4 / 8.0, dt ** 3 / 3.0, dt ** 2 / 2.0],
            [dt ** 3 / 6.0, dt ** 2 / 2.0, dt],
        ]
    ) * sigma_jerk ** 2
    q = np.zeros((STATE_DIM, STATE_DIM))
    q[:3, :3] = q1
    q[3:, 3:] = q1
    return q


@dataclass
class MotionModel:
    name: str
    sigma_jerk: float           # m/s^3, process-noise intensity

    def F(self, dt: float) -> np.ndarray:
        return transition_matrix(dt)

    def Q(self, dt: float) -> np.ndarray:
        return process_noise(dt, self.sigma_jerk)


CV_MODEL = MotionModel("CV (low manoeuvre)", sigma_jerk=0.3)
CA_MODEL = MotionModel("CA (high manoeuvre)", sigma_jerk=12.0)


# ---------------------------------------------------------------- KF
@dataclass
class KalmanFilterCV:
    """Single-model Kalman filter on the shared 6-state vector."""

    dt: float = 0.1
    sigma_meas: float = 3.0
    model: MotionModel = field(default_factory=lambda: CV_MODEL)

    def run(self, meas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Filter a measurement sequence. Returns (states, covariances)."""
        meas = np.asarray(meas, dtype=float)
        f = self.model.F(self.dt)
        q = self.model.Q(self.dt)
        h = measurement_matrix()
        r = np.eye(MEAS_DIM) * self.sigma_meas ** 2

        x = np.zeros(STATE_DIM)
        x[0], x[3] = meas[0, 0], meas[0, 1]
        p = np.eye(STATE_DIM) * 100.0

        xs = np.zeros((meas.shape[0], STATE_DIM))
        ps = np.zeros((meas.shape[0], STATE_DIM, STATE_DIM))
        for k, z in enumerate(meas):
            x = f @ x
            p = f @ p @ f.T + q
            y = z - h @ x
            s = h @ p @ h.T + r
            kg = p @ h.T @ np.linalg.inv(s)
            x = x + kg @ y
            p = (np.eye(STATE_DIM) - kg @ h) @ p
            xs[k], ps[k] = x, p
        return xs, ps


# ---------------------------------------------------------------- IMM
@dataclass
class IMMFilter:
    """Interacting Multiple Model filter over a bank of motion models.

    Handles the regime change that breaks a single-model filter: a UAS in
    steady transit (CV) that suddenly turns or dives (CA). The mode
    probabilities also give a usable manoeuvre-detection output.
    """

    dt: float = 0.1
    sigma_meas: float = 3.0
    models: tuple[MotionModel, ...] = (CV_MODEL, CA_MODEL)
    p_stay: float = 0.95            # probability of remaining in a mode

    def _transition_probs(self) -> np.ndarray:
        m = len(self.models)
        off = (1.0 - self.p_stay) / (m - 1)
        pi = np.full((m, m), off)
        np.fill_diagonal(pi, self.p_stay)
        return pi

    def run(self, meas: np.ndarray) -> dict[str, np.ndarray]:
        meas = np.asarray(meas, dtype=float)
        n, m = meas.shape[0], len(self.models)
        pi = self._transition_probs()
        h = measurement_matrix()
        r = np.eye(MEAS_DIM) * self.sigma_meas ** 2

        x0 = np.zeros(STATE_DIM)
        x0[0], x0[3] = meas[0, 0], meas[0, 1]
        xs = [x0.copy() for _ in range(m)]
        ps = [np.eye(STATE_DIM) * 100.0 for _ in range(m)]
        mu = np.full(m, 1.0 / m)

        out_x = np.zeros((n, STATE_DIM))
        out_p = np.zeros((n, STATE_DIM, STATE_DIM))
        out_mu = np.zeros((n, m))

        for k, z in enumerate(meas):
            # --- mixing -------------------------------------------------
            c_bar = pi.T @ mu
            mix = (pi * mu[:, None]) / np.maximum(c_bar[None, :], 1e-300)
            xs_mix, ps_mix = [], []
            for j in range(m):
                xj = sum(mix[i, j] * xs[i] for i in range(m))
                pj = np.zeros((STATE_DIM, STATE_DIM))
                for i in range(m):
                    d = (xs[i] - xj).reshape(-1, 1)
                    pj += mix[i, j] * (ps[i] + d @ d.T)
                xs_mix.append(xj)
                ps_mix.append(pj)

            # --- per-model predict / update ------------------------------
            lik = np.zeros(m)
            for j, mdl in enumerate(self.models):
                f, q = mdl.F(self.dt), mdl.Q(self.dt)
                xp = f @ xs_mix[j]
                pp = f @ ps_mix[j] @ f.T + q
                y = z - h @ xp
                s = h @ pp @ h.T + r
                s_inv = np.linalg.inv(s)
                kg = pp @ h.T @ s_inv
                xs[j] = xp + kg @ y
                ps[j] = (np.eye(STATE_DIM) - kg @ h) @ pp
                nis = float(y @ s_inv @ y)
                lik[j] = np.exp(-0.5 * nis) / np.sqrt(
                    (2.0 * np.pi) ** MEAS_DIM * max(np.linalg.det(s), 1e-300)
                )

            # --- mode update + combination ------------------------------
            w = c_bar * lik
            mu = w / max(w.sum(), 1e-300)

            xc = sum(mu[j] * xs[j] for j in range(m))
            pc = np.zeros((STATE_DIM, STATE_DIM))
            for j in range(m):
                d = (xs[j] - xc).reshape(-1, 1)
                pc += mu[j] * (ps[j] + d @ d.T)

            out_x[k], out_p[k], out_mu[k] = xc, pc, mu

        return {"x": out_x, "P": out_p, "mode_prob": out_mu}


# ---------------------------------------------------------------- metrics
def position_rmse(truth_xy: np.ndarray, est_state: np.ndarray) -> float:
    err = est_state[:, [0, 3]] - np.asarray(truth_xy, dtype=float)
    return float(np.sqrt(np.mean(np.sum(err ** 2, axis=1))))


def velocity_rmse(truth_vxy: np.ndarray, est_state: np.ndarray) -> float:
    err = est_state[:, [1, 4]] - np.asarray(truth_vxy, dtype=float)
    return float(np.sqrt(np.mean(np.sum(err ** 2, axis=1))))


def nees(truth_state: np.ndarray, est_state: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Normalised estimation error squared, per time step.

    Consistency test: the time-average should be close to the state
    dimension. Much larger means the filter under-states its own
    uncertainty, which is the usual cause of lost tracks.
    """
    out = np.zeros(est_state.shape[0])
    for k in range(est_state.shape[0]):
        d = est_state[k] - truth_state[k]
        try:
            out[k] = float(d @ np.linalg.solve(cov[k], d))
        except np.linalg.LinAlgError:
            out[k] = np.nan
    return out


# ---------------------------------------------------------------- scenarios
def manoeuvring_track(
    duration_s: float = 40.0,
    dt: float = 0.1,
    speed_ms: float = 18.0,
    turn_rate_deg_s: float = 25.0,
    turn_window: tuple[float, float] = (15.0, 22.0),
) -> dict[str, np.ndarray]:
    """Ground truth for a UAS in transit that executes one hard turn.

    This is the scenario a single-model CV filter cannot follow, and is the
    justification for the IMM.
    """
    t = np.arange(0.0, duration_s, dt)
    omega = np.where(
        (t >= turn_window[0]) & (t <= turn_window[1]),
        np.deg2rad(turn_rate_deg_s),
        0.0,
    )
    heading = np.cumsum(omega) * dt
    vx = speed_ms * np.cos(heading)
    vy = speed_ms * np.sin(heading)
    x = np.cumsum(vx) * dt
    y = np.cumsum(vy) * dt
    ax = np.gradient(vx, dt)
    ay = np.gradient(vy, dt)

    state = np.column_stack([x, vx, ax, y, vy, ay])
    return {
        "t": t,
        "state": state,
        "pos": np.column_stack([x, y]),
        "vel": np.column_stack([vx, vy]),
    }


def add_measurement_noise(
    pos: np.ndarray, sigma: float = 3.0, rng: np.random.Generator | None = None
) -> np.ndarray:
    rng = rng or np.random.default_rng()
    return np.asarray(pos, dtype=float) + rng.standard_normal(np.shape(pos)) * sigma


def monte_carlo_compare(
    n_runs: int = 200,
    sigma_meas: float = 4.0,
    dt: float = 0.1,
    seed: int = 7,
) -> dict[str, dict[str, float]]:
    """Compare CV Kalman vs IMM over `n_runs` noise realisations.

    Reports mean +/- std of position RMSE, plus mean NEES for consistency.
    """
    rng = np.random.default_rng(seed)
    truth = manoeuvring_track(dt=dt)
    results: dict[str, list[list[float]]] = {"KF-CV": [], "IMM": []}

    for _ in range(n_runs):
        meas = add_measurement_noise(truth["pos"], sigma_meas, rng)

        xs, ps = KalmanFilterCV(dt=dt, sigma_meas=sigma_meas).run(meas)
        results["KF-CV"].append(
            [
                position_rmse(truth["pos"], xs),
                float(np.nanmean(nees(truth["state"], xs, ps))),
            ]
        )

        imm = IMMFilter(dt=dt, sigma_meas=sigma_meas).run(meas)
        results["IMM"].append(
            [
                position_rmse(truth["pos"], imm["x"]),
                float(np.nanmean(nees(truth["state"], imm["x"], imm["P"]))),
            ]
        )

    summary = {}
    for name, rows in results.items():
        arr = np.asarray(rows)
        summary[name] = {
            "rmse_mean_m": float(arr[:, 0].mean()),
            "rmse_std_m": float(arr[:, 0].std()),
            "nees_mean": float(arr[:, 1].mean()),
            "nees_target": float(STATE_DIM),
            "n_runs": n_runs,
        }
    return summary
