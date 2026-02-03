from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from ..database import get_conn
from ..schemas import Claim, ClaimPage

router = APIRouter()

_SELECT = """
    SELECT id, bene_id, dob, gender, race, state,
           chroniccond_diabetes, chroniccond_heartfailure,
           claim_id, claimstartdt, claimenddt,
           provider, inscclaimamtreimbursed,
           attendingphysician, admissiondt, dischargedt
    FROM   healthcare_claims
"""


def _row_to_claim(row) -> Claim:
    return Claim(
        id=row[0],
        bene_id=row[1],
        dob=row[2],
        gender=row[3],
        race=row[4],
        state=row[5],
        chroniccond_diabetes=row[6],
        chroniccond_heartfailure=row[7],
        claim_id=row[8],
        claimstartdt=row[9],
        claimenddt=row[10],
        provider=row[11],
        inscclaimamtreimbursed=float(row[12]) if row[12] is not None else None,
        attendingphysician=row[13],
        admissiondt=row[14],
        dischargedt=row[15],
    )


@router.get("", response_model=ClaimPage, summary="List claims (paginated)")
def list_claims(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    state: Optional[int] = Query(None, description="CMS state code"),
    gender: Optional[int] = Query(None, ge=1, le=2),
    provider: Optional[str] = Query(None),
    diabetes: Optional[int] = Query(None, ge=1, le=2),
    heartfailure: Optional[int] = Query(None, ge=1, le=2),
):
    filters, params = [], {}
    if state is not None:
        filters.append("state = :state"); params["state"] = state
    if gender is not None:
        filters.append("gender = :gender"); params["gender"] = gender
    if provider:
        filters.append("provider = :provider"); params["provider"] = provider.upper()
    if diabetes is not None:
        filters.append("chroniccond_diabetes = :diabetes"); params["diabetes"] = diabetes
    if heartfailure is not None:
        filters.append("chroniccond_heartfailure = :hf"); params["hf"] = heartfailure

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    offset = (page - 1) * page_size
    params.update({"limit": page_size, "offset": offset})

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM healthcare_claims {where}", params)
        total = cur.fetchone()[0]

        cur.execute(
            f"{_SELECT} {where} ORDER BY id OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY",
            params,
        )
        items = [_row_to_claim(r) for r in cur.fetchall()]

    return ClaimPage(total=total, page=page, page_size=page_size, items=items)


@router.get("/{claim_id}", response_model=Claim, summary="Get single claim by claim_id")
def get_claim(claim_id: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"{_SELECT} WHERE claim_id = :cid", {"cid": claim_id.upper()})
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return _row_to_claim(row)
