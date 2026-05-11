"""
app/agents/report_agent.py
===========================
Orchestrates the report generation process.
Uses the report service to create PDF and JSON outputs.
"""

import uuid
from typing import List, Dict, Optional
import statistics

from app.schemas.score_schema import RankedCandidate, CandidateScore
from app.schemas.jd_schema import JobDescription
from app.schemas.report_schema import ReportData, SkillGapSummary
from app.services.report_service import ReportService
from app.utils.logger import get_logger
from app.utils.file_utils import generate_output_path

logger = get_logger(__name__)


class ReportAgent:
    """
    Generates comprehensive HR shortlisting reports.

    Produces:
    1. ReportData schema with analytics
    2. PDF report via ReportLab
    3. JSON export
    """

    def __init__(self):
        self._report_service = ReportService()
        logger.info("ReportAgent initialized")

    def generate(
        self,
        ranked_candidates: List[RankedCandidate],
        scores: List[CandidateScore],
        jd: JobDescription,
        session_id: str,
        output_dir: str = "./data/outputs",
    ) -> ReportData:
        """
        Generate complete report from ranked candidates.

        Args:
            ranked_candidates: Sorted list of RankedCandidate.
            scores: Full CandidateScore list for analytics.
            jd: Job description that was used for evaluation.
            session_id: Pipeline session identifier.
            output_dir: Directory to save output files.

        Returns:
            ReportData with PDF and JSON paths populated.
        """
        report_id = f"report_{uuid.uuid4().hex[:8]}"

        # --- Analytics ---
        total_scores = [r.total_score for r in ranked_candidates]
        avg_score = statistics.mean(total_scores) if total_scores else 0.0
        max_score = max(total_scores) if total_scores else 0.0
        min_score = min(total_scores) if total_scores else 0.0

        shortlisted = [r for r in ranked_candidates if r.recommendation == "Hire"]
        no_hire = [r for r in ranked_candidates if r.recommendation == "No-Hire"]
        review = [r for r in ranked_candidates if r.recommendation == "Review"]
        overrides = [r for r in ranked_candidates if r.override_applied]

        # --- Skill gap analysis ---
        skill_gaps = self._compute_skill_gaps(ranked_candidates, jd)

        # --- Build report data ---
        report_data = ReportData(
            report_id=report_id,
            job_title=jd.title,
            job_summary=jd.summary,
            required_skills=jd.required_skills,
            total_candidates_evaluated=len(ranked_candidates),
            ranked_candidates=[r.model_dump() for r in ranked_candidates],
            shortlisted_count=len(shortlisted),
            no_hire_count=len(no_hire),
            review_count=len(review),
            average_score=round(avg_score, 2),
            highest_score=round(max_score, 2),
            lowest_score=round(min_score, 2),
            skill_gap_analysis=skill_gaps,
            overrides_applied=len(overrides),
        )

        # --- Generate PDF ---
        pdf_path = generate_output_path(output_dir, prefix=f"report_{session_id[:8]}", extension="pdf")
        try:
            self._report_service.generate_pdf(report_data, scores, pdf_path)
            report_data.pdf_path = pdf_path
            logger.info(f"PDF report generated: {pdf_path}")
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")

        # --- Generate JSON ---
        json_path = generate_output_path(output_dir, prefix=f"report_{session_id[:8]}", extension="json")
        try:
            self._report_service.generate_json(report_data, json_path)
            report_data.json_path = json_path
            logger.info(f"JSON report generated: {json_path}")
        except Exception as e:
            logger.error(f"JSON export failed: {e}")

        logger.info(
            f"Report {report_id} complete: "
            f"{len(ranked_candidates)} candidates | "
            f"{len(shortlisted)} shortlisted"
        )
        return report_data

    def _compute_skill_gaps(
        self, ranked: List[RankedCandidate], jd: JobDescription
    ) -> List[SkillGapSummary]:
        """
        Compute aggregate skill gap analysis across all candidates.

        Args:
            ranked: All ranked candidates.
            jd: Job description with required skills.

        Returns:
            List of SkillGapSummary for each required JD skill.
        """
        if not jd.required_skills or not ranked:
            return []

        total = len(ranked)
        skill_summaries = []

        for skill in jd.required_skills[:20]:
            skill_lower = skill.lower()
            count = sum(
                1
                for r in ranked
                if any(skill_lower == m.lower() for m in r.matched_skills)
            )
            pct = round((count / total) * 100, 1) if total > 0 else 0.0
            skill_summaries.append(
                SkillGapSummary(
                    skill=skill,
                    candidates_with_skill=count,
                    percentage=pct,
                )
            )

        # Sort by percentage ascending (biggest gaps first)
        skill_summaries.sort(key=lambda x: x.percentage)
        return skill_summaries
