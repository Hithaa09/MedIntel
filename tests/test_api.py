"""Tests for FastAPI endpoints (DB-independent)."""
from unittest.mock import MagicMock, patch

import pytest


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_returns_200(api_client):
    resp = api_client.get("/api/health")
    assert resp.status_code == 200


def test_health_response_schema(api_client):
    resp = api_client.get("/api/health")
    body = resp.json()
    assert "status" in body
    assert body["status"] == "ok"
    assert "version" in body


# ── ML status ─────────────────────────────────────────────────────────────────

def test_ml_status_endpoint_reachable(api_client):
    resp = api_client.get("/api/ml/status")
    assert resp.status_code == 200


def test_ml_status_schema(api_client):
    resp = api_client.get("/api/ml/status")
    body = resp.json()
    assert "models_ready" in body
    assert isinstance(body["models_ready"], bool)
    assert "message" in body


def test_ml_metrics_endpoint(api_client):
    resp = api_client.get("/api/ml/metrics")
    # Either returns metrics (200) or 503 if not trained
    assert resp.status_code in (200, 503)


# ── Claims (mocked DB) ────────────────────────────────────────────────────────

def _make_claim_row():
    from datetime import date
    return (
        1, "BENE001", date(1940, 1, 1), 1, 1, 39,
        1, 2,
        "CLM001", date(2009, 1, 1), date(2009, 1, 5),
        "PRV001", 5000.0,
        "PHY001", date(2009, 1, 1), date(2009, 1, 5),
    )


def test_claims_endpoint_with_mock_db(api_client):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)   # COUNT(*)
    mock_cursor.fetchall.return_value = [_make_claim_row()]

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    with patch("backend.app.routers.claims.get_conn", return_value=mock_conn):
        resp = api_client.get("/api/claims?page=1&page_size=20")

    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert "items" in body
    assert isinstance(body["items"], list)


def test_claims_pagination_params(api_client):
    """Bad page_size should return 422 validation error."""
    resp = api_client.get("/api/claims?page_size=9999")
    assert resp.status_code == 422


# ── Analytics (mocked DB) ─────────────────────────────────────────────────────

def test_analytics_summary_schema(api_client):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1000, 743, 2800000.0, 2800.0, 4.2)

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    with patch("backend.app.routers.analytics.get_conn", return_value=mock_conn):
        resp = api_client.get("/api/analytics/summary")

    assert resp.status_code == 200
    body = resp.json()
    for key in ("total_claims", "unique_patients", "total_reimbursed",
                "avg_reimbursed", "avg_los_days"):
        assert key in body


# ── Patients ──────────────────────────────────────────────────────────────────

def test_patient_not_found_returns_404(api_client):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    with patch("backend.app.routers.patients.get_conn", return_value=mock_conn):
        resp = api_client.get("/api/patients/BENE_DOES_NOT_EXIST")

    assert resp.status_code == 404
