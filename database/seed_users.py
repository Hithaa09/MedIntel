"""
Seed demo users into the Oracle app_users table.

Run once after database/schema.sql has been applied:
    python database/seed_users.py

This generates fresh bcrypt hashes each run — safe to re-run
(MERGE ensures no duplicate emails).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import bcrypt
import oracledb

DB_USER = os.getenv("DB_USER", "APP")
DB_PASS = os.getenv("DB_PASS", "app")
DB_DSN  = os.getenv("DB_DSN",  "localhost:1521/XEPDB1")

DEMO_USERS = [
    ("demo@medintel.io",  "Dr. Olivia Carter", "Analyst",  "demo1234"),
    ("admin@medintel.io", "Admin User",         "Admin",    "admin1234"),
]

MERGE_SQL = """
MERGE INTO app_users dst
USING (SELECT :email AS email FROM dual) src
ON (LOWER(dst.email) = LOWER(src.email))
WHEN MATCHED THEN
    UPDATE SET name = :name, role = :role,
               password_hash = :pw_hash, is_active = 1
WHEN NOT MATCHED THEN
    INSERT (email, name, role, password_hash, is_active)
    VALUES (:email, :name, :role, :pw_hash, 1)
"""


def main() -> None:
    conn = oracledb.connect(user=DB_USER, password=DB_PASS, dsn=DB_DSN)
    try:
        cur = conn.cursor()
        for email, name, role, password in DEMO_USERS:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cur.execute(MERGE_SQL, {"email": email, "name": name,
                                    "role": role, "pw_hash": pw_hash})
            print(f"  ✅  {email}  ({role})")
        conn.commit()
        print("\nDemo users seeded successfully.")
        print("Login: demo@medintel.io / demo1234")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
