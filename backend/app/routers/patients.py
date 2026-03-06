from fastapi import APIRouter, Depends, HTTPException, Query
from ..auth import get_current_user
from ..database import get_conn
from ..schemas import PatientSummary, Claim, ClaimPage

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PatientSummary], summary="List patients with risk scores")
def list_patients(
    limit: int = Query(50, ge=1, le=200),
    risk: str = Query(None, description="High | Medium | Low"),
):
    sql = """
        SELECT bene_id, dob, gender, race, state,
               chroniccond_diabetes, chroniccond_heartfailure,
               COUNT(claim_id)             AS total_claims,
               SUM(inscclaimamtreimbursed) AS lifetime_reimbursed,
               CASE
                 WHEN chroniccond_diabetes = 1 AND chroniccond_heartfailure = 1 THEN 'High'
                 WHEN chroniccond_diabetes = 1 OR  chroniccond_heartfailure = 1 THEN 'Medium'
                 ELSE 'Low'
               END AS risk_level
        FROM   healthcare_claims
        GROUP  BY bene_id, dob, gender, race, state,
                  chroniccond_diabetes, chroniccond_heartfailure
        ORDER  BY lifetime_reimbursed DESC
        FETCH FIRST :lim ROWS ONLY
    """
    params: dict = {"lim": limit}

    # Apply risk filter with a wrapper query
    if risk and risk in ("High", "Medium", "Low"):
        sql = f"""
            SELECT * FROM (
                SELECT bene_id, dob, gender, race, state,
                       chroniccond_diabetes, chroniccond_heartfailure,
                       COUNT(claim_id)             AS total_claims,
                       SUM(inscclaimamtreimbursed) AS lifetime_reimbursed,
                       CASE
                         WHEN chroniccond_diabetes = 1 AND chroniccond_heartfailure = 1 THEN 'High'
                         WHEN chroniccond_diabetes = 1 OR  chroniccond_heartfailure = 1 THEN 'Medium'
                         ELSE 'Low'
                       END AS risk_level
                FROM   healthcare_claims
                GROUP  BY bene_id, dob, gender, race, state,
                          chroniccond_diabetes, chroniccond_heartfailure
            )
            WHERE  risk_level = :risk
            ORDER  BY lifetime_reimbursed DESC
            FETCH FIRST :lim ROWS ONLY
        """
        params["risk"] = risk

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        PatientSummary(
            bene_id=r[0],
            dob=r[1],
            gender=r[2],
            race=r[3],
            state=r[4],
            chroniccond_diabetes=r[5],
            chroniccond_heartfailure=r[6],
            total_claims=r[7],
            lifetime_reimbursed=float(r[8] or 0),
            risk_level=r[9],
        )
        for r in rows
    ]


@router.get("/{bene_id}", response_model=PatientSummary, summary="Get single patient profile")
def get_patient(bene_id: str):
    sql = """
        SELECT bene_id, dob, gender, race, state,
               chroniccond_diabetes, chroniccond_heartfailure,
               COUNT(claim_id)             AS total_claims,
               SUM(inscclaimamtreimbursed) AS lifetime_reimbursed,
               CASE
                 WHEN chroniccond_diabetes = 1 AND chroniccond_heartfailure = 1 THEN 'High'
                 WHEN chroniccond_diabetes = 1 OR  chroniccond_heartfailure = 1 THEN 'Medium'
                 ELSE 'Low'
               END AS risk_level
        FROM   healthcare_claims
        WHERE  bene_id = :bid
        GROUP  BY bene_id, dob, gender, race, state,
                  chroniccond_diabetes, chroniccond_heartfailure
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, {"bid": bene_id.upper()})
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Patient '{bene_id}' not found")

    return PatientSummary(
        bene_id=row[0],
        dob=row[1],
        gender=row[2],
        race=row[3],
        state=row[4],
        chroniccond_diabetes=row[5],
        chroniccond_heartfailure=row[6],
        total_claims=row[7],
        lifetime_reimbursed=float(row[8] or 0),
        risk_level=row[9],
    )


@router.get("/{bene_id}/claims", response_model=ClaimPage, summary="All claims for a patient")
def patient_claims(bene_id: str, page: int = 1, page_size: int = 20):
    offset = (page - 1) * page_size
    params = {"bid": bene_id.upper(), "limit": page_size, "offset": offset}

    select = """
        SELECT id, bene_id, dob, gender, race, state,
               chroniccond_diabetes, chroniccond_heartfailure,
               claim_id, claimstartdt, claimenddt,
               provider, inscclaimamtreimbursed,
               attendingphysician, admissiondt, dischargedt
        FROM   healthcare_claims
        WHERE  bene_id = :bid
    """

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM healthcare_claims WHERE bene_id = :bid", {"bid": bene_id.upper()})
        total = cur.fetchone()[0]
        if total == 0:
            raise HTTPException(status_code=404, detail=f"Patient '{bene_id}' not found")

        cur.execute(
            f"{select} ORDER BY claimstartdt OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY",
            params,
        )
        rows = cur.fetchall()

    from .claims import _row_to_claim
    return ClaimPage(
        total=total, page=page, page_size=page_size,
        items=[_row_to_claim(r) for r in rows],
    )
