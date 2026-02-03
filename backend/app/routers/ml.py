"""
ML inference endpoints.

GET /api/ml/status            — are models trained and ready?
GET /api/ml/metrics           — accuracy, ROC-AUC, feature importance
GET /api/ml/patient-risk/{id} — per-patient risk probability (Random Forest)
GET /api/ml/provider-fraud/{p}— per-provider anomaly score (Isolation Forest)
GET /api/ml/all-fraud-scores  — all providers ranked by fraud risk
"""
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

# Add project root so ml/ is importable from the backend process
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from ml.predict import (
    get_all_fraud_scores,
    get_metrics,
    get_provider_fraud_score,
    models_ready,
    predict_patient_risk,
)

from ..database import get_conn

router = APIRouter()

_NOT_TRAINED = HTTPException(
    status_code=503,
    detail="ML models not trained yet. Run:  python -m ml.train",
)


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status", summary="Check if ML models are loaded")
def ml_status():
    ready = models_ready()
    return {
        "models_ready": ready,
        "message": "Models ready — predictions are live." if ready
                   else "Models not trained. Run: python -m ml.train",
    }


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/metrics", summary="Model evaluation metrics (accuracy, ROC-AUC, feature importance)")
def ml_metrics():
    m = get_metrics()
    if not m:
        raise _NOT_TRAINED
    return m


# ── Patient risk ──────────────────────────────────────────────────────────────

@router.get("/patient-risk/{bene_id}", summary="ML-predicted risk score for a patient")
def patient_risk(bene_id: str):
    if not models_ready():
        raise _NOT_TRAINED

    sql = """
        SELECT
            COUNT(claim_id)                        AS claim_count,
            SUM(inscclaimamtreimbursed)            AS total_reimbursed,
            AVG(inscclaimamtreimbursed)            AS avg_reimbursed,
            MAX(inscclaimamtreimbursed)            AS max_reimbursed,
            AVG(dischargedt - admissiondt)         AS avg_los,
            MAX(dischargedt - admissiondt)         AS max_los,
            COUNT(DISTINCT provider)               AS unique_providers,
            MAX(gender)                            AS gender,
            MAX(state)                             AS state,
            MAX(dob)                               AS dob
        FROM healthcare_claims
        WHERE bene_id = :bid
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, {"bid": bene_id.upper()})
        row = cur.fetchone()

    if not row or row[0] == 0:
        raise HTTPException(status_code=404, detail=f"Patient '{bene_id}' not found")

    dob  = row[9]
    age  = float(2010 - dob.year) if dob else 65.0

    features = {
        "claim_count":      float(row[0] or 0),
        "total_reimbursed": float(row[1] or 0),
        "avg_reimbursed":   float(row[2] or 0),
        "max_reimbursed":   float(row[3] or 0),
        "avg_los":          float(row[4] or 0),
        "max_los":          float(row[5] or 0),
        "unique_providers": float(row[6] or 0),
        "gender":           float(row[7] or 1),
        "state":            float(row[8] or 0),
        "age":              age,
    }

    prob = predict_patient_risk(features)
    if prob is None:
        raise _NOT_TRAINED

    score = round(prob * 100, 1)
    level = "High" if score >= 65 else "Medium" if score >= 35 else "Low"

    return {
        "bene_id":          bene_id.upper(),
        "risk_score":       score,
        "risk_probability": round(prob, 4),
        "risk_level":       level,
        "features_used":    features,
    }


# ── Provider fraud ────────────────────────────────────────────────────────────

@router.get("/provider-fraud/{provider}", summary="Fraud anomaly score for a provider")
def provider_fraud(provider: str):
    score = get_provider_fraud_score(provider.upper())
    if score is None:
        raise _NOT_TRAINED
    level = "High" if score >= 70 else "Medium" if score >= 40 else "Low"
    return {"provider": provider.upper(), "fraud_risk_score": score, "risk_level": level}


@router.get("/all-fraud-scores", summary="All providers ranked by fraud risk score")
def all_fraud_scores():
    scores = get_all_fraud_scores()
    if not scores:
        raise _NOT_TRAINED
    return [
        {
            "provider":        k,
            "fraud_risk_score": v,
            "risk_level":      "High" if v >= 70 else "Medium" if v >= 40 else "Low",
        }
        for k, v in sorted(scores.items(), key=lambda x: -x[1])
    ]
