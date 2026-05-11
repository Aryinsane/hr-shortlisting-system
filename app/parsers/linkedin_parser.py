"""
app/parsers/linkedin_parser.py
===============================
Parse LinkedIn profile data exported as JSON.
Handles the standard LinkedIn data export format and custom API formats.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger(__name__)


def parse_linkedin_json(file_path: str) -> Dict[str, Any]:
    """
    Parse a LinkedIn profile JSON export file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        Normalized dictionary with candidate data.

    Raises:
        ValueError: If the file is not valid JSON.
    """
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"LinkedIn JSON file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    return normalize_linkedin_data(raw_data)


def parse_linkedin_json_bytes(file_bytes: bytes, filename: str = "linkedin.json") -> Dict[str, Any]:
    """
    Parse LinkedIn JSON from bytes (for in-memory uploads).

    Args:
        file_bytes: Raw JSON bytes.
        filename: Filename hint for logging.

    Returns:
        Normalized LinkedIn data dictionary.
    """
    try:
        raw_data = json.loads(file_bytes.decode("utf-8"))
        return normalize_linkedin_data(raw_data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filename}: {e}")
        return {}


def normalize_linkedin_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize LinkedIn profile data from various export formats
    into the standard internal format used by the pipeline.

    Handles both the official LinkedIn export format and
    simplified custom formats.

    Args:
        raw: Raw parsed JSON dictionary.

    Returns:
        Normalized dictionary with standardized keys.
    """
    # --- Basic Info ---
    name = (
        raw.get("name", "")
        or f"{raw.get('firstName', '')} {raw.get('lastName', '')}".strip()
    )

    email = raw.get("email", raw.get("emailAddress", ""))
    phone = raw.get("phone", raw.get("phoneNumbers", [{}])[0].get("number", "") if isinstance(raw.get("phoneNumbers"), list) else "")
    location = raw.get("location", raw.get("geoLocationName", ""))
    summary = raw.get("summary", raw.get("headline", ""))
    linkedin_url = raw.get("publicProfileUrl", raw.get("linkedin_url", ""))

    # --- Skills ---
    skills_raw = raw.get("skills", [])
    skills = _extract_skills(skills_raw)

    # --- Work Experience ---
    positions_raw = raw.get("positions", raw.get("experience", []))
    work_experience = _extract_experience(positions_raw)

    # --- Education ---
    education_raw = raw.get("education", [])
    education = _extract_education(education_raw)

    # --- Certifications ---
    certs_raw = raw.get("certifications", raw.get("licenses", []))
    certifications = _extract_certifications(certs_raw)

    # --- Projects ---
    projects_raw = raw.get("projects", [])
    projects = _extract_projects(projects_raw)

    # --- Engagement Metrics ---
    connections = raw.get("connections", raw.get("numConnections", None))
    if isinstance(connections, str):
        # LinkedIn exports connections as "500+" sometimes
        connections = int(connections.replace("+", "").replace(",", "")) if connections.isdigit() else 500

    recommendations_received = raw.get("recommendationsReceived", [])
    recommendations_count = (
        len(recommendations_received)
        if isinstance(recommendations_received, list)
        else raw.get("recommendationsCount", 0)
    )

    # --- Endorsements ---
    endorsements_raw = raw.get("skillEndorsements", {})
    endorsements = _extract_endorsements(skills_raw, endorsements_raw)

    normalized = {
        "name": name,
        "email": email,
        "phone": str(phone) if phone else "",
        "location": location,
        "summary": summary,
        "linkedin_url": linkedin_url,
        "skills": skills,
        "work_experience": work_experience,
        "education": education,
        "certifications": certifications,
        "projects": projects,
        "connections": connections,
        "recommendations_count": recommendations_count,
        "endorsements": endorsements,
    }

    logger.info(
        f"LinkedIn profile normalized: {name} | "
        f"{len(skills)} skills | {len(work_experience)} positions"
    )
    return normalized


