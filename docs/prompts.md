# Prompt Engineering Documentation

## Philosophy

All prompts follow these principles:
1. **Strict JSON output** — No prose, no markdown (except the wrapper)
2. **Injection resistance** — Explicit rejection of instructions embedded in input
3. **Evidence-based** — LLM must cite specific evidence from the profile
4. **Bounded outputs** — Score ranges specified in the prompt itself
5. **Temperature=0** — Deterministic, factual extractions

---

## JD Parsing Prompt (`jd_prompt.txt`)

**Purpose**: Extract structured JobDescription from raw JD text.

**Key decisions**:
- Safety constraint forces LLM to return error JSON on injection detection
- "Extract ONLY information explicitly present" prevents hallucination
- Required output keys match exactly to Pydantic `JobDescription` schema

**Template variables**: `{jd_text}`

---

## Resume Scoring Prompt (`scoring_prompt.txt`)

**Purpose**: Score a candidate against a JD with the mandatory 5-dimension rubric.

**Key decisions**:
- Weights explicitly stated in prompt (30%, 25%, 15%, 20%, 10%)
- Hire thresholds defined (≥65 Hire, 50-64 Review, <50 No-Hire)
- `needs_human_review` auto-triggered for borderline and low-confidence
- `evidence` array forces LLM to cite specific profile content
- Score bounds (0-100) specified per-dimension

**Template variables**:
`{candidate_id}`, `{candidate_name}`, `{jd_title}`, `{required_skills}`,
`{experience_required}`, `{education_required}`, `{domain}`, `{skills}`,
`{experience}`, `{education}`, `{certifications}`, `{projects}`,
`{communication_score}`, `{writing_quality}`, `{semantic_similarity}`

---

## Score Explanation Prompt (`explanation_prompt.txt`)

**Purpose**: Generate HR-readable evaluation explanations from scored data.

**Key decisions**:
- "Be objective, fair, and professional. Do not use biased language."
- Focus on skills and qualifications only (no demographic inferences)
- `interview_focus_areas` helps HR prepare targeted questions
- Explicitly forbids including personal contact information

**Template variables**: `{score_data}`, `{job_title}`, `{required_skills}`

---

## Resume Parsing Prompt (inline in `resume_parser_agent.py`)

**Purpose**: Extract structured CandidateProfile from raw resume text.

**Key decisions**:
- `communication_score_raw` estimated by LLM from writing quality
- `total_experience_years` estimated from work history durations
- Empty string / empty list defaults prevent null fields
- Instruction to estimate, not fabricate unknown information
