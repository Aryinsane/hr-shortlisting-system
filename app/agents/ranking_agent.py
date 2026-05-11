"""
app/agents/ranking_agent.py
============================
Ranks candidates by total score and applies HR override adjustments.
Pure Python logic — no LLM calls needed for ranking.
"""

from typing import List, Dict, Optional

from app.schemas.score_schema import CandidateScore, RankedCandidate
from app.utils.logger import get_logger
from app.utils.constants import HIRE_THRESHOLD

logger = get_logger(__name__)


class RankingAgent:
    """
    Ranks candidates based on their CandidateScore total scores.

    Ranking logic:
    1. Sort by total_score descending
    2. Apply HR overrides if present
    3. Assign sequential rank numbers
    4. Flag borderline candidates for review
    """

    def rank(
        self,
        scores: List[CandidateScore],
        overrides: Optional[Dict[str, Dict]] = None,
    ) -> List[RankedCandidate]:
        """
        Rank a list of candidate scores, applying any HR overrides.

        Args:
            scores: List of CandidateScore objects from the scoring agent.
            overrides: Optional dict mapping candidate_id → override dict
                       with keys: new_score, new_recommendation, reason.

        Returns:
            List of RankedCandidate objects sorted by rank (1 = best).
        """
        if not scores:
            logger.warning("No candidates to rank")
            return []

        overrides = overrides or {}

        # Apply overrides to scores
        adjusted_scores = []
        for score in scores:
            override = overrides.get(score.candidate_id)
            if override:
                new_score = float(override.get("new_score", score.total_score))
                new_recommendation = override.get(
                    "new_recommendation", score.recommendation
                )
                # Create adjusted copy
                adjusted = score.model_copy(
                    update={
                        "total_score": new_score,
                        "recommendation": new_recommendation,
                    }
                )
                adjusted_scores.append(
                    (adjusted, True, override.get("reason", "HR Override"))
                )
                logger.info(
                    f"Override applied to {score.candidate_id}: "
                    f"{score.total_score:.1f} → {new_score:.1f} "
                    f"({score.recommendation} → {new_recommendation})"
                )
            else:
                adjusted_scores.append((score, False, None))

        # Sort by total_score descending
        adjusted_scores.sort(key=lambda x: x[0].total_score, reverse=True)

        # Build ranked list
        ranked = []
        for rank, (score, override_applied, override_reason) in enumerate(
            adjusted_scores, start=1
        ):
            ranked.append(
                RankedCandidate(
                    rank=rank,
                    candidate_id=score.candidate_id,
                    candidate_name=score.candidate_name,
                    total_score=score.total_score,
                    recommendation=score.recommendation,
                    overall_summary=score.overall_summary,
                    matched_skills=score.matched_skills,
                    missing_skills=score.missing_skills,
                    semantic_similarity_score=score.semantic_similarity_score,
                    needs_human_review=score.needs_human_review,
                    override_applied=override_applied,
                    override_reason=override_reason,
                )
            )

        hire_count = sum(1 for r in ranked if r.recommendation == "Hire")
        review_count = sum(1 for r in ranked if r.recommendation == "Review")
        no_hire_count = sum(1 for r in ranked if r.recommendation == "No-Hire")

        logger.info(
            f"Ranked {len(ranked)} candidates: "
            f"{hire_count} Hire | {review_count} Review | {no_hire_count} No-Hire"
        )
        return ranked

    def get_shortlist(
        self, ranked: List[RankedCandidate], top_n: Optional[int] = None
    ) -> List[RankedCandidate]:
        """
        Return only candidates recommended for hire.

        Args:
            ranked: Full ranked list.
            top_n: Optional maximum number to return.

        Returns:
            Filtered list of hire-recommended candidates.
        """
        shortlist = [r for r in ranked if r.recommendation == "Hire"]
        if top_n:
            shortlist = shortlist[:top_n]
        return shortlist
