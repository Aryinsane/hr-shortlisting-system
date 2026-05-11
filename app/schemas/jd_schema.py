"""
app/schemas/jd_schema.py
========================
Pydantic schema for structured Job Description data.
Enforces strict validation to prevent hallucinated outputs.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class JobDescription(BaseModel):
    """
    Structured representation of a parsed Job Description.
    All fields are validated to ensure LLM outputs are well-formed.
    """

    title: str = Field(..., description="Job title/position name", min_length=2, max_length=200)
    company: Optional[str] = Field(None, description="Company name if mentioned")
    summary: str = Field(..., description="Brief summary of the role", min_length=10)

    required_skills: List[str] = Field(
        default_factory=list,
        description="List of required technical/functional skills",
    )
    preferred_skills: List[str] = Field(
        default_factory=list,
        description="List of nice-to-have skills",
    )
    required_experience_years: Optional[float] = Field(
        None,
        ge=0,
        le=50,
        description="Minimum years of experience required",
    )
    experience_description: str = Field(
        default="",
        description="Qualitative description of required experience",
    )

    required_education: str = Field(
        default="",
        description="Education level or field required",
    )
    preferred_certifications: List[str] = Field(
        default_factory=list,
        description="Preferred certifications or credentials",
    )

    responsibilities: List[str] = Field(
        default_factory=list,
        description="Key job responsibilities",
    )
    domain: str = Field(
        default="",
        description="Industry/domain (e.g., Software Engineering, Data Science)",
    )

    keywords: List[str] = Field(
        default_factory=list,
        description="Important keywords extracted for semantic matching",
    )

    @field_validator("required_skills", "preferred_skills", "keywords", mode="before")
    @classmethod
    def clean_list_items(cls, v):
        """Strip whitespace from list items and remove empty strings."""
        if isinstance(v, list):
            return [item.strip() for item in v if isinstance(item, str) and item.strip()]
        return v

    @field_validator("title", "summary", mode="before")
    @classmethod
    def strip_strings(cls, v):
        """Strip whitespace from string fields."""
        return v.strip() if isinstance(v, str) else v

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Senior Python Developer",
                "company": "TechCorp Inc.",
                "summary": "We are looking for an experienced Python developer...",
                "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "preferred_skills": ["Kubernetes", "AWS", "Redis"],
                "required_experience_years": 3.0,
                "experience_description": "3+ years of backend development",
                "required_education": "B.Tech/B.E. in Computer Science or related field",
                "preferred_certifications": ["AWS Certified Developer"],
                "responsibilities": ["Design REST APIs", "Code reviews"],
                "domain": "Software Engineering",
                "keywords": ["Python", "REST", "microservices", "API"],
            }
        }
