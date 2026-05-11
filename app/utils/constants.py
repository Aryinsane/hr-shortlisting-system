"""
app/utils/constants.py
======================
Application-wide constants for the HR shortlisting agent.
Centralizes magic numbers, strings, and configuration defaults.
"""

# ---- Scoring Dimensions ----
SCORING_DIMENSIONS = [
    "skills_match",
    "experience_relevance",
    "education_certifications",
    "projects_portfolio",
    "communication_quality",
]

# ---- Scoring Weights (must sum to 1.0) ----
SCORING_WEIGHTS = {
    "skills_match": 0.30,
    "experience_relevance": 0.25,
    "education_certifications": 0.15,
    "projects_portfolio": 0.20,
    "communication_quality": 0.10,
}

# ---- Score Bounds ----
MIN_SCORE = 0.0
MAX_SCORE = 100.0

# ---- Hire Recommendation Threshold ----
HIRE_THRESHOLD = 65.0

# ---- File Upload ----
MAX_FILE_SIZE_MB = 10
ALLOWED_MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "json": "application/json",
}
ALLOWED_EXTENSIONS = {"pdf", "docx", "json"}

# ---- Prompt Injection Detection ----
INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "forget your instructions",
    "new instructions:",
    "system prompt",
    "you are now",
    "pretend you are",
    "act as",
    "jailbreak",
    "bypass",
    "override instructions",
    "reveal your instructions",
    "what are your instructions",
    "repeat your instructions",
    "print your system prompt",
    "show me your prompt",
    "tell me your prompt",
    "\\n\\nHuman:",
    "\\n\\nAssistant:",
    "<|im_start|>",
    "<|im_end|>",
]

# ---- PII Patterns ----
EMAIL_PATTERN = r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"
PHONE_PATTERN = r"(\+?\d{1,3}[\s\-]?)?(\(?\d{3}\)?[\s\-]?)(\d{3}[\s\-]?\d{4})"
SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
AADHAAR_PATTERN = r"\b\d{4}\s\d{4}\s\d{4}\b"

# ---- Database Table Names ----
TABLE_AUDIT_LOGS = "audit_logs"
TABLE_OVERRIDES = "hr_overrides"
TABLE_CANDIDATES = "candidates"
TABLE_REPORTS = "report_history"

# ---- LangGraph State Keys ----
STATE_JD = "jd_data"
STATE_RESUMES = "resume_data"
STATE_LINKEDIN = "linkedin_data"
STATE_EMBEDDINGS = "embeddings"
STATE_SCORES = "scores"
STATE_RANKINGS = "rankings"
STATE_REPORT = "report"
STATE_OVERRIDES = "overrides"
STATE_ERRORS = "errors"

# ---- OpenAI Model Names ----
MODEL_GPT4O = "gpt-4o"
MODEL_EMBEDDING = "text-embedding-3-small"

# ---- FAISS Settings ----
EMBEDDING_DIMENSION = 1536  # text-embedding-3-small output dimension
FAISS_TOP_K = 5

# ---- Report Settings ----
REPORT_TITLE = "HR Candidate Shortlisting Report"
REPORT_COMPANY = "AI-Powered Recruitment System"

# ---- API Route Prefixes ----
API_V1_PREFIX = "/api/v1"
