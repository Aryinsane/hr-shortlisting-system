"""
app/graph/workflow_graph.py
============================
LangGraph StateGraph workflow for the HR shortlisting pipeline.

Workflow:
START → JD Parser → Resume Parser → LinkedIn Parser →
Embedding Generation → FAISS Matching → Scoring →
Ranking → Report Generation → Human Override →
Audit Logging → END

Each node is a pure function that receives and returns the pipeline state.
The state is a TypedDict shared across all nodes.
"""

import time
import uuid
from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

from langgraph.graph import StateGraph, END

from app.schemas.jd_schema import JobDescription
from app.schemas.candidate_schema import CandidateProfile
from app.schemas.score_schema import CandidateScore, RankedCandidate
from app.schemas.report_schema import ReportData
from app.utils.logger import get_logger
from app.utils.constants import STATE_ERRORS

logger = get_logger(__name__)


# ============================================================
# PIPELINE STATE DEFINITION
# ============================================================

class PipelineState(TypedDict):
    """
    Shared state dict passed between all LangGraph nodes.
    Each node reads relevant fields and writes its outputs.
    """

    # --- Session ---
    session_id: str
    started_at: float

    # --- Inputs ---
    jd_text: str
    resume_files: List[Dict[str, Any]]     # [{"filename": str, "content": bytes}]
    linkedin_files: List[Dict[str, Any]]   # [{"filename": str, "content": bytes}]

    # --- Parsed Data ---
    jd_data: Optional[JobDescription]
    candidate_profiles: List[CandidateProfile]
    jd_embedding: Optional[List[float]]
    candidate_similarities: Dict[str, float]  # candidate_id → similarity

    # --- Scores & Rankings ---
    candidate_scores: List[CandidateScore]
    ranked_candidates: List[RankedCandidate]

    # --- Report ---
    report: Optional[ReportData]

    # --- Human Override ---
    overrides: Dict[str, Dict]  # candidate_id → {new_score, recommendation, reason}

    # --- Errors & Flags ---
    errors: List[str]
    status: str  # running | completed | failed


# ============================================================
# NODE FUNCTIONS
# ============================================================

def node_parse_jd(state: PipelineState) -> PipelineState:
    """
    Node 1: Parse Job Description text into structured JobDescription.
    Uses JDParserAgent with injection detection.
    """
    logger.info("=== NODE: JD Parser ===")
    t0 = time.time()

    try:
        from app.agents.jd_parser_agent import JDParserAgent
        agent = JDParserAgent()
        jd_data = agent.parse(state["jd_text"])
        state["jd_data"] = jd_data

        _log_audit(
            state,
            "jd_parsed",
            "JDParserAgent",
            output_summary=f"Title: {jd_data.title} | Skills: {len(jd_data.required_skills)}",
            duration_ms=(time.time() - t0) * 1000,
        )
        logger.info(f"JD parsed: '{jd_data.title}'")

    except Exception as e:
        error_msg = f"JD parsing failed: {str(e)}"
        state["errors"].append(error_msg)
        state["status"] = "failed"
        logger.error(error_msg)

    return state


def node_parse_resumes(state: PipelineState) -> PipelineState:
    """
    Node 2: Parse all uploaded resume files (PDF/DOCX).
    Runs per-file parsing and collects CandidateProfile objects.
    """
    logger.info("=== NODE: Resume Parser ===")
    t0 = time.time()

    if state.get("status") == "failed":
        return state

    try:
        from app.agents.resume_parser_agent import ResumeParserAgent
        from app.parsers.pdf_parser import extract_text_from_pdf_bytes
        from app.parsers.docx_parser import extract_text_from_docx_bytes
        from app.utils.file_utils import get_file_extension

        agent = ResumeParserAgent()
        profiles = list(state.get("candidate_profiles", []))

        for resume_file in state.get("resume_files", []):
            filename = resume_file["filename"]
            content = resume_file["content"]
            ext = get_file_extension(filename)

            try:
                # Extract text based on file type
                if ext == "pdf":
                    text = extract_text_from_pdf_bytes(content, filename)
                elif ext == "docx":
                    text = extract_text_from_docx_bytes(content, filename)
                else:
                    logger.warning(f"Unsupported resume format: {filename}")
                    continue

                if not text.strip():
                    logger.warning(f"No text extracted from {filename}")
                    state["errors"].append(f"Could not extract text from {filename}")
                    continue

                # Parse into CandidateProfile
                candidate_id = f"c_{uuid.uuid4().hex[:12]}"
                profile = agent.parse(text, candidate_id=candidate_id)
                profiles.append(profile)

                logger.info(f"Resume parsed: {filename} → {candidate_id}")

            except Exception as e:
                error = f"Failed to parse {filename}: {str(e)}"
                state["errors"].append(error)
                logger.error(error)

        state["candidate_profiles"] = profiles

        _log_audit(
            state,
            "resumes_parsed",
            "ResumeParserAgent",
            output_summary=f"Parsed {len(profiles)} resumes",
            duration_ms=(time.time() - t0) * 1000,
        )
        logger.info(f"Total candidates from resumes: {len(profiles)}")

    except Exception as e:
        error_msg = f"Resume parsing node failed: {str(e)}"
        state["errors"].append(error_msg)
        logger.error(error_msg)

    return state


