"""Load: insert a cleaned DataFrame into Oracle healthcare_claims table."""
from datetime import date, datetime
from typing import Optional

import oracledb
import pandas as pd


def _to_date(val) -> Optional[date]:
    if pd.isna(val) or str(val).strip() in ("", "nan", "NaT"):
        return None
    try:
        return datetime.strptime(str(val), "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_int(val, fallback=None):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return fallback


def _to_float(val, fallback=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return fallback


INSERT_SQL = """
INSERT INTO healthcare_claims (
    bene_id, dob, gender, race, state,
    chroniccond_diabetes, chroniccond_heartfailure,
    claim_id, claimstartdt, claimenddt,
    provider, inscclaimamtreimbursed, attendingphysician,
    admissiondt, dischargedt
) VALUES (
    :1, :2, :3, :4, :5,
    :6, :7,
    :8, :9, :10,
    :11, :12, :13,
    :14, :15
)
"""


def load_to_oracle(df: pd.DataFrame, user: str, password: str, dsn: str) -> int:
    batch = [
        (
            row["BeneID"],
            _to_date(row["DOB"]),
            _to_int(row["Gender"]),
            _to_int(row["Race"]),
            _to_int(row["State"]),
            _to_int(row["ChronicCond_Diabetes"]),
            _to_int(row["ChronicCond_Heartfailure"]),
            row["ClaimID"],
            _to_date(row["ClaimStartDt"]),
            _to_date(row["ClaimEndDt"]),
            row.get("Provider"),
            _to_float(row["InscClaimAmtReimbursed"]),
            row.get("AttendingPhysician"),
            _to_date(row["AdmissionDt"]),
            _to_date(row["DischargeDt"]),
        )
        for _, row in df.iterrows()
    ]

    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    try:
        cur = conn.cursor()
        cur.executemany(INSERT_SQL, batch, batcherrors=True)
        errors = cur.getbatcherrors()
        if errors:
            for err in errors[:5]:
                print(f"  Row {err.offset}: {err.message}")
        conn.commit()
        inserted = len(batch) - len(errors)
        return inserted
    finally:
        conn.close()
