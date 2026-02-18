"""Tests for ETL transform functions."""
import pandas as pd
import pytest

from etl.transform import clean


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "BeneID":                 ["B001", "B002", "B003", "B001"],  # B001 duplicate
        "DOB":                    ["1940-05-01", "bad-date", None, "1940-05-01"],
        "Gender":                 ["1", "2", None, "1"],
        "Race":                   ["1", "2", "1", "1"],
        "State":                  ["10", "33", None, "10"],
        "ChronicCond_Diabetes":   ["1", "2", "1", "1"],
        "ChronicCond_Heartfailure": ["2", "1", "2", "2"],
        "ClaimID":                ["C001", "C002", "C003", "C001"],
        "ClaimStartDt":           ["2009-01-01", "2009-03-15", "bad", "2009-01-01"],
        "ClaimEndDt":             ["2009-01-05", "2009-03-18", None, "2009-01-05"],
        "Provider":               ["PRV001", None, "PRV003", "PRV001"],
        "InscClaimAmtReimbursed": ["5000", "abc", None, "5000"],
        "AttendingPhysician":     ["PHY001", "PHY002", None, "PHY001"],
        "AdmissionDt":            ["2009-01-01", "2009-03-15", None, "2009-01-01"],
        "DischargeDt":            ["2009-01-05", "2009-03-18", None, "2009-01-05"],
    })


def test_clean_removes_duplicates(sample_df):
    result = clean(sample_df)
    assert len(result) == 3  # B001 duplicate removed


def test_clean_date_columns(sample_df):
    result = clean(sample_df)
    # Valid dates become ISO strings
    assert result.loc[result["BeneID"] == "B001", "DOB"].iloc[0] == "1940-05-01"
    # Bad dates become NaT → NaN string (NaN is fine, just not a wrong date)
    b002_dob = result.loc[result["BeneID"] == "B002", "DOB"].iloc[0]
    assert b002_dob != "bad-date"


def test_clean_numeric_coercion(sample_df):
    result = clean(sample_df)
    # "abc" reimbursement → 0
    b002 = result.loc[result["BeneID"] == "B002", "InscClaimAmtReimbursed"].iloc[0]
    assert b002 == 0
    # Valid amount stays numeric
    b001 = result.loc[result["BeneID"] == "B001", "InscClaimAmtReimbursed"].iloc[0]
    assert b001 == 5000


def test_clean_condition_flags(sample_df):
    result = clean(sample_df)
    # Valid flags remain
    b001_diabetes = result.loc[result["BeneID"] == "B001", "ChronicCond_Diabetes"].iloc[0]
    assert b001_diabetes in (1, 2)


def test_clean_preserves_row_count_minimum(sample_df):
    result = clean(sample_df)
    assert len(result) >= 1


def test_clean_returns_dataframe(sample_df):
    result = clean(sample_df)
    assert isinstance(result, pd.DataFrame)
