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

from fastapi import APIRouter, Depends, HTTPException

# Add project root so ml/ is importable from the backend process
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from ml.predict import (
    get_all_fraud_scores,
    get_metrics,
    get_provider_fraud_score,
    models_ready,
    predict_patient_spending_risk,
)

from ..auth import get_current_user
from ..database import get_conn

router = APIRouter(dependencies=[Depends(get_current_user)])

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

@router.get("/patient-risk/{bene_id}", summary="ML-predicted spending risk score for a patient (financial risk, not clinical)")
def patient_risk(bene_id: str):
    if not models_ready():
        raise _NOT_TRAINED

    # Single query fetches all needed features + condition flags
    sql = """
        SELECT
            COUNT(claim_id)                        AS claim_count,
            AVG(dischargedt - admissiondt)         AS avg_los,
            MAX(dischargedt - admissiondt)         AS max_los,
            COUNT(DISTINCT provider)               AS unique_providers,
            MAX(gender)                            AS gender,
            MAX(state)                             AS state,
            MAX(dob)                               AS dob,
            MAX(CASE WHEN chroniccond_diabetes    = 1 THEN 1 ELSE 0 END) AS has_diabetes,
            MAX(CASE WHEN chroniccond_heartfailure = 1 THEN 1 ELSE 0 END) AS has_heartfailure
        FROM healthcare_claims
        WHERE bene_id = :bid
    """
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, {"bid": bene_id.upper()})
            row = cur.fetchone()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable — start Oracle and run the ETL pipeline first.",
        ) from exc

    if not row or row[0] == 0:
        raise HTTPException(status_code=404, detail=f"Patient '{bene_id}' not found")

    dob = row[6]
    # Use 2009 — the actual year of this CMS dataset — not a magic constant
    DATA_REF_YEAR = 2009
    age = float(DATA_REF_YEAR - dob.year) if dob else 65.0

    features = {
        "claim_count":       float(row[0] or 0),
        "avg_los":           float(row[1] or 0),
        "max_los":           float(row[2] or 0),
        "unique_providers":  float(row[3] or 0),
        "gender":            float(row[4] or 1),
        "state":             float(row[5] or 0),
        "age":               age,
        "has_diabetes":      float(row[7] or 0),
        "has_heartfailure":  float(row[8] or 0),
    }

    prob = predict_patient_spending_risk(features)
    if prob is None:
        raise _NOT_TRAINED

    score = round(prob * 100, 1)
    level = "High" if score >= 65 else "Medium" if score >= 35 else "Low"

    return {
        "bene_id":          bene_id.upper(),
        "spending_risk_score": score,
        "spending_risk_probability": round(prob, 4),
        "risk_level":       level,
        "note":             "Spending risk = top 25% by reimbursement cost (financial metric, not clinical)",
        "features_used":    features,
    }


# ── Provider fraud ────────────────────────────────────────────────────────────

@router.get("/provider-fraud/{provider}", summary="Fraud anomaly score for a provider")
def provider_fraud(provider: str):
    if not models_ready():
        raise _NOT_TRAINED
    score = get_provider_fraud_score(provider.upper())
    if score is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider.upper()}' not found")
    level = "High" if score >= 70 else "Medium" if score >= 40 else "Low"
    return {"provider": provider.upper(), "fraud_risk_score": score, "risk_level": level}


@router.get("/all-fraud-scores", summary="All providers ranked by fraud risk score")
def all_fraud_scores():
    scores = get_all_fraud_scores()
    if not scores:
        raise _NOT_TRAINED
    return [
        {
            "provider":         k,
            "fraud_risk_score": v,
            "risk_level":       "High" if v >= 70 else "Medium" if v >= 40 else "Low",
        }
        for k, v in sorted(scores.items(), key=lambda x: -x[1])
    ]
