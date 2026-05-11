"""
app/services/audit_service.py
===============================
Service for querying and managing audit logs in SQLite.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.database.models import AuditLog
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AuditService:
    """Provides read access to audit logs for the API and UI."""

    def get_logs(
        self,
        db: Session,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs with optional filters.

        Args:
            db: SQLAlchemy session.
            session_id: Filter by session ID.
            event_type: Filter by event type.
            limit: Maximum records to return.

        Returns:
            List of audit log dicts.
        """
        query = db.query(AuditLog)

        if session_id:
            query = query.filter(AuditLog.session_id == session_id)
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

        return [
            {
                "id": log.id,
                "session_id": log.session_id,
                "event_type": log.event_type,
                "agent_name": log.agent_name,
                "candidate_id": log.candidate_id,
                "input_summary": log.input_summary,
                "output_summary": log.output_summary,
                "status": log.status,
                "duration_ms": log.duration_ms,
                "created_at": str(log.created_at),
            }
            for log in logs
        ]

    def get_sessions(self, db: Session, limit: int = 50) -> List[str]:
        """Get list of unique session IDs."""
        sessions = (
            db.query(AuditLog.session_id)
            .distinct()
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [s[0] for s in sessions]
