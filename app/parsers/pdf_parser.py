"""
app/parsers/pdf_parser.py
=========================
PDF text extraction using dual-method approach:
1. PyMuPDF (fitz) — primary, fast and reliable
2. pdfplumber — fallback for complex layouts

Uses both engines and selects the richer output.
"""

import io
from typing import Optional
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger(__name__)


def extract_text_pymupdf(file_path: str) -> str:
    """
    Extract text from a PDF using PyMuPDF (fitz).
    Fast and handles most standard PDFs well.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Extracted text as a string.
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        pages_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Extract text preserving layout where possible
            text = page.get_text("text")
            if text.strip():
                pages_text.append(text.strip())

        doc.close()
        extracted = "\n\n".join(pages_text)
        logger.debug(
            f"PyMuPDF extracted {len(extracted)} chars from {Path(file_path).name}"
        )
        return extracted

    except ImportError:
        logger.error("PyMuPDF (fitz) not installed. Run: pip install PyMuPDF")
        return ""
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed for {file_path}: {e}")
        return ""


def extract_text_pdfplumber(file_path: str) -> str:
    """
    Extract text from a PDF using pdfplumber.
    Better at handling tables and complex layouts.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Extracted text as a string.
    """
    try:
        import pdfplumber

        pages_text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages_text.append(text.strip())

        extracted = "\n\n".join(pages_text)
        logger.debug(
            f"pdfplumber extracted {len(extracted)} chars from {Path(file_path).name}"
        )
        return extracted

    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return ""
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed for {file_path}: {e}")
        return ""


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using the best available method.
    Tries PyMuPDF first, falls back to pdfplumber, then combines both
    and returns whichever extraction is richer (more characters).

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Best extracted text as a string.

    Raises:
        ValueError: If the file doesn't exist or is empty.
    """
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"PDF file not found: {file_path}")

    if path.stat().st_size == 0:
        raise ValueError(f"PDF file is empty: {file_path}")

    # Extract with both engines
    text_pymupdf = extract_text_pymupdf(file_path)
    text_pdfplumber = extract_text_pdfplumber(file_path)

    # Choose the richer extraction
    if len(text_pymupdf) >= len(text_pdfplumber):
        primary, secondary = text_pymupdf, text_pdfplumber
        method = "PyMuPDF"
    else:
        primary, secondary = text_pdfplumber, text_pymupdf
        method = "pdfplumber"

    # If primary is too short, try combining
    if len(primary) < 100 and secondary:
        combined = f"{primary}\n{secondary}".strip()
        logger.info(
            f"Combined both extractors for {path.name}: {len(combined)} chars"
        )
        return combined

    logger.info(
        f"Selected {method} for {path.name}: {len(primary)} chars extracted"
    )
    return primary


def extract_text_from_pdf_bytes(file_bytes: bytes, filename: str = "upload.pdf") -> str:
    """
    Extract text directly from PDF bytes (for API uploads without saving).

    Args:
        file_bytes: Raw PDF file bytes.
        filename: Filename hint for logging.

    Returns:
        Extracted text as a string.
    """
    try:
        import fitz

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                pages_text.append(text.strip())
        doc.close()

        extracted = "\n\n".join(pages_text)
        logger.debug(f"Extracted {len(extracted)} chars from bytes ({filename})")
        return extracted

    except Exception as e:
        logger.error(f"PDF bytes extraction failed for {filename}: {e}")
        return ""
