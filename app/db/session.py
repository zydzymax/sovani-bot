"""Database session management for SoVAni Bot.

This module provides SQLAlchemy engine and session factory configured
from app.core.config settings.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

# Create engine from settings
_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    future=True,  # Use SQLAlchemy 2.0 API
    echo=False,  # Set to True for SQL debug logging
)

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def get_db():
    """Get database session (dependency injection for FastAPI/handlers)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