def node_parse_linkedin(state: PipelineState) -> PipelineState:
    """
    Node 3: Parse LinkedIn JSON files and merge with existing resume profiles.
    Matches LinkedIn profiles to resume profiles by candidate_id index order.
    """
    logger.info("=== NODE: LinkedIn Parser ===")
    t0 = time.time()

    if state.get("status") == "failed":
        return state

    linkedin_files = state.get("linkedin_files", [])
    if not linkedin_files:
        logger.info("No LinkedIn files provided, skipping")
        return state

    try:
        from app.agents.linkedin_parser_agent import LinkedInParserAgent
        from app.parsers.linkedin_parser import parse_linkedin_json_bytes

        agent = LinkedInParserAgent()
        profiles = list(state.get("candidate_profiles", []))

        for i, li_file in enumerate(linkedin_files):
            filename = li_file["filename"]
            content = li_file["content"]

            try:
                li_data = parse_linkedin_json_bytes(content, filename)
                if not li_data:
                    logger.warning(f"Empty LinkedIn data: {filename}")
                    continue

                # Match to existing profile by index, or create new
                existing = profiles[i] if i < len(profiles) else None
                candidate_id = existing.candidate_id if existing else f"c_{uuid.uuid4().hex[:12]}"

                profile = agent.parse(li_data, candidate_id=candidate_id, existing_profile=existing)

                if existing and i < len(profiles):
                    profiles[i] = profile  # Replace with merged
                else:
                    profiles.append(profile)

                logger.info(f"LinkedIn parsed: {filename} → {candidate_id}")

            except Exception as e:
                error = f"Failed to parse LinkedIn file {filename}: {str(e)}"
                state["errors"].append(error)
                logger.error(error)

        state["candidate_profiles"] = profiles
        _log_audit(
            state,
            "linkedin_parsed",
            "LinkedInParserAgent",
            output_summary=f"Processed {len(linkedin_files)} LinkedIn files",
            duration_ms=(time.time() - t0) * 1000,
        )

    except Exception as e:
        error_msg = f"LinkedIn parsing node failed: {str(e)}"
        state["errors"].append(error_msg)
        logger.error(error_msg)

    return state


def node_generate_embeddings(state: PipelineState) -> PipelineState:
    """
    Node 4: Generate OpenAI embeddings for JD and all candidate profiles.
    Builds the FAISS index for semantic search.
    """
    logger.info("=== NODE: Embedding Generation ===")
    t0 = time.time()

    if state.get("status") == "failed":
        return state

    try:
        from app.embeddings.embedding_service import EmbeddingService
        service = EmbeddingService()
        service.reset()  # Fresh index for this session

        # Embed JD
        jd_data = state.get("jd_data")
        if jd_data:
            jd_text = _jd_to_text(jd_data)
            jd_embedding = service.embed_text(jd_text)
            state["jd_embedding"] = jd_embedding
            logger.info("JD embedding generated")

        # Embed candidates
        profiles = state.get("candidate_profiles", [])
        for profile in profiles:
            candidate_text = _profile_to_text(profile)
            try:
                service.add_candidate(profile.candidate_id, candidate_text)
            except Exception as e:
                logger.warning(f"Failed to embed candidate {profile.candidate_id}: {e}")

        # Save index for persistence
        service.save_index()

        # Store service in state for similarity computation
        state["_embedding_service"] = service  # type: ignore (not in TypedDict)

        _log_audit(
            state,
            "embeddings_generated",
            "EmbeddingService",
            output_summary=f"JD + {len(profiles)} candidate embeddings",
            duration_ms=(time.time() - t0) * 1000,
        )
        logger.info(f"Embeddings generated for {len(profiles)} candidates")

    except Exception as e:
        error_msg = f"Embedding generation failed: {str(e)}"
        state["errors"].append(error_msg)
        logger.error(error_msg)

    return state


