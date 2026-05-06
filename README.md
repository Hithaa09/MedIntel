# MedIntel — Healthcare Claims Analytics

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?style=flat&logo=postgresql&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-F7931E?style=flat&logo=scikitlearn&logoColor=white)
![Render](https://img.shields.io/badge/Deployed-Render-46E3B7?style=flat&logo=render&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat)

A full-stack healthcare data analytics platform built on **PostgreSQL**, **FastAPI**, and **scikit-learn**. Ingests real CMS Medicare inpatient claims data through a structured ETL pipeline, serves it via a JWT-authenticated REST API, and presents it in an interactive dashboard with **ML-powered patient risk scoring** and **provider fraud detection**.

**Live demo:** [https://medintel-frontend.onrender.com](https://medintel-frontend.onrender.com)
> Demo credentials: `demo@medintel.io` / `Demo@MedI24`

---

## What it does

| Layer | Description |
|---|---|
| **ETL Pipeline** | Extracts, cleans, and loads 1,000 Medicare inpatient claims from CMS CSVs |
| **Database** | PostgreSQL — auto-initialised on first startup, no manual setup required |
| **REST API** | FastAPI — JWT auth, claims, analytics, patient risk, provider stats, ML inference |
| **ML Models** | Random Forest (patient spending risk) + Isolation Forest (provider fraud anomaly) |
| **Dashboard** | MedIntel SPA — KPIs, sparklines, charts, patient profiles, fraud risk scores |

---

## Tech Stack

| Component | Technology |
|---|---|
| Database | PostgreSQL 18 (Render managed) — psycopg2 |
| API | FastAPI + Pydantic v2 + uvicorn |
| Auth | JWT Bearer tokens (python-jose + bcrypt) |
| ETL | Python — pandas, python-dotenv |
| Machine Learning | scikit-learn — Random Forest, Isolation Forest |
| Frontend | Vanilla HTML/CSS/JS — Chart.js |
| Deployment | Render (Blueprint — DB + API + Static Site) |

---

## Architecture

```
CMS Source CSVs (Train_*.csv)
        │
        ▼
etl/pipeline.py          extract → transform → load
        │
        ▼
PostgreSQL               healthcare_claims + app_users
        │                (auto-created on first startup)
  ┌─────┴──────┐
  ▼            ▼
FastAPI     ml/train.py
/api/*      (offline training)
  │            │
  └─────┬──────┘
        ▼
MedIntel Dashboard (frontend/index.html)
```

**ML Models:**
- `PatientRiskClassifier` — Random Forest trained on utilisation patterns (claim frequency, LOS, chronic conditions) to predict high-spending patients. Evaluated with accuracy, ROC-AUC, and 5-fold cross-validation.
- `ProviderFraudDetector` — Isolation Forest anomaly detection on provider-level billing statistics. Assigns a 0–100 fraud risk score per provider. Contamination rate is estimated from data using IQR — not hard-coded.

---

## Live Deployment

The app is deployed on Render using a single `render.yaml` Blueprint:

| Service | URL |
|---|---|
| Frontend (Static Site) | https://medintel-frontend.onrender.com |
| Backend API | https://medintel-api-8hph.onrender.com |
| Database | Render PostgreSQL 18 (Oregon) |

> **Note:** Free tier instances spin down after 15 minutes of inactivity. First request after sleep takes ~30 seconds to wake up.

---

## Quick Start (Local)

### Prerequisites
- Python 3.11+
- PostgreSQL running locally

### 1. Clone and install
```bash
git clone https://github.com/Hithaa09/MedIntel.git
cd MedIntel
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — set DATABASE_URL to your local PostgreSQL connection string
# Example: DATABASE_URL=postgresql://postgres:postgres@localhost:5432/medintel
```

### 3. Initialise the database
```bash
# Creates tables, seeds demo users, and loads the CSV in one step
python database/init_pg.py
```

### 4. Train ML models
```bash
python -m ml.train
# Output: ml/models/*.joblib + metrics.json (~30 seconds)
```

### 5. Start the API
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
Interactive API docs: **http://localhost:8000/docs**

### 6. Open the dashboard
Open `frontend/index.html` in a browser (VS Code Live Server recommended).

Login with:
- `demo@medintel.io` / `Demo@MedI24`
- `admin@medintel.io` / `Admin@MedI24`

---

## Deploy to Render (One Command)

```bash
# 1. Push to GitHub
git push origin main

# 2. Go to render.com → New → Blueprint → connect your repo
# Render reads render.yaml and creates all 3 services automatically:
#   - medintel-db     (PostgreSQL)
#   - medintel-api    (FastAPI Web Service)
#   - medintel-frontend (Static Site)
```

The backend auto-initialises the database (tables + demo users + CSV data) on first startup — no manual database setup or shell access needed.

---

## API Reference

All endpoints except `/api/health` and `/api/auth/login` require a `Bearer` token.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Login — returns JWT token |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/claims` | Paginated claims (filter: state, gender, provider, diabetes, heartfailure, date_from, date_to) |
| `GET` | `/api/claims/{id}` | Single claim detail |
| `GET` | `/api/analytics/summary` | KPIs: total claims, unique patients, total reimbursed, avg LOS |
| `GET` | `/api/analytics/monthly-trend` | Monthly claim volume, spend, unique patients, avg LOS |
| `GET` | `/api/analytics/by-state` | Claims grouped by CMS state code |
| `GET` | `/api/analytics/conditions` | Chronic condition distribution (diabetes, heart failure) |
| `GET` | `/api/analytics/top-providers` | Top N providers by claim count |
| `GET` | `/api/patients` | Patient list with risk levels |
| `GET` | `/api/patients/{id}` | Patient profile |
| `GET` | `/api/patients/{id}/claims` | All claims for one patient |
| `GET` | `/api/ml/status` | ML model readiness check |
| `GET` | `/api/ml/metrics` | Model accuracy, ROC-AUC, feature importance, contamination rate |
| `GET` | `/api/ml/patient-risk/{id}` | ML spending risk score for a patient |
| `GET` | `/api/ml/provider-fraud/{id}` | Fraud anomaly score for a provider |
| `GET` | `/api/ml/all-fraud-scores` | All providers ranked by fraud risk |

---

## Dashboard Features

- **Overview** — 4 KPI cards with real period-over-period change badges computed from monthly trend data, sparklines (claims, patients, reimbursement, avg LOS), monthly chart, conditions donut, top states and providers
- **Claims** — paginated table with filters: gender, diabetes, heart failure, provider, state, date range
- **Patients** — searchable patient list with risk levels, click-through patient panel with claim history and ML risk score
- **Providers** — bar charts and ranked table with fraud risk scores from Isolation Forest
- **Insights** — ML model performance metrics (accuracy, ROC-AUC, F1, feature importances, contamination rate), fraud risk summary
- **Global search** — searches claims, patients, and providers in real time

---

## ML Model Details

### Patient Spending Risk Classifier
- **Algorithm:** Random Forest (300 estimators, class-balanced)
- **Features:** Age, gender, state, avg/max LOS per admission, unique providers visited, diabetes flag, heart failure flag
- **Target:** `spending_risk` — whether a patient's total reimbursement falls in the top quartile (≥ 75th percentile). Financial risk metric, not a clinical diagnosis.
- **Evaluation:** Accuracy, weighted F1, ROC-AUC, 5-fold stratified cross-validation

### Provider Fraud Detector
- **Algorithm:** Isolation Forest (unsupervised anomaly detection)
- **Features:** Claim volume, unique patients, claims-per-patient ratio, reimbursement stats (avg/max/std), LOS stats, chronic condition rates
- **Contamination:** Estimated from data using IQR-based outlier heuristic — not hard-coded
- **Output:** Fraud anomaly score 0–100 per provider (higher = more anomalous billing pattern)

---

## Project Structure

```
MedIntel/
├── render.yaml               ← Render Blueprint (DB + API + Frontend)
├── runtime.txt               ← Python 3.11.9 pin for Render
├── requirements.txt          ← all dependencies
├── .env.example              ← environment template
│
├── backend/                  ← FastAPI application
│   ├── requirements.txt      ← server-only dependencies
│   ├── runtime.txt           ← Python version pin
│   └── app/
│       ├── main.py           ← app + auto-init DB on startup
│       ├── config.py         ← settings (DATABASE_URL, JWT, CORS)
│       ├── database.py       ← psycopg2 connection pool
│       ├── auth.py           ← JWT auth + bcrypt
│       ├── schemas.py        ← Pydantic models
│       └── routers/
│           ├── claims.py
│           ├── analytics.py
│           ├── patients.py
│           ├── ml.py
│           └── auth.py
│
├── ml/                       ← Machine learning
│   ├── features.py           ← feature engineering
│   ├── train.py              ← training CLI
│   ├── predict.py            ← inference utilities
│   └── models/               ← saved models (committed)
│       ├── patient_risk_model.joblib
│       ├── provider_fraud_model.joblib
│       ├── provider_fraud_scaler.joblib
│       ├── provider_scores.json
│       └── metrics.json
│
├── etl/                      ← Data pipeline
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   └── pipeline.py           ← CLI orchestrator
│
├── database/
│   ├── init_pg.py            ← one-time PostgreSQL initialisation script
│   ├── schema.sql            ← original Oracle DDL (reference)
│   └── queries.sql           ← showcase SQL queries
│
├── frontend/
│   └── index.html            ← MedIntel SPA dashboard
│
└── data/
    └── healthcare_cleaned.csv  ← 1,000-row CMS claims sample
```

---

## Data Source

[CMS Healthcare Provider Fraud Detection](https://www.kaggle.com/datasets/rohitrox/healthcare-provider-fraud-detection-analysis) — public domain Medicare claims dataset. 1,000 rows sampled from merged beneficiary + inpatient data (2009).

---

## License

MIT
