"""
app/services/report_service.py
================================
Generates PDF reports using ReportLab and JSON exports.
Creates professional, structured HR shortlisting reports.
"""

import json
from pathlib import Path
from typing import List
from datetime import datetime

from app.schemas.report_schema import ReportData
from app.schemas.score_schema import CandidateScore
from app.utils.logger import get_logger
from app.utils.constants import REPORT_TITLE, REPORT_COMPANY

logger = get_logger(__name__)


class ReportService:
    """
    Generates PDF and JSON reports from HR screening results.

    PDF format:
    - Title page with job info
    - Executive summary (stats)
    - Ranked candidate table
    - Individual candidate score cards
    - Skill gap analysis
    """

    def generate_pdf(
        self,
        report_data: ReportData,
        scores: List[CandidateScore],
        output_path: str,
    ) -> str:
        """
        Generate a professional PDF report using ReportLab.

        Args:
            report_data: Report metadata and ranked candidates.
            scores: Full score details for each candidate.
            output_path: Path to write the PDF file.

        Returns:
            Absolute path of the generated PDF.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                HRFlowable, PageBreak,
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

        except ImportError:
            logger.error("ReportLab not installed. Run: pip install reportlab")
            return output_path

        # --- Document Setup ---
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()

        # --- Custom Styles ---
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=12,
            textColor=colors.HexColor("#4a4a8a"),
            spaceAfter=4,
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading1"],
            fontSize=14,
            textColor=colors.HexColor("#1a1a2e"),
            borderPad=4,
            spaceAfter=8,
            spaceBefore=16,
        )
        body_style = ParagraphStyle(
            "BodyText",
            parent=styles["Normal"],
            fontSize=9,
            leading=14,
        )
        small_style = ParagraphStyle(
            "SmallText",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#555555"),
        )

        story = []

        # ---- TITLE PAGE ----
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph(REPORT_TITLE, title_style))
        story.append(Paragraph(REPORT_COMPANY, subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#4a4a8a")))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph(f"<b>Position:</b> {report_data.job_title}", body_style))
        story.append(Paragraph(f"<b>Generated:</b> {report_data.generated_at[:19].replace('T', ' ')} UTC", body_style))
        story.append(Paragraph(f"<b>Report ID:</b> {report_data.report_id}", body_style))
        story.append(Spacer(1, 0.3 * inch))

        # ---- EXECUTIVE SUMMARY ----
        story.append(Paragraph("Executive Summary", section_style))

        summary_data = [
            ["Metric", "Value"],
            ["Total Candidates Evaluated", str(report_data.total_candidates_evaluated)],
            ["Recommended (Hire)", str(report_data.shortlisted_count)],
            ["Under Review", str(report_data.review_count)],
            ["Not Recommended (No-Hire)", str(report_data.no_hire_count)],
            ["Average Score", f"{report_data.average_score:.1f}/100"],
            ["Highest Score", f"{report_data.highest_score:.1f}/100"],
            ["Lowest Score", f"{report_data.lowest_score:.1f}/100"],
            ["HR Overrides Applied", str(report_data.overrides_applied)],
        ]

        summary_table = Table(summary_data, colWidths=[3.5 * inch, 3 * inch])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f5f5f5"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3 * inch))

        # ---- RANKED CANDIDATES TABLE ----
        story.append(Paragraph("Candidate Rankings", section_style))

        header = ["Rank", "Candidate ID", "Score", "Recommendation", "Semantic Sim.", "Override"]
        table_data = [header]

        for r in report_data.ranked_candidates:
            rec_color = {
                "Hire": "✅ Hire",
                "No-Hire": "❌ No-Hire",
                "Review": "⚠️ Review",
            }.get(r.get("recommendation", ""), r.get("recommendation", ""))

            table_data.append([
                str(r.get("rank", "")),
                str(r.get("candidate_id", ""))[-12:],
                f"{r.get('total_score', 0):.1f}",
                r.get("recommendation", ""),
                f"{r.get('semantic_similarity_score', 0):.2f}",
                "Yes" if r.get("override_applied") else "No",
            ])

        rank_table = Table(table_data, colWidths=[0.6*inch, 1.8*inch, 0.8*inch, 1.2*inch, 1*inch, 0.8*inch])
        rank_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a4a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f0ff"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(rank_table)
        story.append(PageBreak())

        # ---- INDIVIDUAL SCORE CARDS ----
        story.append(Paragraph("Candidate Score Cards", section_style))

        score_map = {s.candidate_id: s for s in scores}

        for r in report_data.ranked_candidates[:15]:  # Limit to 15 detailed cards
            cid = r.get("candidate_id", "")
            score = score_map.get(cid)
            if not score:
                continue

            story.append(Paragraph(
                f"Rank #{r.get('rank')} | {cid} | Score: {r.get('total_score', 0):.1f}/100 | {r.get('recommendation', '')}",
                section_style
            ))

            # Dimension scores table
            dim_data = [
                ["Dimension", "Score", "Weight", "Weighted", "Justification"],
                [
                    "Skills Match",
                    f"{score.skills_match.score:.0f}",
                    "30%",
                    f"{score.skills_match.weighted_score:.1f}",
                    Paragraph(score.skills_match.justification[:100], small_style),
                ],
                [
                    "Experience",
                    f"{score.experience_relevance.score:.0f}",
                    "25%",
                    f"{score.experience_relevance.weighted_score:.1f}",
                    Paragraph(score.experience_relevance.justification[:100], small_style),
                ],
                [
                    "Education",
                    f"{score.education_certifications.score:.0f}",
                    "15%",
                    f"{score.education_certifications.weighted_score:.1f}",
                    Paragraph(score.education_certifications.justification[:100], small_style),
                ],
                [
                    "Projects",
                    f"{score.projects_portfolio.score:.0f}",
                    "20%",
                    f"{score.projects_portfolio.weighted_score:.1f}",
                    Paragraph(score.projects_portfolio.justification[:100], small_style),
                ],
                [
                    "Communication",
                    f"{score.communication_quality.score:.0f}",
                    "10%",
                    f"{score.communication_quality.weighted_score:.1f}",
                    Paragraph(score.communication_quality.justification[:100], small_style),
                ],
            ]

            dim_table = Table(dim_data, colWidths=[1.2*inch, 0.6*inch, 0.6*inch, 0.8*inch, 3.5*inch])
            dim_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8f8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(dim_table)

            if score.missing_skills:
                story.append(Paragraph(
                    f"<b>Missing Skills:</b> {', '.join(score.missing_skills[:8])}",
                    small_style
                ))
            story.append(Paragraph(score.overall_summary, small_style))
            story.append(Spacer(1, 0.2 * inch))

        # ---- SKILL GAP ANALYSIS ----
        if report_data.skill_gap_analysis:
            story.append(PageBreak())
            story.append(Paragraph("Skill Gap Analysis", section_style))
            story.append(Paragraph(
                "Percentage of candidates possessing each required skill:",
                body_style
            ))
            story.append(Spacer(1, 0.1 * inch))

            gap_data = [["Required Skill", "Candidates with Skill", "Coverage %"]]
            for gap in report_data.skill_gap_analysis:
                gap_data.append([
                    gap.skill,
                    str(gap.candidates_with_skill),
                    f"{gap.percentage:.0f}%",
                ])

            gap_table = Table(gap_data, colWidths=[3 * inch, 2 * inch, 1.5 * inch])
            gap_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(gap_table)

        # --- Build PDF ---
        doc.build(story)
        logger.info(f"PDF report built: {output_path}")
        return output_path

    def generate_json(self, report_data: ReportData, output_path: str) -> str:
        """
        Export report data as a formatted JSON file.

        Args:
            report_data: Complete ReportData object.
            output_path: Path to write the JSON file.

        Returns:
            Output path.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                report_data.model_dump(),
                f,
                indent=2,
                default=str,
            )

        logger.info(f"JSON report written: {output_path}")
        return output_path
