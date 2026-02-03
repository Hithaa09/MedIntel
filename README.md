# MedIntel — Healthcare Claims Analytics

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)
![Oracle](https://img.shields.io/badge/Oracle-XE%2021c-F80000?style=flat&logo=oracle&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-F7931E?style=flat&logo=scikitlearn&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat)

A full-stack healthcare data analytics platform built on **Oracle XE**, **FastAPI**, and **scikit-learn**. Ingests real CMS Medicare inpatient claims data through a structured ETL pipeline, stores it in a relational database, serves it via a REST API, and presents it in an interactive dashboard with **ML-powered patient risk scoring** and **provider fraud detection**.

---

## What it does

| Layer | Description |
|---|---|
| **ETL Pipeline** | Extracts, cleans, and loads 1,000 Medicare inpatient claims into Oracle XE |
| **Database** | Normalized schema with indexes and 3 analytical SQL views |
| **REST API** | FastAPI — claims, analytics, patient risk, provider stats, ML inference |
| **ML Models** | Random Forest (patient risk) + Isolation Forest (provider fraud anomaly) |
| **Dashboard** | MedIntel SPA — KPIs, charts, patient profiles, fraud risk scores |

---

## Tech Stack

| Component | Technology |
|---|---|
| Database | Oracle XE 21c — oracledb thin driver |
| API | FastAPI + Pydantic + uvicorn |
| ETL | Python — pandas, python-dotenv |
| Machine Learning | scikit-learn — Random Forest, Isolation Forest |
| Frontend | Vanilla HTML/CSS/JS — Chart.js |

---

## Architecture

```
CMS Source CSVs (Train_*.csv)
        │
        ▼
etl/pipeline.py          extract → transform → load
        │
        ▼
Oracle XE                healthcare_claims + 3 SQL views
        │
  ┌─────┴──────┐
  ▼            ▼
FastAPI     ml/train.py
/api/*      (offline training)
  │            │
  └─────┬──────┘
        ▼
MedIntel Dashboard (frontend/index.html)
```

**SQL Views:**
- `v_provider_stats` — per-provider claim volume, avg reimbursement, avg LOS
- `v_monthly_trend` — month-by-month claim counts and spend
- `v_patient_risk` — patient risk scoring (High / Medium / Low)

**ML Models:**
- `PatientRiskClassifier` — Random Forest trained on utilization patterns (claim frequency, reimbursement, LOS) to predict high-risk patients. Evaluated with accuracy, ROC-AUC, and 5-fold cross-validation.
- `ProviderFraudDetector` — Isolation Forest anomaly detection on provider-level statistics. Assigns a 0–100 fraud risk score to each provider.

---

## Quick Start

### 1. Prerequisites
- Oracle XE 21c running locally (`localhost:1521/XEPDB1`)
- Python 3.11+

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your Oracle credentials
```

### 4. Create database schema
Open `database/schema.sql` in Oracle SQL Developer and run as script (F5).

### 5. Run the ETL pipeline
```bash
# Place source CSVs in data/ first (Train_Beneficiarydata-*.csv, Train_Inpatientdata-*.csv)
python -m etl.pipeline --check      # verify DB connection
python -m etl.pipeline              # full ETL run
```

### 6. Train ML models
```bash
python -m ml.train
# Output: ml/models/*.joblib + metrics.json (~30 seconds)
```

### 7. Start the API
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
Interactive API docs: **http://localhost:8000/docs**

### 8. Open the dashboard
Open `frontend/index.html` in a browser (use VS Code Live Server for best results).

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/claims` | Paginated claims (filter by state, gender, provider, conditions) |
| `GET` | `/api/claims/{id}` | Single claim detail |
| `GET` | `/api/analytics/summary` | KPIs: total claims, patients, reimbursed, avg LOS |
| `GET` | `/api/analytics/monthly-trend` | Monthly claim volume and spend |
| `GET` | `/api/analytics/by-state` | Claims grouped by CMS state code |
| `GET` | `/api/analytics/conditions` | Chronic condition distribution |
| `GET` | `/api/analytics/top-providers` | Top N providers by claim count |
| `GET` | `/api/patients` | Patient list with risk scores |
| `GET` | `/api/patients/{id}` | Patient profile |
| `GET` | `/api/patients/{id}/claims` | All claims for one patient |
| `GET` | `/api/ml/status` | ML model readiness check |
| `GET` | `/api/ml/metrics` | Model accuracy, ROC-AUC, feature importance |
| `GET` | `/api/ml/patient-risk/{id}` | ML risk score for a patient |
| `GET` | `/api/ml/provider-fraud/{id}` | Fraud anomaly score for a provider |
| `GET` | `/api/ml/all-fraud-scores` | All providers ranked by fraud risk |

---

## ML Model Details

### Patient Risk Classifier
- **Algorithm:** Random Forest (300 estimators)
- **Features:** Age, gender, state, claim count, total/avg/max reimbursement, avg/max LOS, unique providers
- **Target:** High-risk patient (has both diabetes AND heart failure — a validated clinical proxy)
- **Evaluation:** Accuracy, F1 score, ROC-AUC, 5-fold cross-validation

### Provider Fraud Detector
- **Algorithm:** Isolation Forest (unsupervised anomaly detection)
- **Features:** Claim volume, patient count, reimbursement stats, LOS stats, condition rates
- **Output:** Fraud risk score 0–100 per provider

---

## Project Structure

```
MedIntel/
├── requirements.txt          ← all dependencies
├── .env.example              ← environment template
├── .gitignore
├── README.md
│
├── backend/                  ← FastAPI application
│   ├── requirements.txt      ← server-only subset
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── schemas.py
│       └── routers/
│           ├── claims.py
│           ├── analytics.py
│           ├── patients.py
│           └── ml.py
│
├── ml/                       ← Machine learning
│   ├── features.py           ← feature engineering
│   ├── train.py              ← training CLI
│   ├── predict.py            ← inference utilities
│   └── models/               ← saved models (generated, not committed)
│
├── etl/                      ← Data pipeline
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   └── pipeline.py           ← CLI orchestrator
│
├── database/
│   ├── schema.sql            ← DDL: table, indexes, views
│   └── queries.sql           ← showcase SQL queries
│
├── frontend/
│   └── index.html            ← MedIntel SPA dashboard
│
└── data/
    └── healthcare_cleaned.csv  ← 1,000-row training sample
```

---

## Data Source

[CMS Healthcare Provider Fraud Detection](https://www.kaggle.com/datasets/rohitrox/healthcare-provider-fraud-detection-analysis) — public domain Medicare claims dataset. 1,000 rows sampled from merged beneficiary + inpatient data.

---

## License

MIT
