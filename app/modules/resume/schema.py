"""Structured output contract for the Resume vertical.

This is the *only* resume-specific piece of the data model - the engine core
never imports it directly, it only receives it via VerticalConfig.output_schema.
"""
from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    full_name: str
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
    gpa: str | None = None


class Project(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
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
