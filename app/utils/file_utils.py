"""
app/utils/file_utils.py
=======================
File handling utilities: saving, reading, path management.
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


def ensure_dir(directory: str) -> str:
    """
    Create a directory if it doesn't exist.

    Args:
        directory: Path string to create.

    Returns:
        Absolute path of the created/existing directory.
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def save_upload(
    file_content: bytes,
    filename: str,
    destination_dir: str,
    use_uuid: bool = True,
) -> str:
    """
    Save uploaded file bytes to a destination directory.

    Args:
        file_content: Raw bytes of the uploaded file.
        filename: Original filename (used for extension extraction).
        destination_dir: Directory to save the file in.
        use_uuid: If True, prefix filename with UUID to avoid collisions.

    Returns:
        Absolute path of the saved file.
    """
    ensure_dir(destination_dir)

    ext = Path(filename).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}" if use_uuid else filename
    file_path = Path(destination_dir) / safe_name

    with open(file_path, "wb") as f:
        f.write(file_content)

    logger.info(f"Saved file: {file_path} ({len(file_content)} bytes)")
    return str(file_path.resolve())


def read_text_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    Read a text file and return its content as a string.

    Args:
        file_path: Path to the file.
        encoding: File encoding (default utf-8).

    Returns:
        File content as string.

    Raises:
        FileNotFoundError: If file doesn't exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    return path.read_text(encoding=encoding)


def get_file_extension(filename: str) -> str:
    """
    Extract and return lowercased file extension (without dot).

    Args:
        filename: Original filename.

    Returns:
        Extension string (e.g., 'pdf', 'docx').
    """
    return Path(filename).suffix.lstrip(".").lower()


def delete_file(file_path: str) -> bool:
    """
    Safely delete a file if it exists.

    Args:
        file_path: Path to the file.

    Returns:
        True if deleted, False if not found.
    """
    path = Path(file_path)
    if path.exists():
        path.unlink()
        logger.info(f"Deleted file: {file_path}")
        return True
    return False


def generate_output_path(
    output_dir: str,
    prefix: str = "report",
    extension: str = "pdf",
) -> str:
    """
    Generate a unique output file path.

    Args:
        output_dir: Directory for output files.
        prefix: Filename prefix.
        extension: File extension (without dot).

    Returns:
        Unique file path string.
    """
    ensure_dir(output_dir)
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{extension}"
    return str(Path(output_dir) / filename)
