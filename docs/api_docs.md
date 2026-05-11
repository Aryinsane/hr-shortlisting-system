# API Documentation

Base URL: `http://localhost:8000/api/v1`
Interactive Docs: `http://localhost:8000/docs`

---

## Upload Endpoints

### POST `/upload/jd`
Upload Job Description text.
- **Body** (form): `jd_text: str`
- **Returns**: `{"session_id": "hex32"}`
- **Errors**: 400 if injection detected or text too short

### POST `/upload/resumes/{session_id}`
Upload resume files (PDF/DOCX).
- **Body** (multipart): `files: List[UploadFile]`
- **Returns**: `{"uploaded": [...], "errors": [...], "total_resumes": N}`

### POST `/upload/linkedin/{session_id}`
Upload LinkedIn JSON profiles.
- **Body** (multipart): `files: List[UploadFile]`

### POST `/upload/run/{session_id}`
Trigger the LangGraph pipeline. Runs asynchronously.
- **Returns**: `{"status": "pipeline_started"}`

### GET `/upload/status/{session_id}`
Poll pipeline status.
- **Returns**: `{"status": "running|completed|failed", "errors": [...]}`

---

## Scoring Endpoints

### GET `/scoring/results/{session_id}`
Get ranked candidates and report metadata.

### GET `/scoring/scores/{session_id}?candidate_id=<id>`
Get detailed dimension scores for a candidate.

### GET `/scoring/audit-logs?session_id=<id>&limit=50`
Retrieve audit log entries.

---

## Ranking Endpoints

### GET `/ranking/{session_id}?recommendation=Hire`
Get ranked candidates, optionally filtered by recommendation.

### GET `/ranking/report/pdf/{session_id}`
Download generated PDF report.

### GET `/ranking/report/json/{session_id}`
Download JSON export.

---

## Override Endpoints

### POST `/override/apply`
Apply HR manual score override.
```json
{
  "session_id": "abc123",
  "candidate_id": "c_xyz",
  "original_score": 60.0,
  "overridden_score": 75.0,
  "original_recommendation": "Review",
  "overridden_recommendation": "Hire",
  "override_reason": "Strong culture fit and excellent interview",
  "hr_reviewer": "Jane Smith"
}
```

### GET `/override/list?session_id=<id>`
List all HR overrides.

### DELETE `/override/cancel/{override_id}`
Cancel an override (restores AI score).
