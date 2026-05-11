"""
app/api/main.py
================
FastAPI application entry point.
Registers all routers and configures middleware.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import upload, scoring, ranking, override
from app.database.db import init_db
from app.utils.logger import get_logger
from app.utils.constants import API_V1_PREFIX

logger = get_logger(__name__)

# --- Initialize Database ---
init_db()

# --- FastAPI App ---
app = FastAPI(
    title="HR Resume & LinkedIn Shortlisting Agent API",
    description=(
        "AI-powered HR screening system using GPT-4o, LangChain, LangGraph, "
        "and FAISS for semantic resume-JD matching and candidate scoring."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register Routers ---
app.include_router(upload.router, prefix=f"{API_V1_PREFIX}/upload", tags=["Upload"])
app.include_router(scoring.router, prefix=f"{API_V1_PREFIX}/scoring", tags=["Scoring"])
app.include_router(ranking.router, prefix=f"{API_V1_PREFIX}/ranking", tags=["Ranking"])
app.include_router(override.router, prefix=f"{API_V1_PREFIX}/override", tags=["Override"])


# --- Root endpoint ---
@app.get("/", tags=["Health"])
async def root():
    """API health check endpoint."""
    return {
        "status": "running",
        "service": "HR Shortlisting Agent",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "api_version": "v1",
    }


# --- Global exception handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": str(exc)},
    )
