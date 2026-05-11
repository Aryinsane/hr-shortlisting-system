"""tests/test_parsers.py — Parser unit tests."""
import pytest
from app.parsers.text_cleaner import clean_resume_text, normalize_whitespace


def test_normalize_whitespace():
    raw = "Hello   World\n\n\n\nTest"
    cleaned = normalize_whitespace(raw)
    assert "   " not in cleaned
    assert "\n\n\n" not in cleaned


def test_clean_resume_text_truncation():
    long_text = "A" * 10000
    result = clean_resume_text(long_text, max_chars=5000)
    assert len(result) <= 5100  # allow for ellipsis


def test_clean_resume_text_empty():
    assert clean_resume_text("") == ""


def test_clean_resume_text_normal():
    text = "Python Developer  \t  with experience in Django\n\n\nAWS"
    result = clean_resume_text(text)
    assert "Python Developer" in result
    assert "\t" not in result


def test_linkedin_parser_normalize():
    from app.parsers.linkedin_parser import normalize_linkedin_data
    raw = {
        "firstName": "John", "lastName": "Doe",
        "email": "john@test.com",
        "skills": [{"name": "Python"}, {"name": "AWS"}],
        "positions": [{"companyName": "Google", "title": "SWE", "description": "Backend dev"}],
        "education": [{"schoolName": "MIT", "degreeName": "B.S.", "fieldOfStudy": "CS"}],
    }
    result = normalize_linkedin_data(raw)
    assert result["name"] == "John Doe"
    assert "Python" in result["skills"]
    assert len(result["work_experience"]) == 1


def test_linkedin_parser_empty():
    from app.parsers.linkedin_parser import normalize_linkedin_data
    result = normalize_linkedin_data({})
    assert result["name"] == ""
    assert result["skills"] == []


def test_pdf_bytes_extraction_invalid():
    from app.parsers.pdf_parser import extract_text_from_pdf_bytes
    result = extract_text_from_pdf_bytes(b"not a pdf", "test.pdf")
    assert isinstance(result, str)  # should not raise, returns ""


def test_docx_bytes_extraction_invalid():
    from app.parsers.docx_parser import extract_text_from_docx_bytes
    result = extract_text_from_docx_bytes(b"not a docx", "test.docx")
    assert isinstance(result, str)
