"""
app/schemas/report_schema.py
=============================
Pydantic schema for the final report data structure.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SkillGapSummary(BaseModel):
    """Aggregated skill gap analysis across all candidates."""

    skill: str
    candidates_with_skill: int
    percentage: float


class ReportData(BaseModel):
    """
    Complete report data structure passed to the report generator.
    Contains all ranked candidates, analytics, and metadata.
    """

    report_id: str = Field(..., description="Unique report identifier")
    generated_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="UTC timestamp of report generation",
    )

    # --- Job Info ---
    job_title: str = Field(..., description="Position being recruited for")
    job_summary: str = Field(default="", description="Brief job description summary")
    required_skills: List[str] = Field(default_factory=list)
    total_candidates_evaluated: int = Field(...)

    # --- Results ---
    ranked_candidates: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of RankedCandidate dicts ordered by rank",
    )
    shortlisted_count: int = Field(
        default=0, description="Candidates recommended for hire"
    )
    no_hire_count: int = Field(default=0)
    review_count: int = Field(default=0)

    # --- Analytics ---
    average_score: float = Field(default=0.0, ge=0.0, le=100.0)
    highest_score: float = Field(default=0.0, ge=0.0, le=100.0)
    lowest_score: float = Field(default=0.0, ge=0.0, le=100.0)

    skill_gap_analysis: List[SkillGapSummary] = Field(
        default_factory=list,
        description="Common skill gaps across all candidates",
    )

    # --- Overrides ---
    overrides_applied: int = Field(
        default=0, description="Number of HR manual overrides applied"
    )

    # --- File Paths ---
    pdf_path: Optional[str] = Field(None, description="Path to generated PDF report")
    json_path: Optional[str] = Field(None, description="Path to JSON export")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
