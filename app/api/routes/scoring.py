"""
app/api/routes/scoring.py
==========================
API routes for retrieving candidate scores and rankings.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.db import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/results/{session_id}", summary="Get pipeline results")
async def get_results(session_id: str):
    """
    Retrieve full pipeline results for a session.
    Returns ranked candidates, scores, and report metadata.
    """
    from app.api.routes.upload import get_session

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    status = session.get("status", "not_started")
    if status == "running":
        return {"status": "running", "message": "Pipeline is still processing..."}

    result = session.get("pipeline_result")
    if not result:
        return {
            "status": status,
            "errors": session.get("errors", []),
            "message": "No results available yet",
        }

    # Extract ranked candidates for response
    ranked = result.get("ranked_candidates", [])
    report = result.get("report")

    return {
        "session_id": session_id,
        "status": result.get("status", "completed"),
        "total_candidates": len(ranked),
        "ranked_candidates": [
            {
                "rank": r.rank,
                "candidate_id": r.candidate_id,
                "total_score": r.total_score,
                "recommendation": r.recommendation,
                "overall_summary": r.overall_summary,
                "matched_skills": r.matched_skills[:5],
                "missing_skills": r.missing_skills[:5],
                "override_applied": r.override_applied,
            }
            for r in ranked
        ],
        "report_id": report.report_id if report else None,
        "pdf_path": report.pdf_path if report else None,
        "json_path": report.json_path if report else None,
        "errors": result.get("errors", []),
    }


@router.get("/scores/{session_id}", summary="Get detailed candidate scores")
async def get_scores(session_id: str, candidate_id: Optional[str] = None):
    """
    Get detailed dimension-level scores for all or a specific candidate.
    """
    from app.api.routes.upload import get_session

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = session.get("pipeline_result")
    if not result:
        raise HTTPException(status_code=404, detail="No results found for this session")

    scores = result.get("candidate_scores", [])

    if candidate_id:
        scores = [s for s in scores if s.candidate_id == candidate_id]
        if not scores:
            raise HTTPException(status_code=404, detail=f"No score found for candidate {candidate_id}")

    return {
        "session_id": session_id,
        "scores": [s.model_dump() for s in scores],
    }


@router.get("/audit-logs", summary="Get audit logs")
async def get_audit_logs(
    session_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Retrieve audit logs, optionally filtered by session."""
    from app.services.audit_service import AuditService

    service = AuditService()
    logs = service.get_logs(db, session_id=session_id, limit=limit)
    return {"logs": logs, "total": len(logs)}
