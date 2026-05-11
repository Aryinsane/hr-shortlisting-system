"""
app/api/routes/upload.py
=========================
File upload endpoints for JD, resumes, and LinkedIn profiles.
Includes security validation and pipeline trigger.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.security.file_security import validate_upload
from app.security.malicious_prompt_detector import detect_prompt_injection
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# In-memory session store (use Redis in production)
_sessions: dict = {}


@router.post("/jd", summary="Upload Job Description text")
async def upload_jd(jd_text: str = Form(...)):
    """
    Upload a Job Description text for parsing.

    - Checks for prompt injection in the JD text
    - Returns a session ID for subsequent API calls
    """
    # Security: Check for injection in JD text
    is_malicious, patterns = detect_prompt_injection(jd_text)
    if is_malicious:
        logger.warning(f"JD upload rejected: prompt injection detected. Patterns: {patterns[:2]}")
        raise HTTPException(
            status_code=400,
            detail="SECURITY: Potential prompt injection detected in job description"
        )

    if len(jd_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Job description is too short")

    session_id = uuid.uuid4().hex
    _sessions[session_id] = {
        "jd_text": jd_text,
        "resume_files": [],
        "linkedin_files": [],
    }

    logger.info(f"JD uploaded. Session: {session_id} | {len(jd_text)} chars")
    return {"session_id": session_id, "message": "JD uploaded successfully"}


@router.post("/resumes/{session_id}", summary="Upload resume files")
async def upload_resumes(
    session_id: str,
    files: List[UploadFile] = File(...),
):
    """
    Upload one or more resume files (PDF or DOCX) for a session.

    - Validates file type, size, and magic bytes
    - Associates files with the session
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found. Upload JD first.")

    uploaded = []
    errors = []

    for file in files:
        content = await file.read()
        filename = file.filename or "unknown"

        # Security validation
        is_valid, error_msg = validate_upload(content, filename)
        if not is_valid:
            errors.append({"file": filename, "error": error_msg})
            logger.warning(f"Resume rejected: {filename} — {error_msg}")
            continue

        _sessions[session_id]["resume_files"].append({
            "filename": filename,
            "content": content,
        })
        uploaded.append(filename)
        logger.info(f"Resume uploaded: {filename} ({len(content)} bytes) → Session {session_id}")

    return {
        "session_id": session_id,
        "uploaded": uploaded,
        "errors": errors,
        "total_resumes": len(_sessions[session_id]["resume_files"]),
    }


@router.post("/linkedin/{session_id}", summary="Upload LinkedIn JSON profiles")
async def upload_linkedin(
    session_id: str,
    files: List[UploadFile] = File(...),
):
    """
    Upload LinkedIn profile JSON files for a session.

    - Validates JSON format
    - Associates profiles with the session
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    uploaded = []
    errors = []

    for file in files:
        content = await file.read()
        filename = file.filename or "linkedin.json"

        # Validate file security
        is_valid, error_msg = validate_upload(content, filename)
        if not is_valid:
            errors.append({"file": filename, "error": error_msg})
            continue

        _sessions[session_id]["linkedin_files"].append({
            "filename": filename,
            "content": content,
        })
        uploaded.append(filename)
        logger.info(f"LinkedIn profile uploaded: {filename} → Session {session_id}")

    return {
        "session_id": session_id,
        "uploaded": uploaded,
        "errors": errors,
        "total_linkedin": len(_sessions[session_id]["linkedin_files"]),
    }


@router.post("/run/{session_id}", summary="Run the full screening pipeline")
async def run_pipeline(session_id: str, background_tasks: BackgroundTasks):
    """
    Trigger the complete LangGraph HR pipeline for a session.

    Runs: JD Parsing → Resume Parsing → LinkedIn Parsing →
    Embedding → FAISS → Scoring → Ranking → Report Generation

    Returns immediately with a job acknowledgment.
    The pipeline runs asynchronously in the background.
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]

    if not session.get("jd_text"):
        raise HTTPException(status_code=400, detail="No JD uploaded for this session")

    if not session.get("resume_files"):
        raise HTTPException(status_code=400, detail="No resume files uploaded")

    # Mark as running
    _sessions[session_id]["status"] = "running"

    # Run pipeline in background
    background_tasks.add_task(
        _run_pipeline_background,
        session_id,
        session,
    )

    return {
        "session_id": session_id,
        "status": "pipeline_started",
        "message": "Pipeline is running. Poll /scoring/results/{session_id} for results.",
        "resume_count": len(session["resume_files"]),
        "linkedin_count": len(session.get("linkedin_files", [])),
    }


@router.get("/status/{session_id}", summary="Check pipeline status")
async def get_pipeline_status(session_id: str):
    """Get the current status of a pipeline session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    return {
        "session_id": session_id,
        "status": session.get("status", "not_started"),
        "resume_count": len(session.get("resume_files", [])),
        "linkedin_count": len(session.get("linkedin_files", [])),
        "errors": session.get("errors", []),
    }


async def _run_pipeline_background(session_id: str, session: dict):
    """Background task to execute the LangGraph pipeline."""
    try:
        from app.graph.workflow_graph import run_pipeline

        result = run_pipeline(
            jd_text=session["jd_text"],
            resume_files=session["resume_files"],
            linkedin_files=session.get("linkedin_files", []),
            overrides=session.get("overrides", {}),
        )

        # Store results in session
        _sessions[session_id]["pipeline_result"] = result
        _sessions[session_id]["status"] = result.get("status", "completed")
        _sessions[session_id]["errors"] = result.get("errors", [])

        logger.info(f"Pipeline completed for session {session_id}")

    except Exception as e:
        logger.error(f"Pipeline failed for session {session_id}: {e}")
        _sessions[session_id]["status"] = "failed"
        _sessions[session_id]["errors"] = [str(e)]


def get_session(session_id: str) -> dict:
    """Helper to retrieve session data (used by other routes)."""
    return _sessions.get(session_id, {})
