"""Unit tests for the deeper resume completeness checks that make gap
detection ask for more than just the bare-minimum required fields."""
from app.graph.nodes import build_gap_check_node
from app.modules.resume.completeness import (
    FIELD_ACHIEVEMENTS,
    FIELD_JOB_TITLES_AND_DATES,
    FIELD_SUMMARY,
    check_resume_completeness,
)
from app.modules.resume.config import RESUME_VERTICAL


def test_flags_missing_job_title_and_dates():
    extracted = {"work_experience": [{"company": "Flogen"}]}
    assert FIELD_JOB_TITLES_AND_DATES in check_resume_completeness(extracted)


def test_does_not_flag_job_title_and_dates_when_complete():
    extracted = {
        "work_experience": [
            {"job_title": "Engineer", "company": "Flogen", "start_date": "2022"}
        ]
    }
    assert FIELD_JOB_TITLES_AND_DATES not in check_resume_completeness(extracted)


def test_does_not_reflag_job_title_and_dates_once_answered():
    extracted = {
        "work_experience": [{"company": "Flogen"}],
        FIELD_JOB_TITLES_AND_DATES: "I was a Backend Developer, Jan 2022 - present",
    }
    assert FIELD_JOB_TITLES_AND_DATES not in check_resume_completeness(extracted)


def test_flags_missing_summary_and_achievements():
    extracted = {"work_experience": [{"job_title": "Engineer", "company": "Flogen"}]}
    missing = check_resume_completeness(extracted)
    assert FIELD_SUMMARY in missing
    assert FIELD_ACHIEVEMENTS in missing


def test_no_achievements_flag_without_any_work_experience():
    extracted = {}
    assert FIELD_ACHIEVEMENTS not in check_resume_completeness(extracted)


def test_gap_check_node_merges_required_and_extra_missing_fields():
    gap_check = build_gap_check_node(RESUME_VERTICAL)
    extracted = {
        "full_name": "Mehar",
        "email": "mehar@example.com",
        "work_experience": [{"company": "Flogen"}],
    }
    result = gap_check({"extracted_data": extracted})

    assert "education" in result["missing_fields"]
    assert "skills" in result["missing_fields"]
    assert FIELD_JOB_TITLES_AND_DATES in result["missing_fields"]
    assert FIELD_SUMMARY in result["missing_fields"]
    assert "full_name" not in result["missing_fields"]
    assert "email" not in result["missing_fields"]
