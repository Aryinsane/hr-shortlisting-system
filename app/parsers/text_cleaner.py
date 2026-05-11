"""
app/parsers/text_cleaner.py
============================
Text normalization and cleaning utilities for parsed resume/LinkedIn text.
Applied before sending text to LLMs to reduce noise and token cost.
"""

import re
import unicodedata

from app.utils.logger import get_logger

logger = get_logger(__name__)


def normalize_whitespace(text: str) -> str:
    """
    Collapse multiple spaces, tabs, and excessive newlines.

    Args:
        text: Raw input text.

    Returns:
        Cleaned text with normalized whitespace.
    """
    # Replace tabs with spaces
    text = text.replace("\t", " ")
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    # Collapse more than 2 consecutive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def remove_special_characters(text: str, keep_punctuation: bool = True) -> str:
    """
    Remove non-printable and special unicode characters.

    Args:
        text: Input text.
        keep_punctuation: If True, keep standard punctuation.

    Returns:
        Cleaned text.
    """
    # Normalize unicode (e.g., convert fancy quotes to standard)
    text = unicodedata.normalize("NFKD", text)

    if keep_punctuation:
        # Keep alphanumeric, spaces, and common punctuation.
        # Note: inside a character class, ] must be first (after ^) or escaped.
        # Place ] right after [^ so it's treated as a literal ].
        text = re.sub(r"[^\]\w\s.,;:!?\-(){\[}\\/@#%&*+=<>'\"]", " ", text)
    else:
        text = re.sub(r"[^\w\s]", " ", text)

    return text


def remove_urls(text: str) -> str:
    """
    Remove URLs from text (useful for reducing noise in resume parsing).

    Args:
        text: Input text.

    Returns:
        Text with URLs replaced by [URL].
    """
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$\-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        re.IGNORECASE,
    )
    return url_pattern.sub("[URL]", text)


def truncate_text(text: str, max_chars: int = 8000) -> str:
    """
    Truncate text to a maximum character limit.
    Cuts at a sentence boundary where possible.

    Args:
        text: Input text.
        max_chars: Maximum allowed characters.

    Returns:
        Truncated text with ellipsis if needed.
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    # Try to cut at last period or newline
    last_period = max(truncated.rfind("."), truncated.rfind("\n"))
    if last_period > max_chars * 0.8:
        truncated = truncated[: last_period + 1]

    logger.debug(f"Text truncated from {len(text)} to {len(truncated)} chars")
    return truncated + " [...]"


def clean_resume_text(text: str, max_chars: int = 8000) -> str:
    """
    Full pipeline for cleaning extracted resume/LinkedIn text.
    Order matters: normalize → remove specials → truncate.

    Args:
        text: Raw extracted text.
        max_chars: Maximum characters to retain.

    Returns:
        Cleaned, normalized text ready for LLM processing.
    """
    if not text:
        return ""

    text = normalize_whitespace(text)
    text = remove_special_characters(text, keep_punctuation=True)
    text = normalize_whitespace(text)  # re-normalize after special char removal
    text = truncate_text(text, max_chars=max_chars)

    return text


def extract_section(text: str, section_name: str) -> str:
    """
    Attempt to extract a named section from resume text using heuristics.
    e.g., extract_section(text, "EXPERIENCE") returns the experience block.

    Args:
        text: Full resume text.
        section_name: Section header to look for (case-insensitive).

    Returns:
        Section content or empty string if not found.
    """
    # Common section headers and their variations
    pattern = re.compile(
        rf"(?:^|\n)\s*{re.escape(section_name)}s?\s*[\:\-]?\s*\n(.*?)(?=\n\s*[A-Z][A-Z\s]{{3,}}\s*[\:\-]?\s*\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return ""
