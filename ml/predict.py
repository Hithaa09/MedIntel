"""
Inference utilities — load saved models and run predictions.
Lazy-loaded on first call using double-checked locking (thread-safe).
"""
import json
import threading
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

MODELS_DIR = Path(__file__).parent / "models"

# ── Singletons, loaded once ───────────────────────────────────────────────────
_patient_model   = None
_provider_model  = None
_provider_scaler = None
_provider_scores: dict[str, float] = {}
_metrics: dict = {}
_loaded = False
_lock   = threading.Lock()           # prevents concurrent double-load


def _load() -> None:
    """Load all model artifacts from disk exactly once, thread-safely."""
    global _patient_model, _provider_model, _provider_scaler
    global _provider_scores, _metrics, _loaded

    if _loaded:                      # fast path — no lock needed after first load
        return

    with _lock:
        if _loaded:                  # second check inside lock (double-checked locking)
            return

        pm  = MODELS_DIR / "patient_risk_model.joblib"
        pfm = MODELS_DIR / "provider_fraud_model.joblib"
        pfs = MODELS_DIR / "provider_fraud_scaler.joblib"
        psc = MODELS_DIR / "provider_scores.json"
        mt  = MODELS_DIR / "metrics.json"

        if pm.exists():
            _patient_model = joblib.load(pm)
        if pfm.exists():
            _provider_model = joblib.load(pfm)
        if pfs.exists():
            _provider_scaler = joblib.load(pfs)
        if psc.exists():
            with open(psc) as f:
                _provider_scores = json.load(f)
        if mt.exists():
            with open(mt) as f:
                _metrics = json.load(f)

        _loaded = True


# ── Public API ────────────────────────────────────────────────────────────────

def models_ready() -> bool:
    _load()
    return _patient_model is not None and bool(_provider_scores)


def get_metrics() -> dict:
    _load()
    return _metrics


def predict_patient_spending_risk(features: dict) -> Optional[float]:
    """
    Returns spending risk probability [0.0, 1.0] or None if model unavailable.

    This model predicts financial risk (top 25% spenders), NOT clinical risk.
    Trained on temporally split data — features from early claims,
    target derived from later claims to prevent temporal leakage.

    Expected keys (must match ml.features.PATIENT_FEATURES):
        age, gender, state, claim_count, avg_los, max_los,
        unique_providers, has_diabetes, has_heartfailure
    """
    _load()
    if _patient_model is None:
        return None
    from ml.features import PATIENT_FEATURES
    X = np.array([[features.get(f, 0.0) for f in PATIENT_FEATURES]], dtype=float)
    return float(_patient_model.predict_proba(X)[0][1])


def get_provider_fraud_score(provider: str) -> Optional[float]:
    """Returns fraud anomaly score [0, 100] or None if unavailable."""
    _load()
    return _provider_scores.get(provider) if _provider_scores else None


def get_all_fraud_scores() -> dict[str, float]:
    _load()
    return _provider_scores