def node_faiss_matching(state: PipelineState) -> PipelineState:
    """
    Node 5: FAISS semantic matching — compute similarity between JD and each candidate.
    Stores similarity scores for use in the scoring agent.
    """
    logger.info("=== NODE: FAISS Semantic Matching ===")
    t0 = time.time()

    if state.get("status") == "failed":
        return state

    try:
        service = state.get("_embedding_service")  # type: ignore
        if not service:
            logger.warning("No embedding service in state, re-initializing")
            from app.embeddings.embedding_service import EmbeddingService
            service = EmbeddingService()

        jd_embedding = state.get("jd_embedding", [])
        profiles = state.get("candidate_profiles", [])
        similarities: Dict[str, float] = {}

        for profile in profiles:
            if jd_embedding:
                sim = service.get_candidate_similarity_to_jd(
                    profile.candidate_id, jd_embedding
                )
            else:
                sim = 0.0
            similarities[profile.candidate_id] = sim
            logger.debug(f"{profile.candidate_id}: similarity={sim:.3f}")

        state["candidate_similarities"] = similarities

        _log_audit(
            state,
            "faiss_matching",
            "FAISSService",
            output_summary=f"Computed similarities for {len(similarities)} candidates",
            duration_ms=(time.time() - t0) * 1000,
        )
        logger.info(f"FAISS matching complete: {len(similarities)} candidates")

    except Exception as e:
        error_msg = f"FAISS matching failed: {str(e)}"
        state["errors"].append(error_msg)
        logger.error(error_msg)
        state["candidate_similarities"] = {}

    return state


def node_score_candidates(state: PipelineState) -> PipelineState:
    """
    Node 6: Score each candidate using GPT-4o with the mandatory scoring rubric.
    """
    logger.info("=== NODE: Candidate Scoring ===")
    t0 = time.time()

    if state.get("status") == "failed":
        return state

    profiles = state.get("candidate_profiles", [])
    jd_data = state.get("jd_data")
    similarities = state.get("candidate_similarities", {})

    if not profiles or not jd_data:
        state["errors"].append("No profiles or JD data available for scoring")
        return state

    try:
        from app.agents.scoring_agent import ScoringAgent
        agent = ScoringAgent()
        scores = []

        for profile in profiles:
            try:
                sim = similarities.get(profile.candidate_id, 0.0)
                score = agent.score(profile, jd_data, semantic_similarity=sim)
                scores.append(score)
                logger.info(
                    f"Scored {profile.candidate_id}: {score.total_score:.1f}/100 → {score.recommendation}"
                )
            except Exception as e:
                logger.error(f"Failed to score {profile.candidate_id}: {e}")
                state["errors"].append(f"Scoring failed for {profile.candidate_id}: {e}")

        state["candidate_scores"] = scores

        _log_audit(
            state,
            "candidates_scored",
            "ScoringAgent",
            output_summary=f"Scored {len(scores)} candidates",
            duration_ms=(time.time() - t0) * 1000,
        )
        logger.info(f"Scoring complete: {len(scores)} candidates scored")

    except Exception as e:
        error_msg = f"Scoring node failed: {str(e)}"
        state["errors"].append(error_msg)
        logger.error(error_msg)

    return state


def node_rank_candidates(state: PipelineState) -> PipelineState:
    """
    Node 7: Rank candidates by score, applying any HR overrides.
    """
    logger.info("=== NODE: Candidate Ranking ===")
    t0 = time.time()

    if state.get("status") == "failed":
        return state

    try:
        from app.agents.ranking_agent import RankingAgent
        agent = RankingAgent()

        scores = state.get("candidate_scores", [])
        overrides = state.get("overrides", {})

        ranked = agent.rank(scores, overrides=overrides)
        state["ranked_candidates"] = ranked

        _log_audit(
            state,
            "candidates_ranked",
            "RankingAgent",
            output_summary=f"Ranked {len(ranked)} candidates",
            duration_ms=(time.time() - t0) * 1000,
        )
        logger.info(f"Ranking complete: {len(ranked)} candidates ranked")

    except Exception as e:
        error_msg = f"Ranking node failed: {str(e)}"
        state["errors"].append(error_msg)
        logger.error(error_msg)

    return state


