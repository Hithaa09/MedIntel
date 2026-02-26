"""
Feature engineering for MedIntel ML models.
Reads from the cleaned CSV; no Oracle dependency for training.
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).parent.parent / "data" / "healthcare_cleaned.csv"

# Year the data is from — used to compute patient age
DATA_YEAR = 2010

# ── Feature sets ────────────────────────────────────────────────────────────

PATIENT_FEATURES = [
    "age",
    "gender",
    "state",
    "claim_count",
    "avg_los",
    "max_los",
    "unique_providers",
    "has_diabetes",
    "has_heartfailure",
]

PROVIDER_FEATURES = [
    "total_claims",
    "unique_patients",
    "claims_per_patient",
    "avg_reimbursed",
    "max_reimbursed",
    "std_reimbursed",
    "avg_los",
    "max_los",
    "std_los",
    "diabetes_rate",
    "hf_rate",
]


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_cleaned_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    for col in ("ClaimStartDt", "ClaimEndDt", "AdmissionDt", "DischargeDt", "DOB"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["InscClaimAmtReimbursed"] = pd.to_numeric(
        df["InscClaimAmtReimbursed"], errors="coerce"
    ).fillna(0)
    df["los"] = (df["DischargeDt"] - df["AdmissionDt"]).dt.days.clip(lower=0)
    df["ChronicCond_Diabetes"] = pd.to_numeric(df["ChronicCond_Diabetes"], errors="coerce")
    df["ChronicCond_Heartfailure"] = pd.to_numeric(df["ChronicCond_Heartfailure"], errors="coerce")
    df["Gender"] = pd.to_numeric(df["Gender"], errors="coerce")
    df["State"] = pd.to_numeric(df["State"], errors="coerce")
    return df


# ── Patient-level features ───────────────────────────────────────────────────

def build_patient_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per patient.
    Target: high_spender = 1 when patient's total reimbursement >= 75th percentile.
    Features: demographics + utilisation patterns + chronic condition flags.
    No leakage: total_reimbursed is only used to compute the target, not as an input feature.
    """

    def _mode(s):
        m = pd.to_numeric(s, errors="coerce").dropna()
        return float(m.mode().iloc[0]) if len(m) else 0.0

    agg = df.groupby("BeneID").agg(
        dob=("DOB", "first"),
        gender=("Gender", _mode),
        state=("State", _mode),
        claim_count=("ClaimID", "count"),
        total_reimbursed=("InscClaimAmtReimbursed", "sum"),
        avg_reimbursed=("InscClaimAmtReimbursed", "mean"),
        max_reimbursed=("InscClaimAmtReimbursed", "max"),
        avg_los=("los", "mean"),
        max_los=("los", "max"),
        unique_providers=("Provider", "nunique"),
        chroniccond_diabetes=("ChronicCond_Diabetes", _mode),
        chroniccond_heartfailure=("ChronicCond_Heartfailure", _mode),
    ).reset_index()

    agg["age"] = DATA_YEAR - agg["dob"].dt.year
    median_age = agg["age"].median()
    agg["age"] = agg["age"].clip(0, 120).fillna(median_age)

    # Binary condition flags as features (not used as sole target — avoids leakage)
    agg["has_diabetes"]    = (agg["chroniccond_diabetes"]    == 1).astype(float)
    agg["has_heartfailure"] = (agg["chroniccond_heartfailure"] == 1).astype(float)

    # Target: top-quartile spender (high-cost patient)
    # Predicting future cost from demographic + utilisation features is
    # a legitimate, learnable clinical ML problem with no label leakage.
    q75 = agg["total_reimbursed"].quantile(0.75)
    agg["high_spender"] = (agg["total_reimbursed"] >= q75).astype(int)

    return agg[["BeneID", "total_reimbursed"] + PATIENT_FEATURES + ["high_spender"]].fillna(0)


# ── Provider-level features ──────────────────────────────────────────────────

def build_provider_features(df: pd.DataFrame) -> pd.DataFrame:
    """One row per provider. Used for unsupervised anomaly detection."""

    agg = df.groupby("Provider").agg(
        total_claims=("ClaimID", "count"),
        unique_patients=("BeneID", "nunique"),
        total_reimbursed=("InscClaimAmtReimbursed", "sum"),
        avg_reimbursed=("InscClaimAmtReimbursed", "mean"),
        max_reimbursed=("InscClaimAmtReimbursed", "max"),
        std_reimbursed=("InscClaimAmtReimbursed", "std"),
        avg_los=("los", "mean"),
        max_los=("los", "max"),
        std_los=("los", "std"),
        diabetes_rate=("ChronicCond_Diabetes", lambda x: (x == 1).mean()),
        hf_rate=("ChronicCond_Heartfailure", lambda x: (x == 1).mean()),
    ).reset_index()

    agg["claims_per_patient"] = agg["total_claims"] / agg["unique_patients"].clip(lower=1)

    return agg[["Provider"] + PROVIDER_FEATURES].fillna(0)
