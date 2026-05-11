"""
app/schemas/candidate_schema.py
================================
Pydantic schemas for candidate profile data extracted from
resumes and LinkedIn profiles.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any


class WorkExperience(BaseModel):
    """Represents a single work experience entry."""

    company: str = Field(default="", description="Company/organization name")
    title: str = Field(default="", description="Job title/role")
    duration_months: Optional[int] = Field(
        None, ge=0, description="Duration in months"
    )
    duration_text: str = Field(default="", description="Duration as text (e.g., '2 years 3 months')")
    description: str = Field(default="", description="Role description and responsibilities")
    technologies: List[str] = Field(
        default_factory=list, description="Technologies/tools used in this role"
    )
    is_current: bool = Field(default=False, description="Whether this is the current role")


class Education(BaseModel):
    """Represents a single education entry."""

    institution: str = Field(default="", description="University/college name")
    degree: str = Field(default="", description="Degree title (e.g., B.Tech, M.S.)")
    field_of_study: str = Field(default="", description="Field of study/major")
    graduation_year: Optional[int] = Field(
        None, ge=1950, le=2030, description="Year of graduation"
    )
    gpa: Optional[float] = Field(None, ge=0.0, le=10.0, description="GPA if mentioned")


class Project(BaseModel):
    """Represents a single project entry."""

    name: str = Field(default="", description="Project name")
    description: str = Field(default="", description="Project description")
    technologies: List[str] = Field(
        default_factory=list, description="Technologies used"
    )
    url: Optional[str] = Field(None, description="Project URL (GitHub, demo, etc.)")
    impact: str = Field(default="", description="Impact or outcome of the project")


class CandidateProfile(BaseModel):
    """
    Complete candidate profile extracted from resume and/or LinkedIn.
    This is the unified data model used throughout the pipeline.
    """

    # --- Identity (will be masked for PII compliance) ---
    candidate_id: str = Field(..., description="Unique identifier for the candidate")
    name: str = Field(default="", description="Candidate full name (may be masked)")
    email: str = Field(default="", description="Email address (masked)")
    phone: str = Field(default="", description="Phone number (masked)")
    location: str = Field(default="", description="City/country")

    # --- Source ---
    source: str = Field(
        default="resume",
        description="Data source: 'resume', 'linkedin', or 'combined'",
    )
    raw_text: str = Field(default="", description="Raw extracted text (not sent to LLM directly)")

    # --- Skills ---
    skills: List[str] = Field(
        default_factory=list,
        description="All identified technical and soft skills",
    )
    programming_languages: List[str] = Field(
        default_factory=list, description="Specific programming languages"
    )
    frameworks: List[str] = Field(
        default_factory=list, description="Frameworks and libraries"
    )
    tools: List[str] = Field(
        default_factory=list, description="Tools, platforms, cloud services"
    )

    # --- Experience ---
    work_experience: List[WorkExperience] = Field(
        default_factory=list, description="List of work experience entries"
    )
    total_experience_years: Optional[float] = Field(
        None, ge=0, le=60, description="Total years of professional experience"
    )
    summary: str = Field(default="", description="Professional summary/bio")

    # --- Education ---
    education: List[Education] = Field(
        default_factory=list, description="Educational background"
    )
    certifications: List[str] = Field(
        default_factory=list, description="Professional certifications"
    )

    # --- Projects ---
    projects: List[Project] = Field(
        default_factory=list, description="Notable projects"
    )

    # --- Communication Quality Indicators ---
    communication_score_raw: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Estimated communication quality score (0-100)",
    )
    writing_quality_notes: str = Field(
        default="",
        description="Notes on writing quality, clarity, and professionalism",
    )

    # --- LinkedIn Specific ---
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    connections: Optional[int] = Field(None, ge=0, description="LinkedIn connection count")
    recommendations_count: Optional[int] = Field(
        None, ge=0, description="Number of LinkedIn recommendations"
    )
    endorsements: Dict[str, int] = Field(
        default_factory=dict,
        description="Skill endorsements count map",
    )

    @field_validator("skills", "programming_languages", "frameworks", "tools", "certifications", mode="before")
    @classmethod
    def clean_skills_list(cls, v):
        """Deduplicate and clean skill lists."""
        if isinstance(v, list):
            seen = set()
            result = []
            for item in v:
                if isinstance(item, str):
                    clean = item.strip()
                    if clean and clean.lower() not in seen:
                        seen.add(clean.lower())
                        result.append(clean)
            return result
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "candidate_id": "c_abc123",
                "name": "J*** D***",
                "email": "j***@e***.com",
                "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
                "total_experience_years": 4.5,
            }
        }