def node_generate_report(state: PipelineState) -> PipelineState:
    """
    Node 8: Generate PDF and JSON reports from ranked candidates.
    """
    logger.info("=== NODE: Report Generation ===")
    t0 = time.time()

    if state.get("status") == "failed":
        return state

    try:
        from app.agents.report_agent import ReportAgent
        from app.config.settings import settings

        agent = ReportAgent()
        ranked = state.get("ranked_candidates", [])
        scores = state.get("candidate_scores", [])
        jd_data = state.get("jd_data")

        if not ranked or not jd_data:
            logger.warning("No ranked candidates or JD data for report")
            return state

        report = agent.generate(
            ranked_candidates=ranked,
            scores=scores,
            jd=jd_data,
            session_id=state["session_id"],
            output_dir=settings.output_dir,
        )
        state["report"] = report

        _log_audit(
            state,
            "report_generated",
            "ReportAgent",
            output_summary=f"Report {report.report_id}: {report.shortlisted_count} shortlisted",
            duration_ms=(time.time() - t0) * 1000,
        )

        # Persist report to DB
        _save_report_to_db(state, report)

    except Exception as e:
        error_msg = f"Report generation failed: {str(e)}"
        state["errors"].append(error_msg)
        logger.error(error_msg)

    return state


def node_human_override(state: PipelineState) -> PipelineState:
    """
    Node 9: Human-in-the-loop override checkpoint.
    In automated mode, this passes through. Overrides are applied
    by the ranking node via the 'overrides' state key.
    This node logs any overrides that were applied.
    """
    logger.info("=== NODE: Human Override Checkpoint ===")

    overrides = state.get("overrides", {})
    if overrides:
        logger.info(f"Human overrides applied: {len(overrides)} candidates modified")
        for cid, override in overrides.items():
            logger.info(
                f"Override: {cid} → score={override.get('new_score')}, "
                f"rec={override.get('new_recommendation')}, "
                f"reason={override.get('reason', 'N/A')}"
            )
        _log_audit(
            state,
            "human_override",
            "HumanOverride",
            output_summary=f"{len(overrides)} overrides applied",
        )
    else:
        logger.info("No human overrides applied")

    return state


def node_audit_logging(state: PipelineState) -> PipelineState:
    """
    Node 10: Final audit log entry marking pipeline completion.
    """
    logger.info("=== NODE: Audit Logging ===")

    elapsed = time.time() - state.get("started_at", time.time())
    errors = state.get("errors", [])
    ranked = state.get("ranked_candidates", [])

    state["status"] = "completed" if not state.get("status") == "failed" else "failed"

    _log_audit(
        state,
        "pipeline_completed",
        "PipelineOrchestrator",
        output_summary=(
            f"Session {state['session_id']} complete in {elapsed:.1f}s | "
            f"{len(ranked)} candidates | {len(errors)} errors"
        ),
        status="success" if state["status"] == "completed" else "failure",
    )

    logger.info(
        f"Pipeline complete: {state['status']} | "
        f"{len(ranked)} candidates | {elapsed:.1f}s | {len(errors)} errors"
    )
    return state


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _jd_to_text(jd: JobDescription) -> str:
    """Convert JD to text for embedding."""
    parts = [
        f"Job Title: {jd.title}",
        f"Domain: {jd.domain}",
        f"Summary: {jd.summary}",
        f"Required Skills: {', '.join(jd.required_skills)}",
        f"Preferred Skills: {', '.join(jd.preferred_skills)}",
        f"Experience: {jd.experience_description}",
        f"Education: {jd.required_education}",
        f"Responsibilities: {'; '.join(jd.responsibilities[:5])}",
    ]
    return "\n".join(parts)


def _profile_to_text(profile: CandidateProfile) -> str:
    """Convert candidate profile to text for embedding."""
    parts = [
        f"Skills: {', '.join(profile.skills[:30])}",
        f"Summary: {profile.summary}",
        f"Experience years: {profile.total_experience_years or 0}",
        f"Certifications: {', '.join(profile.certifications[:10])}",
    ]

    for exp in profile.work_experience[:3]:
        parts.append(f"Role: {exp.title} at {exp.company}: {exp.description[:200]}")

    for proj in profile.projects[:3]:
        parts.append(f"Project: {proj.name}: {proj.description[:150]}")

    return "\n".join(parts)


def _log_audit(
    state: PipelineState,
    event_type: str,
    agent_name: str,
    input_summary: str = "",
    output_summary: str = "",
    status: str = "success",
    duration_ms: float = 0.0,
    candidate_id: Optional[str] = None,
):
    """Write an audit log entry to SQLite."""
    try:
        from app.database.db import SessionLocal
        from app.database.models import AuditLog

        db = SessionLocal()
        log_entry = AuditLog(
            session_id=state["session_id"],
            event_type=event_type,
            agent_name=agent_name,
            candidate_id=candidate_id,
            input_summary=input_summary[:500],
            output_summary=output_summary[:500],
            status=status,
            duration_ms=duration_ms,
        )
        db.add(log_entry)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")


