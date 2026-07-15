"""Unit tests for the resume vertical's LangChain tools."""
from app.modules.resume.tools import compute_duration, normalize_date


def test_normalize_date_full_date():
    assert normalize_date.invoke({"date_str": "March 15, 2023"}) == "2023-03"


def test_normalize_date_month_year():
    assert normalize_date.invoke({"date_str": "Jan 2022"}) == "2022-01"


def test_normalize_date_year_only_passthrough():
    assert normalize_date.invoke({"date_str": "2022"}) == "2022"


def test_normalize_date_empty_passthrough():
    assert normalize_date.invoke({"date_str": ""}) == ""


def test_normalize_date_unparseable_passthrough():
    assert normalize_date.invoke({"date_str": "sometime last year"}) == "sometime last year"


def test_compute_duration_years_and_months():
    result = compute_duration.invoke({"start_date": "2022-01", "end_date": "2024-04"})
    assert "2 year" in result
    assert "3 month" in result


def test_compute_duration_present_uses_today():
    result = compute_duration.invoke({"start_date": "2020-01", "end_date": "present"})
    assert "year" in result or "month" in result


def test_compute_duration_missing_start_is_unknown():
    assert compute_duration.invoke({"start_date": "", "end_date": "2024"}) == "unknown duration"


def test_compute_duration_less_than_a_month():
    result = compute_duration.invoke({"start_date": "2024-01-01", "end_date": "2024-01-10"})
    assert result == "less than a month"
