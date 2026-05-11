"""
app/services/scoring_service.py
================================
Wrapper service around the ScoringAgent for use in API routes.
"""

from typing import List, Dict, Any
from app.schemas.jd_schema import JobDescription
from app.schemas.candidate_schema import CandidateProfile
from app.schemas.score_schema import CandidateScore
from app.agents.scoring_agent import ScoringAgent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScoringService:
    """Service layer wrapper around ScoringAgent."""

    def __init__(self):
        self._agent = ScoringAgent()

    def score_all(
        self,
        candidates: List[CandidateProfile],
        jd: JobDescription,
        similarities: Dict[str, float] = None,
    ) -> List[CandidateScore]:
        """
        Score all candidates against a JD.

        Args:
            candidates: List of candidate profiles.
            jd: Job description.
            similarities: Optional FAISS similarity scores.

        Returns:
            List of CandidateScore objects.
        """
        similarities = similarities or {}
        scores = []

        for candidate in candidates:
            try:
                sim = similarities.get(candidate.candidate_id, 0.0)
                score = self._agent.score(candidate, jd, semantic_similarity=sim)
                scores.append(score)
            except Exception as e:
                logger.error(f"Failed to score {candidate.candidate_id}: {e}")

        return scores
