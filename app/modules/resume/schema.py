"""Structured output contract for the Resume vertical.

This is the *only* resume-specific piece of the data model - the engine core
never imports it directly, it only receives it via VerticalConfig.output_schema.
"""
from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    full_name: str
    # The professional title/tagline shown right under the name on most
    # resumes (e.g. "Senior Backend Engineer") - distinct from `summary`,
    # which is the longer paragraph beneath it.
    headline: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    portfolio_url: str | None = None


class WorkExperience(BaseModel):
    job_title: str
    company: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    responsibilities: list[str] = Field(default_factory=list)


class Education(BaseModel):
    degree: str
    institution: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    gpa: str | None = None


class Project(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class VolunteerExperience(BaseModel):
    role: str
    organization: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    description: list[str] = Field(default_factory=list)


class Award(BaseModel):
    title: str
    issuer: str | None = None
    date: str | None = None
    description: str | None = None


class Publication(BaseModel):
    title: str
    publisher: str | None = None
    date: str | None = None
    url: str | None = None


class ResumeOutput(BaseModel):
    language: str = Field(description="Resume language: 'en' or 'ar'")
    contact: ContactInfo
    summary: str | None = None
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    volunteer_experience: list[VolunteerExperience] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    # Professional memberships/affiliations (e.g. "Member, IEEE") - kept as
    # plain strings like skills/certifications since they're rarely more
    # than a name + optional org, not worth a nested model.
    affiliations: list[str] = Field(default_factory=list)
    # Most resumes either omit this entirely or just say "available upon
    # request" - kept as a single optional line rather than a structured
    # list of real contacts, which candidates should never need to type
    # into a public-facing tool like this one.
    references_note: str | None = None
