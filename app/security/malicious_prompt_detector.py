"""
app/security/malicious_prompt_detector.py
==========================================
Detect and block prompt injection attempts in user-supplied text.
Protects the LLM pipeline from jailbreaks, extraction attempts,
and adversarial inputs embedded in resumes or job descriptions.
"""

import re
from typing import Tuple, List
from app.utils.constants import INJECTION_PATTERNS
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PromptInjectionDetector:
    """
    Detects malicious prompt injection patterns in text inputs.

    Checks for:
    - Classic injection phrases ("ignore previous instructions")
    - System prompt extraction attempts
    - Jailbreak patterns
    - Delimiter attacks (<|im_start|> etc.)
    - Role reassignment attempts
    """

    def __init__(self, custom_patterns: List[str] = None):
        """
        Initialize the detector with default and optional custom patterns.

        Args:
            custom_patterns: Additional regex patterns to detect.
        """
        self._patterns = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

        if custom_patterns:
            self._patterns.extend(
                [re.compile(p, re.IGNORECASE) for p in custom_patterns]
            )

        logger.debug(
            f"PromptInjectionDetector initialized with {len(self._patterns)} patterns"
        )

    def check(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check text for injection patterns.

        Args:
            text: Text to scan.

        Returns:
            Tuple of (is_malicious: bool, matched_patterns: List[str])
        """
        if not text:
            return False, []

        matched = []
        for pattern in self._patterns:
            if pattern.search(text):
                matched.append(pattern.pattern)

        is_malicious = len(matched) > 0

        if is_malicious:
            logger.warning(
                f"Prompt injection detected! Matched patterns: {matched[:3]}"
                f" (showing first 3 of {len(matched)})"
            )

        return is_malicious, matched

    def sanitize(self, text: str) -> str:
        """
        Sanitize text by removing detected injection patterns.
        Use this ONLY if you want to continue processing despite detections.
        Prefer blocking (rejecting) inputs when possible.

        Args:
            text: Input text.

        Returns:
            Sanitized text with injection patterns removed.
        """
        sanitized = text
        for pattern in self._patterns:
            sanitized = pattern.sub("[REMOVED]", sanitized)
        return sanitized

    def is_safe(self, text: str) -> bool:
        """
        Convenience method to check if text is safe.

        Args:
            text: Input text.

        Returns:
            True if no injection detected, False otherwise.
        """
        is_malicious, _ = self.check(text)
        return not is_malicious


def detect_prompt_injection(text: str) -> Tuple[bool, List[str]]:
    """
    Module-level convenience function for injection detection.

    Args:
        text: Text to check.

    Returns:
        Tuple of (is_malicious, matched_patterns).
    """
    detector = PromptInjectionDetector()
    return detector.check(text)


def validate_llm_output(output: str, expected_keys: List[str] = None) -> Tuple[bool, str]:
    """
    Validate LLM JSON output for basic structural integrity.
    Hallucination mitigation: ensure output has required fields.

    Args:
        output: Raw LLM output string.
        expected_keys: List of required JSON keys.

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    import json

    if not output or not output.strip():
        return False, "LLM returned empty output"

    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", output)
    if json_match:
        output = json_match.group(1)

    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"

    if expected_keys:
        missing = [k for k in expected_keys if k not in parsed]
        if missing:
            return False, f"Missing required keys: {missing}"

    return True, ""
