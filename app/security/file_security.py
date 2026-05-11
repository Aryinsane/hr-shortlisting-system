"""
app/security/file_security.py
==============================
File upload security validation.
Validates file type, extension, size, and content signatures.
"""

import os
from pathlib import Path
from typing import Tuple, Optional

from app.utils.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Magic bytes (file signatures) for allowed file types
FILE_SIGNATURES = {
    "pdf": [b"%PDF"],
    "docx": [b"PK\x03\x04"],  # DOCX is a ZIP-based format
    "json": [],  # JSON is text; validated by parsing
}

# Maximum allowed file size in bytes
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def validate_file_extension(filename: str) -> Tuple[bool, str]:
    """
    Validate that the file has an allowed extension.

    Args:
        filename: Original filename.

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    ext = Path(filename).suffix.lstrip(".").lower()
    if not ext:
        return False, "File has no extension"

    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f"Extension '{ext}' not allowed. "
            f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return True, ""


def validate_file_size(file_bytes: bytes, filename: str = "") -> Tuple[bool, str]:
    """
    Check that the file doesn't exceed the maximum size limit.

    Args:
        file_bytes: Raw file content.
        filename: Filename for error messages.

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    size = len(file_bytes)
    if size == 0:
        return False, f"File '{filename}' is empty"

    if size > MAX_FILE_SIZE_BYTES:
        size_mb = size / (1024 * 1024)
        return False, (
            f"File '{filename}' is {size_mb:.1f}MB, "
            f"exceeding the {MAX_FILE_SIZE_MB}MB limit"
        )
    return True, ""


def validate_file_signature(file_bytes: bytes, filename: str) -> Tuple[bool, str]:
    """
    Validate the file's magic bytes against its claimed extension.
    Prevents disguised malicious files (e.g., .exe renamed to .pdf).

    Args:
        file_bytes: Raw file content (need at least first 8 bytes).
        filename: Filename with extension.

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    ext = Path(filename).suffix.lstrip(".").lower()

    # JSON files: validate by attempting to parse
    if ext == "json":
        try:
            import json
            json.loads(file_bytes.decode("utf-8", errors="ignore"))
            return True, ""
        except Exception:
            return False, "File claimed to be JSON but could not be parsed"

    # Check magic bytes for binary formats
    signatures = FILE_SIGNATURES.get(ext, [])
    if signatures:
        for sig in signatures:
            if file_bytes[: len(sig)] == sig:
                return True, ""
        return False, (
            f"File '{filename}' does not match expected file signature for .{ext}. "
            "Possible file type spoofing detected."
        )

    return True, ""  # No signature check for other types


def validate_upload(file_bytes: bytes, filename: str) -> Tuple[bool, str]:
    """
    Run all file security validations in sequence.

    Args:
        file_bytes: Raw file content.
        filename: Original filename.

    Returns:
        Tuple of (is_valid: bool, error_message: str)

    All checks must pass for the file to be accepted.
    """
    # 1. Extension check
    ok, err = validate_file_extension(filename)
    if not ok:
        logger.warning(f"File rejected (extension): {filename} — {err}")
        return False, err

    # 2. Size check
    ok, err = validate_file_size(file_bytes, filename)
    if not ok:
        logger.warning(f"File rejected (size): {filename} — {err}")
        return False, err

    # 3. Magic bytes signature check
    ok, err = validate_file_signature(file_bytes, filename)
    if not ok:
        logger.warning(f"File rejected (signature): {filename} — {err}")
        return False, err

    logger.info(
        f"File validation passed: {filename} ({len(file_bytes) / 1024:.1f}KB)"
    )
    return True, ""
