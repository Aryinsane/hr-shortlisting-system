"""
app/api/routes/ranking.py
==========================
API routes for ranking results and report downloads.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{session_id}", summary="Get candidate ranking")
async def get_ranking(session_id: str, recommendation: Optional[str] = None):
    """
    Get the ranked candidate list for a session.
    Optionally filter by recommendation (Hire, No-Hire, Review).
    """
    from app.api.routes.upload import get_session

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = session.get("pipeline_result")
    if not result:
        raise HTTPException(status_code=404, detail="Pipeline results not available")

    ranked = result.get("ranked_candidates", [])

    if recommendation:
        ranked = [r for r in ranked if r.recommendation == recommendation]

    return {
        "session_id": session_id,
        "total": len(ranked),
        "filter": recommendation,
        "candidates": [
            {
                "rank": r.rank,
                "candidate_id": r.candidate_id,
                "candidate_name": r.candidate_name,
                "total_score": r.total_score,
                "recommendation": r.recommendation,
                "needs_human_review": r.needs_human_review,
                "override_applied": r.override_applied,
                "override_reason": r.override_reason,
                "matched_skills": r.matched_skills,
                "missing_skills": r.missing_skills,
                "semantic_similarity": r.semantic_similarity_score,
                "summary": r.overall_summary,
            }
            for r in ranked
        ],
    }


@router.get("/report/pdf/{session_id}", summary="Download PDF report")
async def download_pdf(session_id: str):
    """Download the generated PDF report for a session."""
    from app.api.routes.upload import get_session
    import os

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = session.get("pipeline_result")
    report = result.get("report") if result else None

    if not report or not report.pdf_path:
        raise HTTPException(status_code=404, detail="PDF report not found for this session")

    if not os.path.exists(report.pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    return FileResponse(
        report.pdf_path,
        media_type="application/pdf",
        filename=f"hr_report_{session_id[:8]}.pdf",
    )


@router.get("/report/json/{session_id}", summary="Download JSON report")
async def download_json(session_id: str):
    """Download the generated JSON report for a session."""
    from app.api.routes.upload import get_session
    import json
    from fastapi.responses import JSONResponse
    import os

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = session.get("pipeline_result")
    report = result.get("report") if result else None

    if not report or not report.json_path:
        raise HTTPException(status_code=404, detail="JSON report not found")

    if not os.path.exists(report.json_path):
        raise HTTPException(status_code=404, detail="JSON file not found on disk")

    with open(report.json_path, "r") as f:
        data = json.load(f)

    return JSONResponse(content=data)
