# HR Resume & LinkedIn Shortlisting System

A smart recruitment assistant that helps HR teams screen resumes and LinkedIn profiles using semantic matching and AI-assisted scoring.

Built with Python, FastAPI, LangChain, FAISS, and Streamlit.

---

## Overview

This project automates parts of the hiring workflow by:

- extracting information from resumes and job descriptions
- comparing candidate profiles with job requirements
- ranking applicants using semantic similarity and weighted scoring
- generating downloadable reports for HR review

The system combines rule-based evaluation with LLM-assisted analysis to improve candidate shortlisting efficiency.

---

## Core Features

- Resume parsing from PDF and DOCX files
- LinkedIn profile JSON parsing
- Semantic similarity matching using embeddings + FAISS
- Candidate scoring based on:
  - skills
  - experience
  - education
  - projects
  - communication quality
- Human override support for manual HR review
- PDF and JSON report generation
- Audit logging using SQLite
- Streamlit dashboard for visualization
- REST APIs using FastAPI

---

## Workflow

```text
Job Description Upload
        ↓
Resume & LinkedIn Parsing
        ↓
Embedding Generation
        ↓
Semantic Matching (FAISS)
        ↓
Candidate Scoring
        ↓
Ranking & Review
        ↓
Report Generation

| Layer           | Technology           |
| --------------- | -------------------- |
| Backend         | Python, FastAPI      |
| AI Frameworks   | LangChain, LangGraph |
| Embeddings      | OpenAI Embeddings    |
| Vector Database | FAISS                |
| Frontend        | Streamlit            |
| Database        | SQLite               |
| Validation      | Pydantic             |
| PDF Reports     | ReportLab            |


| Category      | Weight |
| ------------- | ------ |
| Skills Match  | 30%    |
| Experience    | 25%    |
| Education     | 15%    |
| Projects      | 20%    |
| Communication | 10%    |


Security Measures
-File type and size validation
-Basic prompt injection detection
-Environment variable protection for API keys
-PII masking for sensitive data

Future Improvements
-Async task processing
-Better resume ranking strategies
-Multi-language resume support
-Real-time LinkedIn integration
-Bias and fairness analysis

Note
-This project was developed as a learning-focused prototype to explore:
-LLM workflows
-semantic search
-AI-assisted recruitment systems
-workflow orchestration using LangGraph
```
