import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_pool, close_pool, get_conn

# ── Database auto-initialisation ─────────────────────────────────────────────

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
)
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS app_users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    name          VARCHAR(255),
    role          VARCHAR(50),
    password_hash VARCHAR(255),
    is_active     SMALLINT DEFAULT 1
)
"""

DEMO_USERS = [
    ("demo@medintel.io",  "Dr. Olivia Carter", "Analyst", "demo1234"),
    ("admin@medintel.io", "Admin User",         "Admin",   "admin1234"),
]


def _seed_users(cur):
    import bcrypt
    for email, name, role, password in DEMO_USERS:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            """
            INSERT INTO app_users (email, name, role, password_hash, is_active)
            VALUES (%s, %s, %s, %s, 1)
            ON CONFLICT (email) DO NOTHING
            """,
            (email, name, role, pw_hash),
        )


def _load_csv(cur):
    import pandas as pd

    # Works from rootDir=backend: data/ is one level up
    candidates = [
        Path(__file__).parent.parent.parent / "data" / "healthcare_cleaned.csv",
        Path(__file__).parent.parent.parent.parent / "data" / "healthcare_cleaned.csv",
    ]
    csv_path = next((p for p in candidates if p.exists()), None)
    if not csv_path:
        print("  [init] CSV not found — skipping data load")
        return

    print(f"  [init] Loading CSV from {csv_path} ...")
    df = pd.read_csv(csv_path)

    col = lambda *names: next((c for c in names if c in df.columns), None)

    def v(val, cast=None):
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
        s = str(val).strip()
        if not s or s in ("nan", "NaT"):
            return None
        return cast(s) if cast else s

    batch = [
        (
            v(getattr(row, col('BeneID','bene_id'), '')),
            v(getattr(row, col('DOB','dob'), '')),
            v(getattr(row, col('Gender','gender'), ''), int),
            v(getattr(row, col('Race','race'), ''), int),
            v(getattr(row, col('State','state'), ''), int),
            v(getattr(row, col('ChronicCond_Diabetes','chroniccond_diabetes'), ''), int),
            v(getattr(row, col('ChronicCond_Heartfailure','chroniccond_heartfailure'), ''), int),
            v(getattr(row, col('ClaimID','claim_id'), '')),
            v(getattr(row, col('ClaimStartDt','claimstartdt'), '')),
            v(getattr(row, col('ClaimEndDt','claimenddt'), '')),
            v(getattr(row, col('Provider','provider'), '')),
            v(getattr(row, col('InscClaimAmtReimbursed','inscclaimamtreimbursed'), ''), float),
            v(getattr(row, col('AttendingPhysician','attendingphysician'), '')),
            v(getattr(row, col('AdmissionDt','admissiondt'), '')),
            v(getattr(row, col('DischargeDt','dischargedt'), '')),
        )
        for row in df.itertuples(index=False)
    ]

    cur.executemany(
        """
        INSERT INTO healthcare_claims (
            bene_id, dob, gender, race, state,
            chroniccond_diabetes, chroniccond_heartfailure,
            claim_id, claimstartdt, claimenddt,
            provider, inscclaimamtreimbursed, attendingphysician,
            admissiondt, dischargedt
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        batch,
    )
    print(f"  [init] Inserted {len(batch)} rows.")


def _auto_init():
    """Run in a background thread so the server starts immediately."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(CREATE_CLAIMS)
            cur.execute(CREATE_USERS)
            _seed_users(cur)

            cur.execute("SELECT COUNT(*) FROM healthcare_claims")
            if cur.fetchone()[0] == 0:
                _load_csv(cur)
            else:
                print("  [init] Data already loaded — skipping CSV import.")

        print("  [init] Database ready.")
    except Exception as exc:
        print(f"  [init] WARNING: auto-init failed: {exc}")


# ── App ───────────────────────────────────────────────────────────────────────

from .routers import claims, analytics, patients, ml, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    threading.Thread(target=_auto_init, daemon=True).start()
    yield
    close_pool()


app = FastAPI(
    title="MedIntel API",
    description=(
        "REST API powering MedIntel — a healthcare claims analytics platform "
        "backed by PostgreSQL with Medicare inpatient claims data (CMS dataset). "
        "Includes ML-powered patient risk scoring and provider fraud detection. "
        "All data endpoints require a valid JWT Bearer token."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(claims.router,    prefix="/api/claims",    tags=["Claims"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(patients.router,  prefix="/api/patients",  tags=["Patients"])
app.include_router(ml.router,        prefix="/api/ml",        tags=["ML"])


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok", "version": app.version}
