"""Transform: clean, type-coerce, and validate raw DataFrame."""
import pandas as pd

DATE_COLS = ["DOB", "ClaimStartDt", "ClaimEndDt", "AdmissionDt", "DischargeDt"]
TEXT_NULLABLE = ["Gender", "Race", "State", "Provider", "AttendingPhysician"]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Normalise blank strings to NaN so fillna works uniformly
    df.replace(r"^\s*$", pd.NA, regex=True, inplace=True)

    # Dates → ISO string (YYYY-MM-DD); bad/missing → NaN
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

    # Reimbursed amount → numeric
    if "InscClaimAmtReimbursed" in df.columns:
        df["InscClaimAmtReimbursed"] = (
            pd.to_numeric(df["InscClaimAmtReimbursed"], errors="coerce").fillna(0).astype(int)
        )

    # Chronic condition flags → int (1 or 2); invalid → NaN
    for col in ("ChronicCond_Diabetes", "ChronicCond_Heartfailure"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].where(df[col].isin([1, 2]))

    # Gender, Race, State → int
    for col in ("Gender", "Race", "State"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop exact duplicates
    before = len(df)
    df.drop_duplicates(inplace=True)
    after = len(df)
    if before != after:
        print(f"  Removed {before - after} duplicate rows")

    return df.reset_index(drop=True)
