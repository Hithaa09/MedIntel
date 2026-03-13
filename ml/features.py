"""
Feature engineering for MedIntel ML models.
Reads from the cleaned CSV; no Oracle dependency for training.
"""
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).parent.parent / "data" / "healthcare_cleaned.csv"

# ── Feature sets ──────────────────────────────────────────────────────────────

# claim_count is intentionally excluded: it has a mechanical relationship with
# total_reimbursed (more claims → higher total cost), which would make the
# classifier appear better than it is on unseen data.
# The remaining features are legitimate clinical / demographic predictors.
PATIENT_FEATURES = [
    "age",              # older patients typically cost more
    "gender",           # gender-based cost differences are documented in CMS data
    "state",            # geographic variation in care costs
    "avg_los",          # average days per admission — strong cost predictor
    "max_los",          # longest single stay — captures high-acuity episodes
    "unique_providers", # care fragmentation signal
    "has_diabetes",     # chronic condition flag (1 = Yes, 0 = No)
    "has_heartfailure", # chronic condition flag (1 = Yes, 0 = No)
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


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_cleaned_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    for col in ("ClaimStartDt", "ClaimEndDt", "AdmissionDt", "DischargeDt", "DOB"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["InscClaimAmtReimbursed"] = pd.to_numeric(
        df["InscClaimAmtReimbursed"], errors="coerce"
    ).fillna(0)
    df["los"] = (df["DischargeDt"] - df["AdmissionDt"]).dt.days.clip(lower=0)
    df["ChronicCond_Diabetes"]    = pd.to_numeric(df["ChronicCond_Diabetes"],    errors="coerce")
    df["ChronicCond_Heartfailure"] = pd.to_numeric(df["ChronicCond_Heartfailure"], errors="coerce")
    df["Gender"] = pd.to_numeric(df["Gender"], errors="coerce")
    df["State"]  = pd.to_numeric(df["State"],  errors="coerce")
    return df


# ── Patient-level features ────────────────────────────────────────────────────

def build_patient_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per patient.

    Target:   spending_risk = 1  →  patient's total reimbursement ≥ 75th percentile
              (top-quartile spender — financial risk, not clinical risk)

    Leakage note:
      claim_count is excluded because it has a direct mechanical relationship
      with total_reimbursed (more claims = higher total cost). The remaining
      features (age, demographics, avg LOS, chronic condition flags) are
      clinically grounded predictors with no algorithmic link to the target.

      This is a cross-sectional model trained on 2009 CMS data.
      In production with longitudinal records you would predict year-N+1
      spending from year-N features, eliminating residual collinearity.
    """

    def _mode(s):
        m = pd.to_numeric(s, errors="coerce").dropna()
        return float(m.mode().iloc[0]) if len(m) else 0.0

    # Derive reference year from data instead of hard-coding
    ref_year = int(df["ClaimStartDt"].dropna().dt.year.median())

    agg = df.groupby("BeneID").agg(
        dob=("DOB", "first"),
        gender=("Gender", _mode),
        state=("State", _mode),
        total_reimbursed=("InscClaimAmtReimbursed", "sum"),
        avg_los=("los", "mean"),
        max_los=("los", "max"),
        unique_providers=("Provider", "nunique"),
        chroniccond_diabetes=("ChronicCond_Diabetes",    _mode),
        chroniccond_heartfailure=("ChronicCond_Heartfailure", _mode),
    ).reset_index()

    agg["age"] = ref_year - agg["dob"].dt.year
    agg["age"] = agg["age"].clip(0, 120).fillna(agg["age"].median())

    agg["has_diabetes"]     = (agg["chroniccond_diabetes"]     == 1).astype(float)
    agg["has_heartfailure"] = (agg["chroniccond_heartfailure"] == 1).astype(float)

    q75 = agg["total_reimbursed"].quantile(0.75)
    agg["spending_risk"] = (agg["total_reimbursed"] >= q75).astype(int)

    return agg[["BeneID", "total_reimbursed"] + PATIENT_FEATURES + ["spending_risk"]].fillna(0)


# ── Provider-level features ───────────────────────────────────────────────────

def build_provider_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per provider. Used for unsupervised anomaly detection.
    Contamination is estimated from data (IQR method) rather than hard-coded.
    """
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
        diabetes_rate=("ChronicCond_Diabetes",    lambda x: (x == 1).mean()),
        hf_rate=("ChronicCond_Heartfailure", lambda x: (x == 1).mean()),
    ).reset_index()

    agg["claims_per_patient"] = agg["total_claims"] / agg["unique_patients"].clip(lower=1)

    return agg[["Provider"] + PROVIDER_FEATURES].fillna(0)


def estimate_contamination(provider_df: pd.DataFrame) -> float:
    """
    Estimate the anomaly contamination rate from the data using an IQR-based
    outlier heuristic rather than hard-coding an arbitrary fraction.
    Returns a value clamped to [0.05, 0.20].
    """
    scores = provider_df[PROVIDER_FEATURES]
    q1, q3 = scores.quantile(0.25), scores.quantile(0.75)
    iqr = q3 - q1
    # Count rows with ANY feature > 1.5 × IQR above Q3
    outlier_mask = ((scores > q3 + 1.5 * iqr)).any(axis=1)
    rate = outlier_mask.mean()
    return float(max(0.05, min(0.20, rate)))
