"""
app/services/ranking_service.py
================================
Wrapper service around RankingAgent for API routes.
"""

from typing import List, Dict, Optional
from app.schemas.score_schema import CandidateScore, RankedCandidate
from app.agents.ranking_agent import RankingAgent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RankingService:
    """Service layer wrapper around RankingAgent."""

    def __init__(self):
        self._agent = RankingAgent()

    def rank(
        self,
        scores: List[CandidateScore],
        overrides: Optional[Dict[str, Dict]] = None,
    ) -> List[RankedCandidate]:
        """Rank candidates with optional overrides."""
        return self._agent.rank(scores, overrides=overrides)