def _extract_skills(skills_raw: List[Any]) -> List[str]:
    """Extract skill names from various LinkedIn skill formats."""
    skills = []
    for item in skills_raw:
        if isinstance(item, str):
            skills.append(item.strip())
        elif isinstance(item, dict):
            name = item.get("name", item.get("skill", ""))
            if name:
                skills.append(str(name).strip())
    return [s for s in skills if s]


def _extract_experience(positions_raw: List[Any]) -> List[Dict[str, Any]]:
    """Normalize work experience entries."""
    experience = []
    for pos in positions_raw:
        if not isinstance(pos, dict):
            continue

        # Handle both LinkedIn export and custom formats
        company = pos.get("companyName", pos.get("company", ""))
        title = pos.get("title", pos.get("role", ""))
        description = pos.get("description", pos.get("summary", ""))

        # Duration
        start = pos.get("startDate", pos.get("start_date", {}))
        end = pos.get("endDate", pos.get("end_date", {}))
        is_current = end is None or end == {} or pos.get("isCurrent", False)

        duration_text = _format_duration(start, end, is_current)

        experience.append({
            "company": company,
            "title": title,
            "description": description,
            "duration_text": duration_text,
            "is_current": is_current,
            "technologies": pos.get("technologies", []),
        })
    return experience


def _extract_education(education_raw: List[Any]) -> List[Dict[str, Any]]:
    """Normalize education entries."""
    education = []
    for edu in education_raw:
        if not isinstance(edu, dict):
            continue
        education.append({
            "institution": edu.get("schoolName", edu.get("institution", "")),
            "degree": edu.get("degreeName", edu.get("degree", "")),
            "field_of_study": edu.get("fieldOfStudy", edu.get("field", "")),
            "graduation_year": edu.get("endDate", {}).get("year") if isinstance(edu.get("endDate"), dict) else edu.get("graduation_year"),
        })
    return education


def _extract_certifications(certs_raw: List[Any]) -> List[str]:
    """Extract certification names."""
    certs = []
    for cert in certs_raw:
        if isinstance(cert, str):
            certs.append(cert.strip())
        elif isinstance(cert, dict):
            name = cert.get("name", cert.get("certification", ""))
            if name:
                certs.append(str(name).strip())
    return [c for c in certs if c]


def _extract_projects(projects_raw: List[Any]) -> List[Dict[str, Any]]:
    """Normalize project entries."""
    projects = []
    for proj in projects_raw:
        if isinstance(proj, dict):
            projects.append({
                "name": proj.get("title", proj.get("name", "")),
                "description": proj.get("description", ""),
                "url": proj.get("url", None),
                "technologies": proj.get("technologies", []),
            })
    return projects


def _extract_endorsements(skills_raw: List[Any], endorsements_raw: Any) -> Dict[str, int]:
    """Extract skill endorsement counts."""
    endorsements = {}
    if isinstance(endorsements_raw, dict):
        return {k: int(v) for k, v in endorsements_raw.items() if v}

    # If endorsements are embedded in skills list
    for item in skills_raw:
        if isinstance(item, dict):
            name = item.get("name", "")
            count = item.get("endorsementCount", item.get("endorsements", 0))
            if name and count:
                endorsements[name] = int(count)
    return endorsements


def _format_duration(start: Any, end: Any, is_current: bool) -> str:
    """Format duration from start/end date dicts."""
    if isinstance(start, dict):
        start_str = f"{start.get('month', '')}/{start.get('year', '')}".strip("/")
    else:
        start_str = str(start) if start else ""

    if is_current:
        end_str = "Present"
    elif isinstance(end, dict):
        end_str = f"{end.get('month', '')}/{end.get('year', '')}".strip("/")
    else:
        end_str = str(end) if end else ""

    if start_str or end_str:
        return f"{start_str} - {end_str}".strip(" -")
    return ""
