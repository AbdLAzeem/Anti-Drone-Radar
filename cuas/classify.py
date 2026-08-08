"""
LAYER 2b - TRAINED CLASSIFIER
=============================
Turns the micro-Doppler features into a measured decision, with the numbers
a reviewer will ask for: a confusion matrix, cross-validated accuracy, and a
ROC/AUC on the operationally meaningful binary question.

Three classes are synthesised with randomised parameters so the classifier is
not fitting one fixed signature:

  multirotor  - 4-8 rotors, 2-3 blades, 4000-9000 rpm
  fixed-wing  - single 2-blade propeller, larger blade, higher airspeed
  bird        - 2-9 Hz flapping, small radial excursion

The binary question that matters for a port radar is **UAS vs bird**: false
alarms on gulls are what make an operator switch a system off. That is
reported separately from the 3-class result.

Deliberately a classical pipeline (interpretable features -> SVM) rather than
a CNN on raw spectrograms. With a synthetic dataset a CNN mostly learns the
generator, and every feature here can be defended physically. A CNN
comparison is a stated next step, not a claim.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from . import microdoppler as md

CLASS_NAMES: tuple[str, ...] = ("multirotor", "fixed-wing", "bird")
UAS_CLASSES: tuple[str, ...] = ("multirotor", "fixed-wing")


# ---------------------------------------------------------------- dataset
def _random_multirotor(rng: np.random.Generator) -> md.RotorTarget:
    return md.RotorTarget(
        label="multirotor",
        n_rotors=int(rng.choice([4, 6, 8])),
        n_blades=int(rng.choice([2, 3])),
        blade_len_m=float(rng.uniform(0.09, 0.20)),
        rpm=float(rng.uniform(4000.0, 9000.0)),
        body_speed_ms=float(rng.uniform(2.0, 22.0)),
        aspect_el_deg=float(rng.uniform(5.0, 45.0)),
        body_to_rotor_rcs_ratio=float(rng.uniform(1.5, 6.0)),
    )


def _random_fixed_wing(rng: np.random.Generator) -> md.RotorTarget:
    return md.RotorTarget(
        label="fixed-wing",
        n_rotors=1,
        n_blades=2,
        blade_len_m=float(rng.uniform(0.18, 0.35)),
        rpm=float(rng.uniform(3000.0, 6500.0)),
        # Overlaps the multirotor and bird ranges on purpose: speed must not
        # be a free giveaway for the class label.
        body_speed_ms=float(rng.uniform(12.0, 40.0)),
        aspect_el_deg=float(rng.uniform(5.0, 40.0)),
        body_to_rotor_rcs_ratio=float(rng.uniform(4.0, 15.0)),
    )


def _random_bird(rng: np.random.Generator) -> md.BirdTarget:
    return md.BirdTarget(
        label="bird",
        flap_rate_hz=float(rng.uniform(2.0, 9.0)),
        wing_excursion_m=float(rng.uniform(0.10, 0.40)),
        body_speed_ms=float(rng.uniform(5.0, 20.0)),
        aspect_el_deg=float(rng.uniform(5.0, 50.0)),
        body_to_wing_rcs_ratio=float(rng.uniform(1.5, 5.0)),
        n_harmonics=int(rng.integers(2, 5)),
    )


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray                  # string labels
    feature_names: tuple[str, ...]
    snr_db: np.ndarray


def build_dataset(
    n_per_class: int = 60,
    fs: float = 20_000.0,
    duration_s: float = 0.5,
    snr_range_db: tuple[float, float] = (8.0, 30.0),
    seed: int = 42,
) -> Dataset:
    """Synthesise a labelled dataset with randomised targets and SNR.

    SNR is randomised over a wide range on purpose: a classifier that only
    works at high SNR is useless at the edge of the detection envelope, which
    is exactly where classification decisions are needed.
    """
    rng = np.random.default_rng(seed)
    rows, labels, snrs = [], [], []

    for cls in CLASS_NAMES:
        for _ in range(n_per_class):
            snr = float(rng.uniform(*snr_range_db))
            if cls == "multirotor":
                _t, sig = md.synth_rotor(_random_multirotor(rng), fs=fs,
                                         duration_s=duration_s, snr_db=snr, rng=rng)
            elif cls == "fixed-wing":
                _t, sig = md.synth_rotor(_random_fixed_wing(rng), fs=fs,
                                         duration_s=duration_s, snr_db=snr, rng=rng)
            else:
                _t, sig = md.synth_bird(_random_bird(rng), fs=fs,
                                        duration_s=duration_s, snr_db=snr, rng=rng)
            feats = md.extract_features(sig, fs)
            rows.append([feats[k] for k in md.FEATURE_NAMES])
            labels.append(cls)
            snrs.append(snr)

    return Dataset(
        X=np.asarray(rows, dtype=float),
        y=np.asarray(labels),
        feature_names=md.FEATURE_NAMES,
        snr_db=np.asarray(snrs, dtype=float),
    )


# ---------------------------------------------------------------- model
def make_model() -> Pipeline:
    """Standardised RBF-SVM with probability output."""
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("svm", SVC(kernel="rbf", C=10.0, gamma="scale",
                        probability=True, random_state=0)),
        ]
    )


@dataclass
class ClassifierReport:
    accuracy: float
    confusion: np.ndarray
    class_names: tuple[str, ...]
    uas_vs_bird_auc: float
    roc_fpr: np.ndarray
    roc_tpr: np.ndarray
    per_class_recall: dict[str, float]
    accuracy_by_snr: list[dict]
    n_samples: int
    n_folds: int
    operating_point: dict
    excluded_features: tuple[str, ...] = ()


#: Features that encode bulk radial speed rather than the micro-Doppler
#: signature itself. A real radar does measure speed and would use it, but a
#: claim about *signature-based* classification must not rest on it - so the
#: ablation below drops these and re-reports.
SPEED_FEATURES: tuple[str, ...] = ("centroid_abs",)


def evaluate(
    ds: Dataset,
    n_folds: int = 5,
    seed: int = 0,
    exclude_features: tuple[str, ...] = (),
) -> ClassifierReport:
    """Cross-validated evaluation. No number here comes from training data.

    Uses `cross_val_predict`, so every prediction is made by a model that did
    not see that sample. Reporting training accuracy would be meaningless.

    `exclude_features` drops named columns before fitting - used for the
    speed-feature ablation.
    """
    model = make_model()
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)

    if exclude_features:
        keep = [i for i, n in enumerate(ds.feature_names)
                if n not in exclude_features]
        x = ds.X[:, keep]
    else:
        x = ds.X

    y_pred = cross_val_predict(model, x, ds.y, cv=cv)
    y_proba = cross_val_predict(model, x, ds.y, cv=cv, method="predict_proba")
    classes = sorted(set(ds.y))

    acc = float(accuracy_score(ds.y, y_pred))
    cm = confusion_matrix(ds.y, y_pred, labels=list(CLASS_NAMES))

    recall = {}
    for i, cls in enumerate(CLASS_NAMES):
        total = cm[i].sum()
        recall[cls] = float(cm[i, i] / total) if total else float("nan")

    # --- binary UAS vs bird ---------------------------------------------
    is_uas = np.isin(ds.y, UAS_CLASSES).astype(int)
    uas_idx = [classes.index(c) for c in UAS_CLASSES if c in classes]
    score_uas = y_proba[:, uas_idx].sum(axis=1)
    auc = float(roc_auc_score(is_uas, score_uas))
    fpr, tpr, thr = roc_curve(is_uas, score_uas)

    # Operating point: the lowest false-alarm rate that still holds
    # detection at 0.95 - the way a C-UAS requirement is actually written.
    target_tpr = 0.95
    ok = np.where(tpr >= target_tpr)[0]
    j = int(ok[0]) if ok.size else int(np.argmax(tpr))
    operating_point = {
        "target_detection_rate": target_tpr,
        "achieved_detection_rate": float(tpr[j]),
        "false_alarm_rate_on_birds": float(fpr[j]),
        "threshold": float(thr[j]) if j < thr.size else float("nan"),
    }

    # --- accuracy vs SNR -------------------------------------------------
    edges = [8.0, 13.0, 18.0, 24.0, 30.001]
    by_snr = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (ds.snr_db >= lo) & (ds.snr_db < hi)
        if m.sum() >= 5:
            by_snr.append(
                {
                    "snr_band_db": f"{lo:.0f}-{hi:.0f}",
                    "n": int(m.sum()),
                    "accuracy": float(accuracy_score(ds.y[m], y_pred[m])),
                }
            )

    return ClassifierReport(
        accuracy=acc,
        confusion=cm,
        class_names=CLASS_NAMES,
        uas_vs_bird_auc=auc,
        roc_fpr=fpr,
        roc_tpr=tpr,
        per_class_recall=recall,
        accuracy_by_snr=by_snr,
        n_samples=int(ds.X.shape[0]),
        n_folds=n_folds,
        operating_point=operating_point,
        excluded_features=tuple(exclude_features),
    )


def evaluate_with_ablation(
    ds: Dataset, n_folds: int = 5, seed: int = 0
) -> dict[str, ClassifierReport]:
    """Report the full feature set and the signature-only ablation together.

    The pair is the honest presentation. Permutation importance shows bulk
    radial Doppler (`centroid_abs`) carrying a large share of the decision,
    and the synthetic classes have partly non-overlapping speed ranges - so
    the full-feature score is partly a speed discriminator. The ablation
    answers the question a reviewer will actually ask: how well does the
    *micro-Doppler signature alone* separate a UAS from a bird?
    """
    return {
        "all_features": evaluate(ds, n_folds, seed),
        "signature_only": evaluate(ds, n_folds, seed,
                                   exclude_features=SPEED_FEATURES),
    }


def feature_importance(ds: Dataset, n_folds: int = 5, seed: int = 0) -> list[dict]:
    """Permutation importance - which features actually carry the decision.

    Needed to defend the feature set: a feature that can be shuffled without
    hurting accuracy is not evidence of anything.
    """
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import train_test_split

    x_tr, x_te, y_tr, y_te = train_test_split(
        ds.X, ds.y, test_size=0.3, stratify=ds.y, random_state=seed
    )
    model = make_model().fit(x_tr, y_tr)
    imp = permutation_importance(model, x_te, y_te, n_repeats=15,
                                 random_state=seed)
    rows = [
        {"feature": name,
         "importance": float(imp.importances_mean[i]),
         "std": float(imp.importances_std[i])}
        for i, name in enumerate(ds.feature_names)
    ]
    return sorted(rows, key=lambda r: -r["importance"])
