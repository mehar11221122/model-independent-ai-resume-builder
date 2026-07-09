from app.modules.resume.schema import ContactInfo, ResumeOutput, WorkExperience
from app.modules.resume.validation import (
    check_date_consistency,
    check_duplicate_experience,
    check_minimum_content,
)


def _resume(**overrides) -> ResumeOutput:
    defaults = dict(
        language="en",
        contact=ContactInfo(full_name="Jane Sample"),
        work_experience=[],
        education=[],
        projects=[],
    )
    defaults.update(overrides)
    return ResumeOutput(**defaults)


def test_no_errors_on_valid_resume():
    resume = _resume(
        work_experience=[
            WorkExperience(job_title="Engineer", company="Example Corp", start_date="2020-01", end_date="2022-01")
        ]
    )
    assert check_duplicate_experience(resume) == []
    assert check_date_consistency(resume) == []
    assert check_minimum_content(resume) == []


def test_detects_duplicate_experience():
    exp = WorkExperience(job_title="Engineer", company="Example Corp")
    resume = _resume(work_experience=[exp, exp])
    assert len(check_duplicate_experience(resume)) == 1


def test_detects_date_inconsistency():
    resume = _resume(
        work_experience=[
            WorkExperience(
                job_title="Engineer",
                company="Example Corp",
                start_date="2022-01",
                end_date="2020-01",
            )
        ]
    )
    assert len(check_date_consistency(resume)) == 1


def test_detects_insufficient_content():
    resume = _resume()
    assert len(check_minimum_content(resume)) == 1
