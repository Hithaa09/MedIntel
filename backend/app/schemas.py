from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Claim ──────────────────────────────────────────────────────────────────

class Claim(BaseModel):
    id: int
    bene_id: str
    dob: Optional[date]
    gender: Optional[int]
    race: Optional[int]
    state: Optional[int]
    chroniccond_diabetes: Optional[int]
    chroniccond_heartfailure: Optional[int]
    claim_id: str
    claimstartdt: Optional[date]
    claimenddt: Optional[date]
    provider: Optional[str]
    inscclaimamtreimbursed: Optional[float]
    attendingphysician: Optional[str]
    admissiondt: Optional[date]
    dischargedt: Optional[date]


class ClaimPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[Claim]


# ── Analytics ──────────────────────────────────────────────────────────────

class Summary(BaseModel):
    total_claims: int
    unique_patients: int
    total_reimbursed: float
    avg_reimbursed: float
    avg_los_days: Optional[float]


class StateCount(BaseModel):
    state: Optional[int]
    total_claims: int
    total_reimbursed: float


class ConditionStats(BaseModel):
    diabetes_yes: int
    diabetes_no: int
    heartfailure_yes: int
    heartfailure_no: int
    both_conditions: int


class ProviderStat(BaseModel):
    provider: str
    total_claims: int
    unique_patients: int
    total_reimbursed: float
    avg_reimbursed: float
    avg_los_days: Optional[float]


class MonthlyPoint(BaseModel):
    month_label: str
    total_claims: int
    total_reimbursed: float
    unique_patients: int
    avg_los_days: Optional[float]


# ── Patient ────────────────────────────────────────────────────────────────

class PatientSummary(BaseModel):
    bene_id: str
    dob: Optional[date]
    gender: Optional[int]
    race: Optional[int]
    state: Optional[int]
    chroniccond_diabetes: Optional[int]
    chroniccond_heartfailure: Optional[int]
    total_claims: int
    lifetime_reimbursed: float
    risk_level: str
