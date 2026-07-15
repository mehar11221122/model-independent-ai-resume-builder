from app.modules.resume.schema import (
    Award,
    ContactInfo,
    Publication,
    ResumeOutput,
    VolunteerExperience,
    WorkExperience,
)
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


def test_volunteer_only_resume_counts_as_sufficient_content():
    resume = _resume(
        volunteer_experience=[
            VolunteerExperience(role="Coordinator", organization="Local Shelter")
        ]
    )
    assert check_minimum_content(resume) == []


def test_optional_sections_default_to_empty():
    resume = _resume()
    assert resume.volunteer_experience == []
    assert resume.awards == []
    assert resume.publications == []
    assert resume.affiliations == []
    assert resume.contact.headline is None
    assert resume.references_note is None


def test_optional_sections_accept_data():
    resume = _resume(
        contact=ContactInfo(full_name="Jane Sample", headline="Senior Engineer"),
        awards=[Award(title="Employee of the Year", issuer="Example Corp", date="2023")],
        publications=[Publication(title="Scaling APIs", publisher="Tech Journal")],
        affiliations=["Member, IEEE"],
        references_note="Available upon request",
    )
    assert resume.contact.headline == "Senior Engineer"
    assert resume.awards[0].title == "Employee of the Year"
    assert resume.publications[0].title == "Scaling APIs"
    assert resume.affiliations == ["Member, IEEE"]
    assert resume.references_note == "Available upon request"
