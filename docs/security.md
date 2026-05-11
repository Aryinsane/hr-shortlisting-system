# Security Documentation

## Threat Model & Mitigations

### 1. Prompt Injection

**Threat**: Malicious text in a resume (e.g., "ignore previous instructions")
that manipulates GPT-4o behavior.

**Mitigations**:
- `malicious_prompt_detector.py` — 20+ regex patterns detect injection attempts
- All user inputs scanned before LLM calls
- System prompt instructs GPT-4o to reject instructions from input text
- Structured JSON responses prevent free-form manipulation
- Temperature=0 reduces creative interpretations

**Detected patterns include**:
- "ignore previous instructions"
- "system prompt", "reveal your instructions"
- Delimiter attacks (`<|im_start|>`, `\n\nHuman:`)
- Role reassignment ("you are now", "act as")

### 2. PII Protection

**Threat**: Storing or logging personally identifiable information.

**Mitigations**:
- `pii_masking.py` masks names, emails, phones before storage
- `raw_text` field is never persisted (cleared after parsing)
- Audit logs contain only summaries, never raw resume text
- Regex patterns detect: emails, phone numbers, SSN, Aadhaar

**Masking format**:
- Email: `john.doe@example.com` → `j***@e***.com`
- Phone: `+91-9876543210` → `+91-XXXXXX3210`
- Name: `John Doe` → `J*** D***`

### 3. API Key Security

**Mitigations**:
- API key loaded only from `.env` via `python-dotenv`
- `.env` listed in `.gitignore` — never committed
- `.env.example` provided for setup reference
- No hardcoded keys anywhere in source code

### 4. Hallucination Mitigation

**Threat**: GPT-4o generating false skill claims or fabricated scores.

**Mitigations**:
- Pydantic schemas enforce type and range validation on all LLM outputs
- `model_validator` recomputes total_score from dimensions (not trusted from LLM)
- Score bounds enforced: 0.0 ≤ score ≤ 100.0 for all dimensions
- `confidence_score` field flags low-confidence evaluations
- `needs_human_review=True` auto-set for borderline scores (48–67)
- Temperature=0 for deterministic, factual outputs
- Prompts include "Extract ONLY information explicitly present"

### 5. File Upload Security

**Mitigations**:
- `file_security.py` validates every upload
- Extension whitelist: only `.pdf`, `.docx`, `.json`
- File size limit: configurable (default 10MB)
- Magic bytes check: verifies PDF starts with `%PDF`, DOCX starts with `PK\x03\x04`
- JSON files validated by actual parsing attempt
- Empty files rejected

## Security Checklist

- [x] Prompt injection detection
- [x] PII masking before storage
- [x] API key in environment only
- [x] File type + size + signature validation
- [x] Pydantic output validation
- [x] Score recomputation (not trusted from LLM)
- [x] Human review flags for borderline cases
- [x] Complete audit trail
- [x] CORS configured (restrict in production)
- [x] No SQL injection (SQLAlchemy ORM)
