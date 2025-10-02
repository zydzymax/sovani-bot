"""Tests for job monitoring service."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, JobRun
from app.services.job_monitoring import get_job_statistics, get_job_status, monitor_job


@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


def test_monitor_job_success(test_db, monkeypatch):
    """Test monitor_job context manager for successful job."""
    # Patch SessionLocal to return test_db
    from app.services import job_monitoring

    monkeypatch.setattr(job_monitoring, "SessionLocal", lambda: test_db)

    # Run job with monitoring
    with monitor_job("test_job"):
        time.sleep(0.01)  # Simulate work

    # Check job run was created
    runs = test_db.query(JobRun).filter(JobRun.job_name == "test_job").all()
    assert len(runs) == 1

    run = runs[0]
    assert run.status == "success"
    assert run.duration_seconds is not None
    assert run.duration_seconds > 0
    assert run.error_message is None


def test_monitor_job_failure(test_db, monkeypatch):
    """Test monitor_job context manager for failed job."""
    from app.services import job_monitoring

    monkeypatch.setattr(job_monitoring, "SessionLocal", lambda: test_db)

    # Run job that raises exception
    with pytest.raises(ValueError):
        with monitor_job("failing_job"):
            raise ValueError("Test error")

    # Check job run was created with failure status
    runs = test_db.query(JobRun).filter(JobRun.job_name == "failing_job").all()
    assert len(runs) == 1

    run = runs[0]
    assert run.status == "failed"
    assert run.error_message == "Test error"
    assert run.duration_seconds is not None


def test_get_job_status(test_db, monkeypatch):
    """Test get_job_status function."""
    from app.services import job_monitoring

    monkeypatch.setattr(job_monitoring, "SessionLocal", lambda: test_db)

    # Create some job runs
    test_db.add(
        JobRun(
            job_name="job1",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            status="success",
            duration_seconds=1.5,
        )
    )
    test_db.add(
        JobRun(
            job_name="job2",
            started_at=datetime.now(UTC),
            status="running",
        )
    )
    test_db.commit()

    # Get all jobs
    status = get_job_status(limit=10)
    assert len(status) == 2

    # Get specific job
    status = get_job_status(job_name="job1", limit=10)
    assert len(status) == 1
    assert status[0]["job_name"] == "job1"
    assert status[0]["status"] == "success"


def test_get_job_statistics(test_db, monkeypatch):
    """Test get_job_statistics function."""
    from app.services import job_monitoring

    monkeypatch.setattr(job_monitoring, "SessionLocal", lambda: test_db)

    # Create job runs
    for i in range(5):
        status = "success" if i < 4 else "failed"
        test_db.add(
            JobRun(
                job_name="test_job",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                status=status,
                duration_seconds=2.0,
            )
        )
    test_db.commit()

    # Get statistics
    stats = get_job_statistics("test_job")

    assert stats["job_name"] == "test_job"
    assert stats["total_runs"] == 5
    assert stats["successful_runs"] == 4
    assert stats["failed_runs"] == 1
    assert stats["success_rate"] == 80.0
    assert stats["avg_duration_seconds"] == 2.0
