from fastapi import APIRouter, Depends
from ..auth import get_current_user
from ..database import get_conn
from ..schemas import (
    Summary, StateCount, ConditionStats, ProviderStat, MonthlyPoint
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/summary", response_model=Summary, summary="High-level KPIs")
def summary():
    sql = """
        SELECT
            COUNT(*)                                    AS total_claims,
            COUNT(DISTINCT bene_id)                     AS unique_patients,
            SUM(inscclaimamtreimbursed)                 AS total_reimbursed,
            ROUND(AVG(inscclaimamtreimbursed)::numeric, 2) AS avg_reimbursed,
            ROUND(AVG(dischargedt - admissiondt)::numeric, 1) AS avg_los_days
        FROM healthcare_claims
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
    return Summary(
        total_claims=row[0],
        unique_patients=row[1],
        total_reimbursed=float(row[2] or 0),
        avg_reimbursed=float(row[3] or 0),
        avg_los_days=float(row[4]) if row[4] is not None else None,
    )


@router.get("/by-state", response_model=list[StateCount], summary="Claims grouped by state")
def by_state():
    sql = """
        SELECT state,
               COUNT(*)                AS total_claims,
               SUM(inscclaimamtreimbursed) AS total_reimbursed
        FROM   healthcare_claims
        GROUP  BY state
        ORDER  BY total_claims DESC
        LIMIT  20
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        StateCount(state=r[0], total_claims=r[1], total_reimbursed=float(r[2] or 0))
        for r in rows
    ]


@router.get("/conditions", response_model=ConditionStats, summary="Chronic condition breakdown")
def conditions():
    sql = """
        SELECT
            SUM(CASE WHEN chroniccond_diabetes    = 1 THEN 1 ELSE 0 END) AS d_yes,
            SUM(CASE WHEN chroniccond_diabetes    = 2 THEN 1 ELSE 0 END) AS d_no,
            SUM(CASE WHEN chroniccond_heartfailure = 1 THEN 1 ELSE 0 END) AS hf_yes,
            SUM(CASE WHEN chroniccond_heartfailure = 2 THEN 1 ELSE 0 END) AS hf_no,
            SUM(CASE WHEN chroniccond_diabetes    = 1
                      AND chroniccond_heartfailure = 1 THEN 1 ELSE 0 END) AS both_conds
        FROM healthcare_claims
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
    return ConditionStats(
        diabetes_yes=row[0] or 0,
        diabetes_no=row[1] or 0,
        heartfailure_yes=row[2] or 0,
        heartfailure_no=row[3] or 0,
        both_conditions=row[4] or 0,
    )


@router.get("/top-providers", response_model=list[ProviderStat], summary="Top providers by claim volume")
def top_providers(limit: int = 10):
    sql = """
        SELECT provider,
               COUNT(*)                                       AS total_claims,
               COUNT(DISTINCT bene_id)                        AS unique_patients,
               SUM(inscclaimamtreimbursed)                    AS total_reimbursed,
               ROUND(AVG(inscclaimamtreimbursed)::numeric, 2) AS avg_reimbursed,
               ROUND(AVG(dischargedt - admissiondt)::numeric, 1) AS avg_los_days
        FROM   healthcare_claims
        WHERE  provider IS NOT NULL
        GROUP  BY provider
        ORDER  BY total_claims DESC
        LIMIT  %(lim)s
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, {"lim": limit})
        rows = cur.fetchall()
    return [
        ProviderStat(
            provider=r[0],
            total_claims=r[1],
            unique_patients=r[2],
            total_reimbursed=float(r[3] or 0),
            avg_reimbursed=float(r[4] or 0),
            avg_los_days=float(r[5]) if r[5] is not None else None,
        )
        for r in rows
    ]


@router.get("/monthly-trend", response_model=list[MonthlyPoint], summary="Monthly claim volume and spend")
def monthly_trend():
    sql = """
        SELECT TO_CHAR(claimstartdt, 'YYYY-MM')                  AS month_label,
               COUNT(*)                                           AS total_claims,
               SUM(inscclaimamtreimbursed)                        AS total_reimbursed,
               COUNT(DISTINCT bene_id)                            AS unique_patients,
               ROUND(AVG(dischargedt - admissiondt)::numeric, 1)  AS avg_los_days
        FROM   healthcare_claims
        WHERE  claimstartdt IS NOT NULL
        GROUP  BY TO_CHAR(claimstartdt, 'YYYY-MM')
        ORDER  BY month_label
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        MonthlyPoint(
            month_label=r[0],
            total_claims=r[1],
            total_reimbursed=float(r[2] or 0),
            unique_patients=r[3] or 0,
            avg_los_days=float(r[4]) if r[4] is not None else None,
        )
        for r in rows
    ]
