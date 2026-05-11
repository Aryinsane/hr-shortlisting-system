"""
app/database/db.py
==================
SQLAlchemy database engine and session management for SQLite.
Used exclusively for audit logs, overrides, candidate metadata, and reports.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.utils.logger import get_logger

logger = get_logger(__name__)

# --- Database URL ---
# Default to local SQLite; can be overridden via DATABASE_URL env var
DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///./app/database/audit_logs.db"
)

# --- Create engine ---
# connect_args is SQLite-specific: allows multi-threaded access
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # Set to True for SQL debug logging
)

# --- Session factory ---
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# --- Base class for ORM models ---
Base = declarative_base()


def init_db() -> None:
    """
    Initialize the database by creating all tables defined in models.
    Call this once at application startup.
    """
    # Import models here to ensure they are registered with Base
    from app.database import models  # noqa: F401

    # Ensure the directory exists for SQLite file
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized — all tables created.")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    Automatically closes the session after the request.

    Yields:
        SQLAlchemy Session instance.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
