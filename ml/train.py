"""
MedIntel ML Training Pipeline
==============================

Trains two models:
  1. Patient Spending Risk Classifier  — Random Forest (supervised)
     Predicts high-cost patients based on spending patterns (financial risk, not clinical)
  2. Provider Fraud Detector  — Isolation Forest (unsupervised / anomaly)

Usage:
    python -m ml.train

Output:
    ml/models/patient_spending_risk_model.joblib
    ml/models/provider_fraud_model.joblib
    ml/models/provider_fraud_scaler.joblib
    ml/models/provider_scores.json
    ml/models/metrics.json
"""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml.features import (
    PATIENT_FEATURES,
    PROVIDER_FEATURES,
    build_patient_features,
    build_provider_features,
    estimate_contamination,
    load_cleaned_data,
)

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


# ── Model 1: Patient Risk Classifier ────────────────────────────────────────

def train_patient_risk(patient_df) -> dict:
    print("\n[1/2]  Patient Spending Risk Classifier  (Random Forest)")
    print("─" * 50)
    print("  Stratified 80/20 split: random split stratified by target class")

    X = patient_df[PATIENT_FEATURES].values
    y = patient_df["spending_risk"].values

    n_pos = y.sum()
    print(f"  Patients   : {len(X):,}")
    print(f"  High spending-risk : {n_pos:,}  ({n_pos / len(y) * 100:.1f}%)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"  80/20 validation split: {len(X_train)} train, {len(X_test)} test")

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    # 5-fold cross-validation ROC-AUC
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")

    acc   = accuracy_score(y_test, y_pred)
    f1    = f1_score(y_test, y_pred, average="weighted")
    auc   = roc_auc_score(y_test, y_prob)
    cm    = confusion_matrix(y_test, y_pred).tolist()
    rep   = classification_report(y_test, y_pred, output_dict=True)

    print(f"  Accuracy   : {acc:.1%}")
    print(f"  ROC-AUC    : {auc:.4f}")
    print(f"  F1 Score   : {f1:.4f}")
    print(f"  CV ROC-AUC : {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    print(f"  Confusion  : TN={cm[0][0]} FP={cm[0][1]} FN={cm[1][0]} TP={cm[1][1]}")

    # Feature importance
    fi = {
        feat: round(float(imp), 4)
        for feat, imp in zip(PATIENT_FEATURES, model.feature_importances_)
    }
    top3 = sorted(fi.items(), key=lambda x: -x[1])[:3]
    print(f"  Top features: {', '.join(f'{k}={v:.3f}' for k, v in top3)}")

    joblib.dump(model, MODELS_DIR / "patient_risk_model.joblib")

    return {
        "model":             "RandomForestClassifier",
        "target":            "spending_risk (top 25% future spending)",
        "temporal_split":    "Earlier claims → features, later claims → target (prevents leakage)",
        "n_estimators":      300,
        "accuracy":          round(acc, 4),
        "f1_score":          round(f1, 4),
        "roc_auc":           round(auc, 4),
        "cv_roc_auc_mean":   round(float(cv_scores.mean()), 4),
        "cv_roc_auc_std":    round(float(cv_scores.std()), 4),
        "n_train":           int(len(X_train)),
        "n_test":            int(len(X_test)),
        "spending_risk_rate": round(float(y.mean()), 4),
        "feature_importance": fi,
        "confusion_matrix":  cm,
        "classification_report": rep,
    }


# ── Model 2: Provider Fraud Detector ────────────────────────────────────────

def train_provider_fraud(provider_df) -> tuple[dict, dict]:
    print("\n[2/2]  Provider Fraud Detector  (Isolation Forest)")
    print("─" * 50)

    X_raw = provider_df[PROVIDER_FEATURES].values
    print(f"  Providers  : {len(X_raw):,}")

    # Estimate contamination from data (IQR-based) instead of hard-coding
    contamination = estimate_contamination(provider_df)
    print(f"  Contamination (estimated): {contamination:.3f}")

    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    model = IsolationForest(
        n_estimators=300,
        contamination=contamination,
        max_features=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X)

    # score_samples: lower = more anomalous; invert and normalise → 0-100
    raw = model.score_samples(X)
    mn, mx = raw.min(), raw.max()
    fraud_scores = 100.0 * (mx - raw) / (mx - mn + 1e-9)

    flagged_high   = int((fraud_scores >= 70).sum())
    flagged_medium = int(((fraud_scores >= 40) & (fraud_scores < 70)).sum())

    print(f"  High risk  (≥70): {flagged_high}")
    print(f"  Medium risk (40-69): {flagged_medium}")
    print(f"  Avg score  : {fraud_scores.mean():.1f}")

    # Build lookup without iterrows() — use vectorized zip over arrays
    providers   = provider_df["Provider"].tolist()
    score_lookup = {
        str(p): round(float(s), 1)
        for p, s in zip(providers, fraud_scores)
    }

    joblib.dump(model,  MODELS_DIR / "provider_fraud_model.joblib")
    joblib.dump(scaler, MODELS_DIR / "provider_fraud_scaler.joblib")
    with open(MODELS_DIR / "provider_scores.json", "w") as f:
        json.dump(score_lookup, f, indent=2)

    metrics = {
        "model":           "IsolationForest",
        "n_estimators":    300,
        "contamination":   round(contamination, 3),
        "n_providers":     int(len(X_raw)),
        "flagged_high":    flagged_high,
        "flagged_medium":  flagged_medium,
        "avg_fraud_score": round(float(fraud_scores.mean()), 2),
        "features":        PROVIDER_FEATURES,
    }
    return metrics, score_lookup


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()
    print("=" * 60)
    print("  MedIntel — ML Training Pipeline")
    print("=" * 60)

    print("\nLoading and engineering features …")
    df = load_cleaned_data()
    patient_df  = build_patient_features(df)
    provider_df = build_provider_features(df)
    print(f"  {len(patient_df):,} patients | {len(provider_df):,} providers")

    patient_metrics             = train_patient_risk(patient_df)
    provider_metrics, _scores   = train_provider_fraud(provider_df)

    all_metrics = {
        "patient_spending_risk":    patient_metrics,
        "provider_fraud":  provider_metrics,
    }
    with open(MODELS_DIR / "metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  ✅  Training complete in {elapsed:.1f}s")
    print(f"  Models saved → ml/models/")
    print(f"{'='*60}")
    print("\n  Next steps:")
    print("  1. cd backend && uvicorn app.main:app --reload")
    print("  2. Open frontend/index.html")
    print("  3. ML risk scores are now live in the dashboard\n")


if __name__ == "__main__":
    main()
