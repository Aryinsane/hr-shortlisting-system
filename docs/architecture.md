# Architecture Documentation

## System Overview

The HR Shortlisting Agent is a production-style AI pipeline built on a clean
layered architecture:

```
[Upload Layer] → [Security Layer] → [Parsing Layer] → [AI Layer] → [Storage Layer] → [Output Layer]
```

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI (Port 8501)               │
│  Upload | Rankings | Scores | Override | Analytics | Logs │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP REST
┌───────────────────────▼─────────────────────────────────┐
│                FastAPI Backend (Port 8000)                │
│  /upload  /scoring  /ranking  /override                   │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│              LangGraph StateGraph Workflow                │
│  10 nodes: JD→Resume→LinkedIn→Embed→FAISS→              │
│           Score→Rank→Report→Override→Audit               │
└──┬────────────────────────────────────────┬─────────────┘
   │                                        │
┌──▼──────────────┐              ┌──────────▼──────────────┐
│  OpenAI GPT-4o  │              │     FAISS Index          │
│  text-emb-3-sm  │              │   (cosine similarity)    │
└─────────────────┘              └─────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                   SQLite Database                        │
│  audit_logs | hr_overrides | candidates | report_history │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Input**: JD text + Resume files (PDF/DOCX) + LinkedIn JSON
2. **Security Gate**: Injection detection + File validation + PII detection
3. **Parsing**: Text extraction → LLM structured extraction → Pydantic validation
4. **Embedding**: OpenAI API → float[1536] vectors → FAISS IndexFlatIP
5. **Scoring**: GPT-4o with strict prompt → DimensionScore × weight → total
6. **Ranking**: Sort descending → apply overrides → assign ranks
7. **Output**: PDF (ReportLab) + JSON export + Streamlit display

## Key Design Decisions

### Why LangGraph?
LangGraph provides explicit state management between pipeline nodes,
making it easy to inspect, debug, and replay any stage. The StateGraph
pattern is far more maintainable than a chain of async callbacks.

### Why FAISS over ChromaDB?
FAISS is a battle-tested C++ library with Python bindings, providing
excellent performance for CPU-based similarity search without the overhead
of a full vector database server.

### Why SQLite?
For an internship-scale deployment, SQLite provides a zero-config,
serverless relational database. All audit logs and HR overrides persist
reliably with ACID guarantees.

### Why Pydantic v2?
Pydantic provides compile-time type safety, automatic validation, and
structured output guarantees — critical for hallucination mitigation when
working with LLM-generated JSON.
