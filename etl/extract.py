"""Extract: load and merge raw source CSVs into a single DataFrame."""
import pandas as pd

BENEF_COLS = [
    "BeneID", "DOB", "Gender", "Race", "State",
    "ChronicCond_Diabetes", "ChronicCond_Heartfailure",
]
INPAT_COLS = [
    "ClaimID", "BeneID", "ClaimStartDt", "ClaimEndDt",
    "Provider", "InscClaimAmtReimbursed", "AttendingPhysician",
    "AdmissionDt", "DischargeDt",
]
FINAL_ORDER = [
    "BeneID", "DOB", "Gender", "Race", "State",
    "ChronicCond_Diabetes", "ChronicCond_Heartfailure",
    "ClaimID", "ClaimStartDt", "ClaimEndDt",
    "Provider", "InscClaimAmtReimbursed", "AttendingPhysician",
    "AdmissionDt", "DischargeDt",
]


def _require_cols(df: pd.DataFrame, needed: list[str], label: str) -> None:
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}\nFound: {list(df.columns)}")


def load_raw(benef_path: str, inpat_path: str, sample_n: int = 1000) -> pd.DataFrame:
    benef = pd.read_csv(benef_path, dtype=str, low_memory=False)
    inpat = pd.read_csv(inpat_path, dtype=str, low_memory=False)

    _require_cols(benef, BENEF_COLS, "Beneficiary file")
    _require_cols(inpat, INPAT_COLS, "Inpatient file")

    merged = inpat[INPAT_COLS].merge(benef[BENEF_COLS], on="BeneID", how="inner")
    merged = merged[FINAL_ORDER]

    if sample_n and len(merged) > sample_n:
        merged = merged.sample(n=sample_n, random_state=42).reset_index(drop=True)

    return merged
