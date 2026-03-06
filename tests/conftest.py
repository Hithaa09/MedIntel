"""Shared pytest fixtures for MedIntel test suite."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ── ML / data fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def raw_df():
    from ml.features import load_cleaned_data
    return load_cleaned_data()


@pytest.fixture(scope="session")
def patient_df(raw_df):
    from ml.features import build_patient_features
    return build_patient_features(raw_df)


@pytest.fixture(scope="session")
def provider_df(raw_df):
    from ml.features import build_provider_features
    return build_provider_features(raw_df)


# ── API client fixture ────────────────────────────────────────────────────────

@pytest.fixture()
def api_client():
    """
    FastAPI TestClient with:
      - Oracle pool mocked out (no real DB required)
      - Valid JWT token injected as default Authorization header
    """
    from fastapi.testclient import TestClient

    with patch("backend.app.database.init_pool"), \
         patch("backend.app.database.close_pool"):
        from backend.app.main import app
        from backend.app.auth import create_access_token

        token = create_access_token(
            email="test@medintel.io",
            name="Test User",
            role="Analyst",
        )
        headers = {"Authorization": f"Bearer {token}"}

        with TestClient(app, headers=headers, raise_server_exceptions=False) as client:
            yield client


@pytest.fixture()
def auth_token():
    """Return a valid JWT token string for use in individual test assertions."""
    from backend.app.auth import create_access_token
    return create_access_token("test@medintel.io", "Test User", "Analyst")
