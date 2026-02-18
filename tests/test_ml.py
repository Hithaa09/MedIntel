"""Tests for ML feature engineering and inference."""
import pytest

from ml.features import PATIENT_FEATURES, PROVIDER_FEATURES


# ── Feature engineering ──────────────────────────────────────────────────────

class TestPatientFeatures:

    def test_returns_correct_columns(self, patient_df):
        expected = {"BeneID", "total_reimbursed", "high_spender"} | set(PATIENT_FEATURES)
        assert expected.issubset(set(patient_df.columns))

    def test_no_missing_feature_values(self, patient_df):
        assert patient_df[PATIENT_FEATURES].isnull().sum().sum() == 0

    def test_high_spender_is_binary(self, patient_df):
        unique_vals = set(patient_df["high_spender"].unique())
        assert unique_vals <= {0, 1}

    def test_high_spender_rate_near_25_percent(self, patient_df):
        rate = patient_df["high_spender"].mean()
        # Should be close to 25% (top quartile definition)
        assert 0.20 <= rate <= 0.30

    def test_age_is_positive(self, patient_df):
        assert (patient_df["age"] >= 0).all()

    def test_claim_count_is_positive(self, patient_df):
        assert (patient_df["claim_count"] > 0).all()

    def test_gender_values(self, patient_df):
        # Encoded gender should be 1 or 2
        assert patient_df["gender"].isin([0, 1, 2]).all()

    def test_unique_patients(self, patient_df):
        # One row per patient
        assert patient_df["BeneID"].nunique() == len(patient_df)


class TestProviderFeatures:

    def test_returns_correct_columns(self, provider_df):
        expected = {"Provider"} | set(PROVIDER_FEATURES)
        assert expected.issubset(set(provider_df.columns))

    def test_no_missing_feature_values(self, provider_df):
        assert provider_df[PROVIDER_FEATURES].isnull().sum().sum() == 0

    def test_claims_per_patient_is_positive(self, provider_df):
        assert (provider_df["claims_per_patient"] > 0).all()

    def test_rates_between_zero_and_one(self, provider_df):
        assert provider_df["diabetes_rate"].between(0, 1).all()
        assert provider_df["hf_rate"].between(0, 1).all()

    def test_unique_providers(self, provider_df):
        assert provider_df["Provider"].nunique() == len(provider_df)


# ── ML inference ─────────────────────────────────────────────────────────────

class TestMLInference:

    def test_models_ready(self):
        from ml.predict import models_ready
        assert models_ready(), (
            "Models not found — run `python -m ml.train` before running tests."
        )

    def test_patient_risk_returns_probability(self):
        from ml.predict import predict_patient_risk
        features = {
            "age": 75, "gender": 2, "state": 39, "claim_count": 3,
            "avg_los": 4.5, "max_los": 7, "unique_providers": 2,
            "has_diabetes": 1, "has_heartfailure": 0,
        }
        prob = predict_patient_risk(features)
        assert prob is not None
        assert 0.0 <= prob <= 1.0

    def test_patient_risk_high_utilisation_scores_higher(self):
        from ml.predict import predict_patient_risk
        low = predict_patient_risk({
            "age": 50, "gender": 1, "state": 10, "claim_count": 1,
            "avg_los": 1, "max_los": 2, "unique_providers": 1,
            "has_diabetes": 0, "has_heartfailure": 0,
        })
        high = predict_patient_risk({
            "age": 82, "gender": 2, "state": 10, "claim_count": 8,
            "avg_los": 12, "max_los": 20, "unique_providers": 5,
            "has_diabetes": 1, "has_heartfailure": 1,
        })
        # High-utilisation patient should have higher predicted risk
        assert high > low

    def test_fraud_score_is_in_range(self, provider_df):
        from ml.predict import get_provider_fraud_score
        provider = provider_df["Provider"].iloc[0]
        score = get_provider_fraud_score(provider)
        assert score is not None
        assert 0.0 <= score <= 100.0

    def test_fraud_scores_loaded(self):
        from ml.predict import get_all_fraud_scores
        scores = get_all_fraud_scores()
        assert len(scores) > 0

    def test_metrics_contain_expected_keys(self):
        from ml.predict import get_metrics
        m = get_metrics()
        assert "patient_risk" in m
        assert "provider_fraud" in m
        assert "roc_auc" in m["patient_risk"]
        assert "accuracy" in m["patient_risk"]
