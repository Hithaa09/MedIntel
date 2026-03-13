"""Tests for ML feature engineering and inference."""
import pytest

from ml.features import PATIENT_FEATURES, PROVIDER_FEATURES


# ── Patient features ──────────────────────────────────────────────────────────

class TestPatientFeatures:

    def test_returns_correct_columns(self, patient_df):
        expected = {"BeneID", "total_reimbursed", "spending_risk"} | set(PATIENT_FEATURES)
        assert expected.issubset(set(patient_df.columns))

    def test_no_missing_feature_values(self, patient_df):
        assert patient_df[PATIENT_FEATURES].isnull().sum().sum() == 0

    def test_spending_risk_is_binary(self, patient_df):
        assert set(patient_df["spending_risk"].unique()) <= {0, 1}

    def test_spending_risk_rate_near_25_percent(self, patient_df):
        rate = patient_df["spending_risk"].mean()
        assert 0.20 <= rate <= 0.30

    def test_age_is_positive(self, patient_df):
        assert (patient_df["age"] >= 0).all()

    def test_gender_values(self, patient_df):
        assert patient_df["gender"].isin([0, 1, 2]).all()

    def test_unique_patients(self, patient_df):
        assert patient_df["BeneID"].nunique() == len(patient_df)

    def test_claim_count_not_a_feature(self, patient_df):
        # claim_count is intentionally excluded to avoid mechanical leakage
        assert "claim_count" not in PATIENT_FEATURES


# ── Provider features ─────────────────────────────────────────────────────────

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


# ── ML inference ──────────────────────────────────────────────────────────────

class TestMLInference:

    def test_models_ready(self):
        from ml.predict import models_ready
        assert models_ready(), "Run `python -m ml.train` before running tests."

    def test_spending_risk_returns_probability(self):
        from ml.predict import predict_patient_spending_risk
        features = {
            "age": 75, "gender": 2, "state": 39,
            "avg_los": 4.5, "max_los": 7, "unique_providers": 2,
            "has_diabetes": 1, "has_heartfailure": 0,
        }
        prob = predict_patient_spending_risk(features)
        assert prob is not None
        assert 0.0 <= prob <= 1.0

    def test_high_risk_profile_scores_higher(self):
        from ml.predict import predict_patient_spending_risk
        low = predict_patient_spending_risk({
            "age": 50, "gender": 1, "state": 10,
            "avg_los": 1, "max_los": 2, "unique_providers": 1,
            "has_diabetes": 0, "has_heartfailure": 0,
        })
        high = predict_patient_spending_risk({
            "age": 82, "gender": 2, "state": 10,
            "avg_los": 12, "max_los": 20, "unique_providers": 5,
            "has_diabetes": 1, "has_heartfailure": 1,
        })
        assert high > low

    def test_fraud_score_is_in_range(self, provider_df):
        from ml.predict import get_provider_fraud_score
        score = get_provider_fraud_score(provider_df["Provider"].iloc[0])
        assert score is not None
        assert 0.0 <= score <= 100.0

    def test_fraud_scores_loaded(self):
        from ml.predict import get_all_fraud_scores
        assert len(get_all_fraud_scores()) > 0

    def test_metrics_contain_expected_keys(self):
        from ml.predict import get_metrics
        m = get_metrics()
        # Key is patient_spending_risk (renamed from patient_risk)
        key = "patient_spending_risk" if "patient_spending_risk" in m else "patient_risk"
        assert key in m
        assert "roc_auc"   in m[key]
        assert "accuracy"  in m[key]
        assert "provider_fraud" in m
