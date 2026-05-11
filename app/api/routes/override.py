"""
app/api/routes/override.py
===========================
API routes for HR manual score overrides.
Supports human-in-the-loop score and recommendation adjustments.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field

from app.database.db import get_db
from app.services.override_service import OverrideService
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
override_service = OverrideService()


class OverrideRequest(BaseModel):
    """Request model for HR override."""

    session_id: str = Field(..., description="Pipeline session ID")
    candidate_id: str = Field(..., description="Target candidate ID")
    original_score: float = Field(..., ge=0, le=100)
    overridden_score: float = Field(..., ge=0, le=100)
    original_recommendation: str = Field(..., pattern="^(Hire|No-Hire|Review)$")
    overridden_recommendation: str = Field(..., pattern="^(Hire|No-Hire|Review)$")
    override_reason: str = Field(..., min_length=10, max_length=500)
    hr_reviewer: str = Field(default="HR Team", max_length=100)


@router.post("/apply", summary="Apply HR override to a candidate score")
async def apply_override(
    request: OverrideRequest,
    db: Session = Depends(get_db),
):
    """
    Apply a manual HR override to a candidate's AI-generated score.

    The override is:
    1. Persisted to SQLite for audit trail
    2. Applied to the ranking on next retrieval

    Security: All overrides are logged with reviewer ID.
    """
    # Validate score makes sense
    if request.overridden_score == request.original_score and \
       request.overridden_recommendation == request.original_recommendation:
        raise HTTPException(
            status_code=400,
            detail="Override must change either score or recommendation"
        )

    result = override_service.apply_override(
        db=db,
        session_id=request.session_id,
        candidate_id=request.candidate_id,
        original_score=request.original_score,
        overridden_score=request.overridden_score,
        original_recommendation=request.original_recommendation,
        overridden_recommendation=request.overridden_recommendation,
        override_reason=request.override_reason,
        hr_reviewer=request.hr_reviewer,
    )

    logger.info(
        f"Override applied via API: {request.candidate_id} | "
        f"{request.original_score}→{request.overridden_score} | "
        f"by {request.hr_reviewer}"
    )

    return {
        "success": True,
        "override": result,
        "message": (
            f"Override recorded. Score changed from {request.original_score:.1f} "
            f"to {request.overridden_score:.1f}. "
            f"Recommendation: {request.original_recommendation} → {request.overridden_recommendation}"
        ),
    }


@router.get("/list", summary="List all HR overrides")
async def list_overrides(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get all HR overrides, optionally filtered by session."""
    overrides = override_service.get_overrides(db, session_id=session_id)
    return {"overrides": overrides, "total": len(overrides)}


@router.delete("/cancel/{override_id}", summary="Cancel an HR override")
async def cancel_override(override_id: int, db: Session = Depends(get_db)):
    """
    Cancel a previously applied HR override.
    The original AI score will be restored.
    """
    from app.database.models import HROverride

    override = db.query(HROverride).filter(HROverride.id == override_id).first()
    if not override:
        raise HTTPException(status_code=404, detail=f"Override {override_id} not found")

    db.delete(override)
    db.commit()

    logger.info(f"Override {override_id} cancelled")
    return {"success": True, "message": f"Override {override_id} cancelled. AI score restored."}
