"""
app/schemas/score_schema.py
============================
Pydantic schemas for candidate scoring and ranking results.
Enforces structured outputs from the scoring agent.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal


class DimensionScore(BaseModel):
    """Score and justification for a single scoring dimension."""

    dimension: str = Field(..., description="Scoring dimension name")
    score: float = Field(..., ge=0.0, le=100.0, description="Raw score (0-100)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight applied to this dimension")
    weighted_score: float = Field(..., ge=0.0, le=100.0, description="Weight * score")
    justification: str = Field(
        ...,
        min_length=5,
        description="One-line justification for this dimension score",
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Specific evidence from resume/LinkedIn supporting the score",
    )


class CandidateScore(BaseModel):
    """
    Complete scoring result for a single candidate.
    Contains dimension scores, total score, and hire recommendation.
    """

    candidate_id: str = Field(..., description="Links back to CandidateProfile.candidate_id")
    candidate_name: str = Field(default="", description="Masked candidate name")

    # --- Dimension Scores ---
    skills_match: DimensionScore = Field(..., description="Skills match score (30%)")
    experience_relevance: DimensionScore = Field(
        ..., description="Experience relevance score (25%)"
    )
    education_certifications: DimensionScore = Field(
        ..., description="Education & certifications score (15%)"
    )
    projects_portfolio: DimensionScore = Field(
        ..., description="Projects/portfolio score (20%)"
    )
    communication_quality: DimensionScore = Field(
        ..., description="Communication quality score (10%)"
    )

    # --- Aggregate ---
    total_score: float = Field(..., ge=0.0, le=100.0, description="Weighted total score")
    recommendation: Literal["Hire", "No-Hire", "Review"] = Field(
        ...,
        description="Hire recommendation: Hire (>=65), No-Hire (<50), Review (50-64)",
    )
    overall_summary: str = Field(
        ..., description="2-3 sentence overall candidate evaluation"
    )

    # --- Semantic Similarity ---
    semantic_similarity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="FAISS cosine similarity score (0-1)",
    )

    # --- Skill Gap ---
    matched_skills: List[str] = Field(
        default_factory=list,
        description="Skills matching JD requirements",
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Required JD skills not found in candidate profile",
    )

    # --- Confidence ---
    confidence_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Model confidence in the evaluation (0-1)",
    )
    needs_human_review: bool = Field(
        default=False,
        description="Flag for HR review (low confidence or borderline score)",
    )

    @model_validator(mode="after")
    def validate_total_score(self):
        """Verify total_score matches sum of weighted dimension scores."""
        computed = (
            self.skills_match.weighted_score
            + self.experience_relevance.weighted_score
            + self.education_certifications.weighted_score
            + self.projects_portfolio.weighted_score
            + self.communication_quality.weighted_score
        )
        # Allow small floating point tolerance
        if abs(computed - self.total_score) > 2.0:
            # Recompute instead of rejecting — hallucination mitigation
            self.total_score = round(computed, 2)
        return self


class RankedCandidate(BaseModel):
    """Candidate with rank and scoring information for final output."""

    rank: int = Field(..., ge=1, description="Rank position (1 = best)")
    candidate_id: str = Field(...)
    candidate_name: str = Field(default="")
    total_score: float = Field(..., ge=0.0, le=100.0)
    recommendation: Literal["Hire", "No-Hire", "Review"]
    overall_summary: str = Field(default="")
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    semantic_similarity_score: float = Field(default=0.0)
    needs_human_review: bool = Field(default=False)
    override_applied: bool = Field(
        default=False,
        description="True if HR manually overrode the AI score",
    )
    override_reason: Optional[str] = Field(
        None, description="HR's reason for manual override"
    )
