"""
app/agents/linkedin_parser_agent.py
=====================================
Agent that converts normalized LinkedIn JSON data into a CandidateProfile.
Merges LinkedIn data with existing resume profile if available.
"""

import uuid
from typing import Dict, Any, Optional

from app.schemas.candidate_schema import (
    CandidateProfile, WorkExperience, Education, Project
)
from app.parsers.linkedin_parser import normalize_linkedin_data
from app.security.pii_masking import mask_name, mask_email, mask_phone
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LinkedInParserAgent:
    """
    Converts normalized LinkedIn JSON data into a CandidateProfile.
    Can merge with existing resume profile for a combined view.
    """

    def parse(
        self,
        linkedin_data: Dict[str, Any],
        candidate_id: str = None,
        existing_profile: Optional[CandidateProfile] = None,
    ) -> CandidateProfile:
        """
        Parse LinkedIn data into a CandidateProfile.

        Args:
            linkedin_data: Normalized LinkedIn data dictionary.
            candidate_id: Candidate ID (generated if not provided).
            existing_profile: Existing resume profile to merge with.

        Returns:
            CandidateProfile with LinkedIn data (merged if applicable).
        """
        if not candidate_id:
            candidate_id = f"c_{uuid.uuid4().hex[:12]}"

        # Parse work experience
        work_experience = []
        for exp in linkedin_data.get("work_experience", []):
            try:
                work_experience.append(WorkExperience(
                    company=exp.get("company", ""),
                    title=exp.get("title", ""),
                    duration_text=exp.get("duration_text", ""),
                    description=exp.get("description", ""),
                    technologies=exp.get("technologies", []),
                    is_current=exp.get("is_current", False),
                ))
            except Exception as e:
                logger.debug(f"Skipping invalid experience entry: {e}")

        # Parse education
        education = []
        for edu in linkedin_data.get("education", []):
            try:
                education.append(Education(
                    institution=edu.get("institution", ""),
                    degree=edu.get("degree", ""),
                    field_of_study=edu.get("field_of_study", ""),
                    graduation_year=edu.get("graduation_year"),
                ))
            except Exception as e:
                logger.debug(f"Skipping invalid education entry: {e}")

        # Parse projects
        projects = []
        for proj in linkedin_data.get("projects", []):
            try:
                projects.append(Project(
                    name=proj.get("name", ""),
                    description=proj.get("description", ""),
                    technologies=proj.get("technologies", []),
                    url=proj.get("url"),
                ))
            except Exception as e:
                logger.debug(f"Skipping invalid project entry: {e}")

        # Build LinkedIn profile
        linkedin_profile = CandidateProfile(
            candidate_id=candidate_id,
            name=mask_name(linkedin_data.get("name", "")),
            email=mask_email(linkedin_data.get("email", "")),
            phone=mask_phone(str(linkedin_data.get("phone", ""))),
            location=linkedin_data.get("location", ""),
            source="linkedin",
            summary=linkedin_data.get("summary", ""),
            skills=linkedin_data.get("skills", []),
            work_experience=work_experience,
            education=education,
            certifications=linkedin_data.get("certifications", []),
            projects=projects,
            linkedin_url=linkedin_data.get("linkedin_url"),
            connections=linkedin_data.get("connections"),
            recommendations_count=linkedin_data.get("recommendations_count", 0),
            endorsements=linkedin_data.get("endorsements", {}),
            # LinkedIn activity as a proxy for communication quality
            communication_score_raw=self._estimate_communication_score(linkedin_data),
        )

        # If we have an existing resume profile, merge the two
        if existing_profile:
            merged = self._merge_profiles(existing_profile, linkedin_profile)
            logger.info(
                f"Merged LinkedIn with resume for {candidate_id}: "
                f"{len(merged.skills)} total skills"
            )
            return merged

        logger.info(
            f"LinkedIn profile parsed: {candidate_id} | "
            f"{len(linkedin_profile.skills)} skills | "
            f"{len(linkedin_profile.work_experience)} positions"
        )
        return linkedin_profile

    def _estimate_communication_score(self, data: Dict[str, Any]) -> float:
        """
        Estimate communication quality score from LinkedIn profile completeness.

        Factors:
        - Summary present and detailed
        - Recommendations count
        - Skills with endorsements
        - Professional URL

        Returns:
            Estimated score (0-100).
        """
        score = 40.0  # Base score

        summary = data.get("summary", "")
        if summary and len(summary) > 100:
            score += 20.0
        elif summary and len(summary) > 50:
            score += 10.0

        recs = data.get("recommendations_count", 0) or 0
        score += min(20.0, recs * 5.0)  # Up to 20 points for recommendations

        endorsements = data.get("endorsements", {})
        if len(endorsements) > 5:
            score += 10.0
        elif len(endorsements) > 0:
            score += 5.0

        if data.get("linkedin_url"):
            score += 5.0

        connections = data.get("connections", 0) or 0
        if connections > 200:
            score += 5.0

        return min(100.0, score)

    def _merge_profiles(
        self,
        resume_profile: CandidateProfile,
        linkedin_profile: CandidateProfile,
    ) -> CandidateProfile:
        """
        Merge resume and LinkedIn profiles into a single combined profile.
        Resume data takes precedence for structured fields;
        LinkedIn adds additional skills, experience, and metrics.

        Args:
            resume_profile: Profile parsed from resume.
            linkedin_profile: Profile parsed from LinkedIn.

        Returns:
            Merged CandidateProfile with source='combined'.
        """
        # Merge skills (deduplicate)
        all_skills = list(resume_profile.skills)
        for skill in linkedin_profile.skills:
            if skill.lower() not in [s.lower() for s in all_skills]:
                all_skills.append(skill)

        # Merge certifications
        all_certs = list(resume_profile.certifications)
        for cert in linkedin_profile.certifications:
            if cert not in all_certs:
                all_certs.append(cert)

        # Merge projects
        all_projects = list(resume_profile.projects)
        resume_project_names = {p.name.lower() for p in resume_profile.projects}
        for proj in linkedin_profile.projects:
            if proj.name.lower() not in resume_project_names:
                all_projects.append(proj)

        # Use better communication score
        comm_score = max(
            resume_profile.communication_score_raw,
            linkedin_profile.communication_score_raw,
        )

        merged = resume_profile.model_copy(update={
            "source": "combined",
            "skills": all_skills,
            "certifications": all_certs,
            "projects": all_projects,
            "linkedin_url": linkedin_profile.linkedin_url,
            "connections": linkedin_profile.connections,
            "recommendations_count": linkedin_profile.recommendations_count,
            "endorsements": linkedin_profile.endorsements,
            "communication_score_raw": comm_score,
        })

        # Use LinkedIn experience if resume has none
        if not resume_profile.work_experience and linkedin_profile.work_experience:
            merged = merged.model_copy(update={
                "work_experience": linkedin_profile.work_experience,
            })

        return merged
