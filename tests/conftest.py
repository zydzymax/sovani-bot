"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import asyncio
import os
import re

import pytest
import vcr as vcr_module
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base

SENSITIVE_HEADERS = [
    ("Authorization", "Bearer ***"),
    ("Client-Id", "***"),
    ("Api-Key", "***"),
    ("X-Api-Key", "***"),
]


def scrub_body(body: str) -> str:
    """Sanitize sensitive data in request/response bodies."""
    # OpenAI API keys
    body = re.sub(r"\bsk-[A-Za-z0-9]{8,}\b", "sk-***", body)
    # Telegram bot tokens
    body = re.sub(r"\b\d{9,11}:[A-Za-z0-9_-]{20,}\b", "***:***", body)
    # Bearer tokens
    body = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._-]{10,}\b", "Bearer ***", body)
    # Real SKU IDs (replace with placeholders)
    body = re.sub(r"\b\d{8,11}\b", "12345678", body)
    # Real article codes
    body = re.sub(r'"supplierArticle"\s*:\s*"[^"]{5,}"', '"supplierArticle":"TEST-SKU-001"', body)
    body = re.sub(r'"offer_id"\s*:\s*"[^"]{5,}"', '"offer_id":"TEST-SKU-001"', body)
    return body


@pytest.fixture(scope="session")
def vcr():
    """VCR fixture for recording/replaying HTTP interactions."""
    return vcr_module.VCR(
        cassette_library_dir="tests/cassettes",
        record_mode=os.getenv("VCR_MODE", "once"),  # once/new_episodes/none
        filter_headers=SENSITIVE_HEADERS,
        before_record_response=lambda r: {
            **r,
            "body": (
                {
                    "string": scrub_body(r["body"]["string"].decode("utf-8", "ignore")).encode(
                        "utf-8"
                    )
                }
                if isinstance(r.get("body", {}).get("string"), (bytes, bytearray))
                else r
            ),
        },
        before_record_request=lambda r: r,
    )


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations_before_tests():
    """
    Automatically apply Alembic migrations to test DB before all tests.

    Uses DATABASE_URL from environment. For in-memory tests, this ensures
    BI views and all schema changes are applied before contract tests run.
    """
    db_url = os.getenv("DATABASE_URL", "sqlite:///./test_sovani.db")

    # Skip migration for in-memory databases (they use Base.metadata.create_all)
    if ":memory:" in db_url:
        return

    # Apply migrations
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    try:
        command.upgrade(cfg, "head")
    except Exception as e:
        print(f"Warning: Migration failed (may already be applied): {e}")


@pytest.fixture
def db() -> Session:
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def run_async(async_fn, *args, **kwargs):
    """Helper to run async functions in sync pytest context."""
    return asyncio.get_event_loop().run_until_complete(async_fn(*args, **kwargs))


# Make run_async available as pytest.run
pytest.run = run_async
