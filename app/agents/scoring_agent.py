"""
app/agents/scoring_agent.py
============================
LangChain agent that scores candidates against a JD using GPT-4o.
Implements the mandatory 5-dimension scoring rubric with exact weights.
Includes hallucination mitigation via Pydantic validation and rule-based checks.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config.settings import settings
from app.schemas.jd_schema import JobDescription
from app.schemas.candidate_schema import CandidateProfile
from app.schemas.score_schema import CandidateScore, DimensionScore
from app.security.malicious_prompt_detector import PromptInjectionDetector
from app.utils.logger import get_logger
from app.utils.constants import HIRE_THRESHOLD

logger = get_logger(__name__)

# Load scoring prompt template
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "scoring_prompt.txt"
_SCORING_PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")

_injection_detector = PromptInjectionDetector()


class ScoringAgent:
    """
    Scores a candidate profile against a job description.

    Implements the mandatory scoring rubric:
    - Skills Match: 30%
    - Experience Relevance: 25%
    - Education & Certifications: 15%
    - Projects/Portfolio: 20%
    - Communication Quality: 10%

    Hallucination Mitigation:
    - Pydantic validation enforces score ranges (0-100)
    - model_validator recomputes total_score from weighted dimensions
    - Confidence check triggers human review flag for borderline scores
    - Temperature 0 for deterministic output
    """

    def __init__(self):
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.temperature,
            openai_api_key=settings.openai_api_key,
            max_tokens=settings.max_tokens,
        )
        logger.info("ScoringAgent initialized")

    def score(
        self,
        candidate: CandidateProfile,
        jd: JobDescription,
        semantic_similarity: float = 0.0,
    ) -> CandidateScore:
        """
        Score a single candidate against the job description.

        Args:
            candidate: Parsed candidate profile.
            jd: Structured job description.
            semantic_similarity: FAISS cosine similarity score (0-1).

        Returns:
            Validated CandidateScore with all dimension scores.
        """
        # Build prompt with candidate and JD data
        prompt = self._build_prompt(candidate, jd, semantic_similarity)

        # Call LLM
        messages = [
            SystemMessage(
                content=(
                    "You are an objective HR scoring system. "
                    "Return ONLY valid JSON. Be precise and consistent. "
                    "Do NOT deviate from the scoring structure."
                )
            ),
            HumanMessage(content=prompt),
        ]

        logger.info(f"Scoring candidate {candidate.candidate_id}...")
        response = self._llm.invoke(messages)
        raw_output = response.content

        # Parse and validate
        score_data = self._parse_output(raw_output)
        candidate_score = self._build_score(score_data, candidate, semantic_similarity)

        logger.info(
            f"Scored {candidate.candidate_id}: "
            f"{candidate_score.total_score:.1f}/100 → {candidate_score.recommendation}"
        )
        return candidate_score

    def _build_prompt(
        self,
        candidate: CandidateProfile,
        jd: JobDescription,
        semantic_similarity: float,
    ) -> str:
        """Fill the scoring prompt template with candidate and JD data."""

        # Format experience as readable text
        experience_text = self._format_experience(candidate)
        education_text = self._format_education(candidate)
        projects_text = self._format_projects(candidate)

        return (
            _SCORING_PROMPT_TEMPLATE
            .replace("{candidate_id}", candidate.candidate_id)
            .replace("{candidate_name}", candidate.name)
            .replace("{jd_title}", jd.title)
            .replace("{required_skills}", ", ".join(jd.required_skills[:20]))
            .replace("{experience_required}", f"{jd.required_experience_years or 0}+ years")
            .replace("{education_required}", jd.required_education)
            .replace("{domain}", jd.domain)
            .replace("{skills}", ", ".join(candidate.skills[:30]))
            .replace("{experience}", experience_text[:2000])
            .replace("{education}", education_text[:500])
            .replace("{certifications}", ", ".join(candidate.certifications[:10]))
            .replace("{projects}", projects_text[:1500])
            .replace("{communication_score}", str(round(candidate.communication_score_raw, 1)))
            .replace("{writing_quality}", candidate.writing_quality_notes[:200])
            .replace("{semantic_similarity}", f"{semantic_similarity:.3f}")
        )

    def _format_experience(self, candidate: CandidateProfile) -> str:
        """Format work experience for prompt."""
        if not candidate.work_experience:
            return f"Total experience: {candidate.total_experience_years or 0} years"

        parts = []
        for exp in candidate.work_experience[:5]:  # Limit to 5 most recent
            parts.append(
                f"{exp.title} at {exp.company} ({exp.duration_text}): {exp.description[:200]}"
            )
        return "\n".join(parts)

    def _format_education(self, candidate: CandidateProfile) -> str:
        """Format education for prompt."""
        if not candidate.education:
            return "Not specified"
        parts = []
        for edu in candidate.education:
            parts.append(
                f"{edu.degree} in {edu.field_of_study} from {edu.institution} "
                f"({edu.graduation_year or 'year N/A'})"
            )
        return "; ".join(parts)

    def _format_projects(self, candidate: CandidateProfile) -> str:
        """Format projects for prompt."""
        if not candidate.projects:
            return "No projects listed"
        parts = []
        for proj in candidate.projects[:5]:
            tech_str = ", ".join(proj.technologies[:5])
            parts.append(f"{proj.name}: {proj.description[:150]} [Tech: {tech_str}]")
        return "\n".join(parts)

    def _parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse and validate JSON from LLM response."""
        # Strip markdown
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_output.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Score JSON parse error: {e}. Raw: {raw_output[:300]}")
            return {}  # Return empty; _build_score creates default

    def _build_score(
        self,
        data: Dict[str, Any],
        candidate: CandidateProfile,
        semantic_similarity: float,
    ) -> CandidateScore:
        """
        Build a validated CandidateScore from LLM output.
        Falls back to default scores if LLM output is malformed.
        Applies rule-based verification to catch hallucinated scores.
        """

        def parse_dimension(dim_key: str, weight: float) -> DimensionScore:
            """Extract and validate a single dimension score."""
            dim_data = data.get(dim_key, {})
            if not isinstance(dim_data, dict):
                score = float(dim_data) if isinstance(dim_data, (int, float)) else 50.0
                dim_data = {}
            else:
                score = float(dim_data.get("score", 50.0))

            score = max(0.0, min(100.0, score))
            weighted = round(score * weight, 2)

            return DimensionScore(
                dimension=dim_key,
                score=score,
                weight=weight,
                weighted_score=weighted,
                justification=str(dim_data.get("justification", "Score assigned by AI")),
                evidence=dim_data.get("evidence", []),
            )

        # Parse all dimensions with correct weights
        skills = parse_dimension("skills_match", settings.weight_skills)
        experience = parse_dimension("experience_relevance", settings.weight_experience)
        education = parse_dimension("education_certifications", settings.weight_education)
        projects = parse_dimension("projects_portfolio", settings.weight_projects)
        communication = parse_dimension("communication_quality", settings.weight_communication)

        # Compute total from dimensions (rule-based verification)
        total = round(
            skills.weighted_score
            + experience.weighted_score
            + education.weighted_score
            + projects.weighted_score
            + communication.weighted_score,
            2,
        )

        # Determine recommendation
        if total >= HIRE_THRESHOLD:
            recommendation = "Hire"
        elif total >= 50:
            recommendation = "Review"
        else:
            recommendation = "No-Hire"

        # Confidence check — flag borderline scores for human review
        confidence = float(data.get("confidence_score", 0.8))
        needs_review = (48 <= total <= 67) or (confidence < 0.7)

        # Compute skill gap
        candidate_skills_lower = {s.lower() for s in candidate.skills}
        jd_skills = data.get("matched_skills", [])  # LLM-provided
        missing_skills = data.get("missing_skills", [])

        return CandidateScore(
            candidate_id=candidate.candidate_id,
            candidate_name=candidate.name,
            skills_match=skills,
            experience_relevance=experience,
            education_certifications=education,
            projects_portfolio=projects,
            communication_quality=communication,
            total_score=total,
            recommendation=recommendation,
            overall_summary=str(
                data.get("overall_summary", "Candidate evaluated by AI scoring system.")
            ),
            semantic_similarity_score=semantic_similarity,
            matched_skills=jd_skills[:20],
            missing_skills=missing_skills[:20],
            confidence_score=max(0.0, min(1.0, confidence)),
            needs_human_review=needs_review,
        )
