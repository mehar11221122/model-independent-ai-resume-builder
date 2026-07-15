"""Business-rule validation beyond plain schema validation - duplicate and
consistency checks called out in the scope doc's "Validation layer" deliverable."""
from app.modules.resume.schema import ResumeOutput


def check_duplicate_experience(resume: ResumeOutput) -> list[str]:
    errors = []
    seen = set()
    for exp in resume.work_experience:
        key = (exp.job_title.strip().lower(), exp.company.strip().lower())
        if key in seen:
            errors.append(
                f"Duplicate work experience entry detected: {exp.job_title} at {exp.company}"
            )
        seen.add(key)
    return errors


def check_date_consistency(resume: ResumeOutput) -> list[str]:
    errors = []
    for exp in resume.work_experience:
        if exp.start_date and exp.end_date and not exp.is_current:
            if exp.start_date > exp.end_date:
                errors.append(
                    f"Work experience at {exp.company}: start_date after end_date."
                )
    return errors


def check_minimum_content(resume: ResumeOutput) -> list[str]:
    errors = []
    if (
        not resume.work_experience
        and not resume.education
        and not resume.projects
        and not resume.volunteer_experience
    ):
        errors.append(
            "Resume has no work experience, education, projects, or volunteer "
            "experience - insufficient content."
        )
    return errors


RESUME_VALIDATORS = [
    check_duplicate_experience,
    check_date_consistency,
    check_minimum_content,
]
