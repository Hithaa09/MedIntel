"""
ETL pipeline CLI.

Usage:
    python -m etl.pipeline                   # full run: extract → transform → load
    python -m etl.pipeline --check           # test DB connection only
    python -m etl.pipeline --skip-load       # extract + transform, save CSV, no DB insert
"""
import argparse
import os
import sys
import time
from pathlib import Path

# Allow running from project root as:  python -m etl.pipeline
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import oracledb

from etl.extract import load_raw
from etl.transform import clean
from etl.load import load_to_oracle

# ---- paths ---------------------------------------------------------------
BENEF_PATH   = str(PROJECT_ROOT / "data" / "Train_Beneficiarydata-1542865627584.csv")
INPAT_PATH   = str(PROJECT_ROOT / "data" / "Train_Inpatientdata-1542865627584.csv")
RAW_OUT      = str(PROJECT_ROOT / "data" / "healthcare_raw_1000x15.csv")
CLEANED_OUT  = str(PROJECT_ROOT / "data" / "healthcare_cleaned.csv")

# ---- DB config ------------------------------------------------------------
DB_USER = os.getenv("DB_USER", "APP")
DB_PASS = os.getenv("DB_PASS", "app")
DB_DSN  = os.getenv("DB_DSN",  "localhost:1521/XEPDB1")


def check_connection() -> bool:
    try:
        conn = oracledb.connect(user=DB_USER, password=DB_PASS, dsn=DB_DSN)
        cur = conn.cursor()
        cur.execute("SELECT sys_context('USERENV','SERVICE_NAME') FROM dual")
        service = cur.fetchone()[0]
        cur.execute("SELECT sys_context('USERENV','CURRENT_SCHEMA') FROM dual")
        schema = cur.fetchone()[0]
        conn.close()
        print(f"  Connected to service={service}  schema={schema}")
        return True
    except Exception as exc:
        print(f"  Connection failed: {exc}")
        return False


def run(skip_load: bool = False) -> None:
    t0 = time.time()
    print("=" * 60)
    print("MedIntel — ETL Pipeline")
    print("=" * 60)

    # Step 1 – Extract
    print("\n[1/3] Extracting …")
    df = load_raw(BENEF_PATH, INPAT_PATH, sample_n=1000)
    df.to_csv(RAW_OUT, index=False)
    print(f"  Raw data: {df.shape}  → {RAW_OUT}")

    # Step 2 – Transform
    print("\n[2/3] Transforming …")
    df = clean(df)
    df.to_csv(CLEANED_OUT, index=False)
    print(f"  Cleaned data: {df.shape}  → {CLEANED_OUT}")

    # Step 3 – Load
    if skip_load:
        print("\n[3/3] Skipping load (--skip-load flag).")
    else:
        print("\n[3/3] Loading to Oracle …")
        if not check_connection():
            print("  Aborting: cannot reach Oracle.")
            sys.exit(1)
        inserted = load_to_oracle(df, DB_USER, DB_PASS, DB_DSN)
        print(f"  Inserted {inserted} rows into healthcare_claims")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Healthcare Claims ETL")
    parser.add_argument("--check",     action="store_true", help="Test DB connection and exit")
    parser.add_argument("--skip-load", action="store_true", help="Extract+transform only; skip DB load")
    args = parser.parse_args()

    if args.check:
        print("Checking DB connection …")
        ok = check_connection()
        sys.exit(0 if ok else 1)

    run(skip_load=args.skip_load)


if __name__ == "__main__":
    main()
