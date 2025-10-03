"""Tests for operational health check detectors."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ops.detectors import (
    check_api_latency_p95,
    check_cash_balance_threshold,
    check_commission_outliers,
    check_db_growth,
    check_ingest_success_rate,
    check_scheduler_on_time,
    run_all_detectors,
)


def test_check_api_latency_p95_placeholder(db: Session):
    """Test API latency check (placeholder implementation)."""
    result = check_api_latency_p95(db)

    assert result["ok"] is True
    assert result["severity"] == "info"
    assert "fingerprint" in result
    assert "extras" in result


def test_check_ingest_success_rate_no_data(db: Session):
    """Test ingest success rate with no data."""
    result = check_ingest_success_rate(db)

    assert result["ok"] is False
    assert result["severity"] == "error"
    assert "no data ingested" in result["msg"].lower()


def test_check_ingest_success_rate_with_data(db: Session):
    """Test ingest success rate with existing data."""
    # Insert test sales data for yesterday
    yesterday = date.today() - timedelta(days=1)
    db.execute(
        text(
            """
        INSERT INTO daily_sales
        (d, sku_id, marketplace, revenue_gross, qty, commission_amount, delivery_cost)
        VALUES (:d, 1, 'WB', 1000.0, 10, 150.0, 50.0)
        """
        ),
        {"d": yesterday},
    )
    db.commit()

    result = check_ingest_success_rate(db)

    assert result["ok"] is True
    assert result["severity"] == "info"
    assert result["extras"]["records_24h"] >= 1


def test_check_scheduler_on_time_placeholder(db: Session):
    """Test scheduler on-time check (placeholder)."""
    result = check_scheduler_on_time(db)

    assert result["ok"] is True
    assert result["severity"] == "info"


def test_check_cash_balance_threshold_no_data(db: Session):
    """Test cash balance check with no data."""
    result = check_cash_balance_threshold(db)

    assert result["ok"] is True
    assert result["severity"] == "info"
    assert "no cashflow data" in result["msg"].lower()


def test_check_cash_balance_threshold_negative(db: Session):
    """Test cash balance check with negative balance below threshold."""
    # Insert cashflow data with negative balance
    test_date = date.today()
    db.execute(
        text(
            """
        INSERT INTO cashflow_daily (d, marketplace, inflow, outflow, net, src_hash)
        VALUES (:d, 'WB', 5000.0, 20000.0, -15000.0, 'test_hash')
        """
        ),
        {"d": test_date},
    )
    db.commit()

    result = check_cash_balance_threshold(db)

    assert result["ok"] is False
    assert result["severity"] == "critical"
    assert "below alert threshold" in result["msg"]
    assert result["extras"]["balance"] < 0


def test_check_cash_balance_threshold_healthy(db: Session):
    """Test cash balance check with healthy balance."""
    test_date = date.today()
    db.execute(
        text(
            """
        INSERT INTO cashflow_daily (d, marketplace, inflow, outflow, net, src_hash)
        VALUES (:d, 'WB', 20000.0, 5000.0, 15000.0, 'test_hash')
        """
        ),
        {"d": test_date},
    )
    db.commit()

    result = check_cash_balance_threshold(db)

    assert result["ok"] is True
    assert result["severity"] == "info"
    assert "healthy" in result["msg"].lower()


def test_check_commission_outliers_none(db: Session):
    """Test commission outliers check with no outliers."""
    result = check_commission_outliers(db)

    assert result["ok"] is True
    assert result["severity"] == "info"
    assert result["extras"]["outliers_count"] == 0


def test_check_commission_outliers_detected(db: Session):
    """Test commission outliers check with many outliers."""
    # Insert sales and commission rules to create outliers
    # This requires vw_commission_recon view to work properly
    # For now, test the logic with mocked data

    with patch.object(type(db), "execute", return_value=MagicMock(scalar=lambda: 10)):
        result = check_commission_outliers(db)

        assert result["ok"] is False
        assert result["severity"] == "warning"
        assert "outliers detected" in result["msg"]


def test_check_db_growth_healthy(db: Session):
    """Test DB growth check with healthy size."""
    result = check_db_growth(db)

    # Small test DB should pass
    assert result["ok"] is True
    assert result["severity"] == "info"
    assert "healthy" in result["msg"].lower()


def test_run_all_detectors(db: Session):
    """Test running all detectors."""
    results = run_all_detectors(db)

    # Should return 6 detector results
    assert len(results) == 6

    # Each result should have required fields
    for result in results:
        assert "ok" in result
        assert "severity" in result
        assert "msg" in result
        assert "fingerprint" in result
        assert "extras" in result

    # At least some should pass
    passed = sum(1 for r in results if r["ok"])
    assert passed >= 3  # Most placeholders return ok=True


def test_run_all_detectors_with_exception(db: Session):
    """Test run_all_detectors handles exceptions gracefully."""
    # Mock one detector to raise exception
    with patch("app.ops.detectors.check_api_latency_p95", side_effect=RuntimeError("Test error")):
        results = run_all_detectors(db)

        # Should still return results
        assert len(results) == 6

        # First result should be the failed one
        assert results[0]["ok"] is False
        assert results[0]["severity"] == "error"
        assert "crashed" in results[0]["msg"].lower()


def test_detector_fingerprint_consistency():
    """Test that detector fingerprints are deterministic."""
    from app.ops.detectors import _fingerprint

    fp1 = _fingerprint("test_source", "test_key")
    fp2 = _fingerprint("test_source", "test_key")

    assert fp1 == fp2
    assert len(fp1) == 32  # MD5 hex length


def test_detector_fingerprint_uniqueness():
    """Test that different inputs produce different fingerprints."""
    from app.ops.detectors import _fingerprint

    fp1 = _fingerprint("source1", "key1")
    fp2 = _fingerprint("source2", "key1")
    fp3 = _fingerprint("source1", "key2")

    assert fp1 != fp2
    assert fp1 != fp3
    assert fp2 != fp3
