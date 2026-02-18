"""Shared pytest fixtures for MedIntel test suite."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def raw_df():
    """Load the cleaned CSV once for the whole test session."""
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


@pytest.fixture()
def api_client():
    """FastAPI TestClient with Oracle pool mocked out."""
    from fastapi.testclient import TestClient

    with patch("backend.app.database.init_pool"), \
         patch("backend.app.database.close_pool"):
        from backend.app.main import app
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
