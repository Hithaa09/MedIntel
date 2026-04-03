"""
One-time PostgreSQL initialisation script.

Creates tables, seeds demo users, and loads the healthcare claims CSV.

Usage (run once after Render PostgreSQL is provisioned):
    DATABASE_URL=postgresql://... python database/init_pg.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import bcrypt
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/medintel")
DATA_CSV     = ROOT / "data" / "healthcare_cleaned.csv"

CREATE_CLAIMS = """
CREATE TABLE IF NOT EXISTS healthcare_claims (
    id                       SERIAL PRIMARY KEY,
    bene_id                  VARCHAR(20),
    dob                      DATE,
    gender                   SMALLINT,
    race                     SMALLINT,
    state                    SMALLINT,
    chroniccond_diabetes     SMALLINT,
    chroniccond_heartfailure SMALLINT,
    claim_id                 VARCHAR(30),
    claimstartdt             DATE,
    claimenddt               DATE,
    provider                 VARCHAR(20),
    inscclaimamtreimbursed   NUMERIC(12,2),
    attendingphysician       VARCHAR(20),
    admissiondt              DATE,
    dischargedt              DATE
);
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS app_users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    name          VARCHAR(255),
    role          VARCHAR(50),
    password_hash VARCHAR(255),
    is_active     SMALLINT DEFAULT 1
);
"""

DEMO_USERS = [
    ("demo@medintel.io",  "Dr. Olivia Carter", "Analyst", "demo1234"),
    ("admin@medintel.io", "Admin User",         "Admin",   "admin1234"),
]


def _to_val(val, cast=None):
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if not s or s in ("nan", "NaT"):
        return None
    return cast(s) if cast else s


def main():
    print(f"Connecting to: {DATABASE_URL[:40]}...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # ── Create tables ─────────────────────────────────────────────
    print("Creating tables...")
    cur.execute(CREATE_CLAIMS)
    cur.execute(CREATE_USERS)
    conn.commit()

    # ── Seed demo users ───────────────────────────────────────────
    print("Seeding demo users...")
    for email, name, role, password in DEMO_USERS:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            """
            INSERT INTO app_users (email, name, role, password_hash, is_active)
            VALUES (%s, %s, %s, %s, 1)
            ON CONFLICT (email) DO UPDATE
              SET name=EXCLUDED.name, role=EXCLUDED.role,
                  password_hash=EXCLUDED.password_hash, is_active=1
            """,
            (email, name, role, pw_hash),
        )
    conn.commit()
    print("  demo@medintel.io  / demo1234")
    print("  admin@medintel.io / admin1234")

    # ── Load CSV data ─────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM healthcare_claims")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"Skipping CSV load — {existing} rows already present.")
        conn.close()
        return

    print(f"Loading CSV from {DATA_CSV} ...")
    df = pd.read_csv(DATA_CSV)

    INSERT_SQL = """
        INSERT INTO healthcare_claims (
            bene_id, dob, gender, race, state,
            chroniccond_diabetes, chroniccond_heartfailure,
            claim_id, claimstartdt, claimenddt,
            provider, inscclaimamtreimbursed, attendingphysician,
            admissiondt, dischargedt
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    # Map CSV column names (try both original and cleaned versions)
    col = lambda *candidates: next((c for c in candidates if c in df.columns), None)

    batch = []
    for row in df.itertuples(index=False):
        batch.append((
            _to_val(getattr(row, col('BeneID','bene_id'), None)),
            _to_val(getattr(row, col('DOB','dob'), None)),
            _to_val(getattr(row, col('Gender','gender'), None), int),
            _to_val(getattr(row, col('Race','race'), None), int),
            _to_val(getattr(row, col('State','state'), None), int),
            _to_val(getattr(row, col('ChronicCond_Diabetes','chroniccond_diabetes'), None), int),
            _to_val(getattr(row, col('ChronicCond_Heartfailure','chroniccond_heartfailure'), None), int),
            _to_val(getattr(row, col('ClaimID','claim_id'), None)),
            _to_val(getattr(row, col('ClaimStartDt','claimstartdt'), None)),
            _to_val(getattr(row, col('ClaimEndDt','claimenddt'), None)),
            _to_val(getattr(row, col('Provider','provider'), None)),
            _to_val(getattr(row, col('InscClaimAmtReimbursed','inscclaimamtreimbursed'), None), float),
            _to_val(getattr(row, col('AttendingPhysician','attendingphysician'), None)),
            _to_val(getattr(row, col('AdmissionDt','admissiondt'), None)),
            _to_val(getattr(row, col('DischargeDt','dischargedt'), None)),
        ))

    cur.executemany(INSERT_SQL, batch)
    conn.commit()
    print(f"  Inserted {len(batch)} rows.")
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
