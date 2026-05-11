"""
app/database/models.py
=======================
SQLAlchemy ORM models for:
- Audit Logs: Every agent action is logged.
- HR Overrides: Manual HR score adjustments.
- Candidate Metadata: Basic candidate info for retrieval.
- Report History: Record of all generated reports.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Text,
    DateTime,
    JSON,
)
from sqlalchemy.sql import func
from app.database.db import Base


class AuditLog(Base):
    """
    Stores a complete audit trail of all pipeline actions.
    Each LangGraph node logs its inputs/outputs here.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=False)
    event_type = Column(
        String(100),
        nullable=False,
        comment="e.g., jd_parsed, resume_scored, override_applied",
    )
    agent_name = Column(String(100), comment="Name of the LangGraph agent/node")
    candidate_id = Column(String(64), index=True, nullable=True)
    input_summary = Column(Text, comment="Sanitized summary of inputs (no raw PII)")
    output_summary = Column(Text, comment="Sanitized summary of outputs")
    status = Column(
        String(20),
        default="success",
        comment="success | failure | warning",
    )
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True, comment="Processing time in milliseconds")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} event={self.event_type} status={self.status}>"


class HROverride(Base):
    """
    Records manual HR score overrides applied to AI-generated scores.
    Enables human-in-the-loop correction and audit transparency.
    """

    __tablename__ = "hr_overrides"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=False)
    candidate_id = Column(String(64), index=True, nullable=False)
    original_score = Column(Float, nullable=False)
    overridden_score = Column(Float, nullable=False)
    original_recommendation = Column(String(20), nullable=False)
    overridden_recommendation = Column(String(20), nullable=False)
    override_reason = Column(Text, nullable=False, comment="HR justification for override")
    hr_reviewer = Column(String(100), default="HR Team")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<HROverride candidate={self.candidate_id} "
            f"{self.original_score:.1f}->{self.overridden_score:.1f}>"
        )


class CandidateRecord(Base):
    """
    Persists candidate metadata for retrieval and reporting.
    Stores masked PII only.
    """

    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=False)
    masked_name = Column(String(200), default="")
    masked_email = Column(String(200), default="")
    source = Column(String(50), comment="resume | linkedin | combined")
    total_score = Column(Float, nullable=True)
    recommendation = Column(String(20), nullable=True)
    rank = Column(Integer, nullable=True)
    skills_json = Column(JSON, comment="List of extracted skills")
    score_details_json = Column(JSON, comment="Full CandidateScore dict")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Candidate id={self.candidate_id} score={self.total_score}>"


class ReportHistory(Base):
    """
    Tracks every generated report for retrieval and audit purposes.
    """

    __tablename__ = "report_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    report_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=False)
    job_title = Column(String(200), nullable=False)
    total_candidates = Column(Integer, default=0)
    shortlisted_count = Column(Integer, default=0)
    pdf_path = Column(String(500), nullable=True)
    json_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Report id={self.report_id} job={self.job_title}>"