def _save_report_to_db(state: PipelineState, report: ReportData):
    """Persist report metadata to SQLite."""
    try:
        from app.database.db import SessionLocal
        from app.database.models import ReportHistory

        db = SessionLocal()
        record = ReportHistory(
            report_id=report.report_id,
            session_id=state["session_id"],
            job_title=report.job_title,
            total_candidates=report.total_candidates_evaluated,
            shortlisted_count=report.shortlisted_count,
            pdf_path=report.pdf_path,
            json_path=report.json_path,
        )
        db.add(record)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Report DB save failed: {e}")


# ============================================================
# GRAPH CONSTRUCTION
# ============================================================

def build_workflow() -> StateGraph:
    """
    Build and compile the LangGraph StateGraph for the HR pipeline.

    Returns:
        Compiled LangGraph runnable (CompiledGraph).
    """
    workflow = StateGraph(PipelineState)

    # --- Add nodes ---
    workflow.add_node("parse_jd", node_parse_jd)
    workflow.add_node("parse_resumes", node_parse_resumes)
    workflow.add_node("parse_linkedin", node_parse_linkedin)
    workflow.add_node("generate_embeddings", node_generate_embeddings)
    workflow.add_node("faiss_matching", node_faiss_matching)
    workflow.add_node("score_candidates", node_score_candidates)
    workflow.add_node("rank_candidates", node_rank_candidates)
    workflow.add_node("generate_report", node_generate_report)
    workflow.add_node("human_override", node_human_override)
    workflow.add_node("audit_logging", node_audit_logging)

    # --- Define edges (sequential pipeline) ---
    workflow.set_entry_point("parse_jd")
    workflow.add_edge("parse_jd", "parse_resumes")
    workflow.add_edge("parse_resumes", "parse_linkedin")
    workflow.add_edge("parse_linkedin", "generate_embeddings")
    workflow.add_edge("generate_embeddings", "faiss_matching")
    workflow.add_edge("faiss_matching", "score_candidates")
    workflow.add_edge("score_candidates", "rank_candidates")
    workflow.add_edge("rank_candidates", "generate_report")
    workflow.add_edge("generate_report", "human_override")
    workflow.add_edge("human_override", "audit_logging")
    workflow.add_edge("audit_logging", END)

    return workflow.compile()


def create_initial_state(
    jd_text: str,
    resume_files: List[Dict[str, Any]],
    linkedin_files: List[Dict[str, Any]] = None,
    overrides: Dict[str, Dict] = None,
) -> PipelineState:
    """
    Create the initial pipeline state for a new session.

    Args:
        jd_text: Raw job description text.
        resume_files: List of {filename, content} dicts for resumes.
        linkedin_files: Optional list of LinkedIn JSON file dicts.
        overrides: Optional HR overrides to apply.

    Returns:
        Initialized PipelineState.
    """
    return PipelineState(
        session_id=uuid.uuid4().hex,
        started_at=time.time(),
        jd_text=jd_text,
        resume_files=resume_files or [],
        linkedin_files=linkedin_files or [],
        jd_data=None,
        candidate_profiles=[],
        jd_embedding=None,
        candidate_similarities={},
        candidate_scores=[],
        ranked_candidates=[],
        report=None,
        overrides=overrides or {},
        errors=[],
        status="running",
    )


# --- Convenience runner ---
def run_pipeline(
    jd_text: str,
    resume_files: List[Dict[str, Any]],
    linkedin_files: List[Dict[str, Any]] = None,
    overrides: Dict[str, Dict] = None,
) -> PipelineState:
    """
    Run the complete HR pipeline end-to-end.

    Args:
        jd_text: Job description text.
        resume_files: Resume file dicts [{filename, content}].
        linkedin_files: Optional LinkedIn JSON file dicts.
        overrides: Optional HR score overrides.

    Returns:
        Final pipeline state with all results.
    """
    from app.database.db import init_db
    init_db()

    graph = build_workflow()
    initial_state = create_initial_state(
        jd_text=jd_text,
        resume_files=resume_files,
        linkedin_files=linkedin_files,
        overrides=overrides,
    )

    logger.info(
        f"Starting HR pipeline session: {initial_state['session_id']} | "
        f"{len(resume_files)} resumes | "
        f"{len(linkedin_files or [])} LinkedIn profiles"
    )

    final_state = graph.invoke(initial_state)
    return final_state
