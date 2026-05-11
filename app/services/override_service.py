"""
app/services/override_service.py
==================================
Service for managing HR manual score overrides.
Persists overrides to SQLite and provides retrieval.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.database.models import HROverride, CandidateRecord
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OverrideService:
    """
    Manages HR manual score overrides.
    Overrides are persisted to SQLite and applied during ranking.
    """

    def apply_override(
        self,
        db: Session,
        session_id: str,
        candidate_id: str,
        original_score: float,
        overridden_score: float,
        original_recommendation: str,
        overridden_recommendation: str,
        override_reason: str,
        hr_reviewer: str = "HR Team",
    ) -> Dict[str, Any]:
        """
        Record an HR override for a candidate.

        Args:
            db: SQLAlchemy session.
            session_id: Pipeline session ID.
            candidate_id: Target candidate ID.
            original_score: AI-generated score.
            overridden_score: HR-adjusted score.
            original_recommendation: AI recommendation.
            overridden_recommendation: HR recommendation.
            override_reason: HR justification text.
            hr_reviewer: Name of the HR reviewer.

        Returns:
            Override record dict.
        """
        # Validate score bounds
        overridden_score = max(0.0, min(100.0, overridden_score))
        valid_recs = {"Hire", "No-Hire", "Review"}
        if overridden_recommendation not in valid_recs:
            overridden_recommendation = original_recommendation

        override = HROverride(
            session_id=session_id,
            candidate_id=candidate_id,
            original_score=original_score,
            overridden_score=overridden_score,
            original_recommendation=original_recommendation,
            overridden_recommendation=overridden_recommendation,
            override_reason=override_reason[:500],
            hr_reviewer=hr_reviewer,
        )
        db.add(override)
        db.commit()
        db.refresh(override)

        logger.info(
            f"Override recorded: {candidate_id} | "
            f"{original_score:.1f}→{overridden_score:.1f} | "
            f"{original_recommendation}→{overridden_recommendation}"
        )

        return {
            "id": override.id,
            "candidate_id": candidate_id,
            "original_score": original_score,
            "overridden_score": overridden_score,
            "original_recommendation": original_recommendation,
            "overridden_recommendation": overridden_recommendation,
            "reason": override_reason,
            "reviewer": hr_reviewer,
        }

    def get_overrides(
        self,
        db: Session,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all HR overrides, optionally filtered by session.

        Args:
            db: SQLAlchemy session.
            session_id: Optional filter.

        Returns:
            List of override dicts.
        """
        query = db.query(HROverride)
        if session_id:
            query = query.filter(HROverride.session_id == session_id)

        overrides = query.order_by(HROverride.created_at.desc()).all()
        return [
            {
                "id": o.id,
                "session_id": o.session_id,
                "candidate_id": o.candidate_id,
                "original_score": o.original_score,
                "overridden_score": o.overridden_score,
                "original_recommendation": o.original_recommendation,
                "overridden_recommendation": o.overridden_recommendation,
                "reason": o.override_reason,
                "reviewer": o.hr_reviewer,
                "created_at": str(o.created_at),
            }
            for o in overrides
        ]

    def get_overrides_dict(self, db: Session, session_id: str) -> Dict[str, Dict]:
        """
        Get overrides as a dict keyed by candidate_id.
        Suitable for passing to the ranking agent.

        Args:
            db: SQLAlchemy session.
            session_id: Pipeline session ID.

        Returns:
            Dict mapping candidate_id → override dict.
        """
        overrides = self.get_overrides(db, session_id=session_id)
        return {
            o["candidate_id"]: {
                "new_score": o["overridden_score"],
                "new_recommendation": o["overridden_recommendation"],
                "reason": o["reason"],
            }
            for o in overrides
        }
