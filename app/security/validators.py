"""
app/security/validators.py
===========================
Input validation for API endpoints and LLM outputs.
Provides reusable validation functions across the application.
"""

import re
import json
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.utils.logger import get_logger

logger = get_logger(__name__)


def validate_json_string(json_str: str) -> Tuple[bool, Optional[Dict], str]:
    """
    Validate and parse a JSON string.
    Handles markdown code-block-wrapped JSON from LLMs.

    Args:
        json_str: Raw JSON string (possibly wrapped in ```json...```).

    Returns:
        Tuple of (is_valid, parsed_dict_or_None, error_message).
    """
    if not json_str or not json_str.strip():
        return False, None, "Empty JSON string"

    # Strip markdown code block wrappers
    cleaned = re.sub(r"^```(?:json)?\s*", "", json_str.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        return True, parsed, ""
    except json.JSONDecodeError as e:
        return False, None, f"JSON parse error: {e}"


def validate_score_range(score: Any, field_name: str = "score") -> Tuple[bool, str]:
    """
    Validate that a score value is within the 0–100 range.

    Args:
        score: The score value to check.
        field_name: Name of the field for error messages.

    Returns:
        Tuple of (is_valid, error_message).
    """
    try:
        score_float = float(score)
    except (TypeError, ValueError):
        return False, f"{field_name} must be a number, got: {type(score).__name__}"

    if not (0.0 <= score_float <= 100.0):
        return False, f"{field_name} must be between 0 and 100, got: {score_float}"

    return True, ""


def validate_candidate_scores(scores_dict: Dict) -> Tuple[bool, List[str]]:
    """
    Validate all dimension scores in a candidate score dictionary.

    Args:
        scores_dict: Dictionary containing scoring dimensions.

    Returns:
        Tuple of (all_valid: bool, list_of_errors).
    """
    required_dimensions = [
        "skills_match",
        "experience_relevance",
        "education_certifications",
        "projects_portfolio",
        "communication_quality",
    ]

    errors = []

    for dim in required_dimensions:
        if dim not in scores_dict:
            errors.append(f"Missing scoring dimension: {dim}")
            continue

        dim_data = scores_dict[dim]
        if isinstance(dim_data, dict):
            score = dim_data.get("score", -1)
        else:
            score = dim_data

        ok, err = validate_score_range(score, field_name=dim)
        if not ok:
            errors.append(err)

    # Validate total score
    if "total_score" in scores_dict:
        ok, err = validate_score_range(scores_dict["total_score"], "total_score")
        if not ok:
            errors.append(err)

    return len(errors) == 0, errors


def validate_session_id(session_id: str) -> Tuple[bool, str]:
    """
    Validate session ID format (alphanumeric + hyphens, 8–64 chars).

    Args:
        session_id: Session identifier.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not session_id:
        return False, "Session ID cannot be empty"

    if not re.match(r"^[a-zA-Z0-9\-_]{8,64}$", session_id):
        return False, "Invalid session ID format"

    return True, ""


def sanitize_string_input(text: str, max_length: int = 50000) -> str:
    """
    Basic sanitization for string API inputs.
    Strips leading/trailing whitespace and enforces max length.

    Args:
        text: Input string.
        max_length: Maximum allowed length.

    Returns:
        Sanitized string.
    """
    if not isinstance(text, str):
        text = str(text)

    text = text.strip()
    if len(text) > max_length:
        logger.warning(f"Input truncated from {len(text)} to {max_length} chars")
        text = text[:max_length]

    return text
