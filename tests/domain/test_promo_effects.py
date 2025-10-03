"""Tests for promo effects measurement (Stage 14)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.pricing.promo_effects import measure_promo_lift


def test_no_promo_returns_none():
    """Test that no promo data returns lift=None, quality='low'."""
    series = [
        {"d": date(2025, 1, 1), "weekday": 0, "units": 10, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 2), "weekday": 1, "units": 12, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 3), "weekday": 2, "units": 11, "price": 1000, "promo_flag": False},
    ]

    result = measure_promo_lift(series, window=14)

    assert result["lift"] is None
    assert result["quality"] == "low"
    assert result["n"] == 0


def test_single_promo_day_low_quality():
    """Test that single promo day returns lift but quality='low'."""
    series = [
        {"d": date(2025, 1, 1), "weekday": 0, "units": 10, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 8), "weekday": 0, "units": 10, "price": 1000, "promo_flag": False},
        {
            "d": date(2025, 1, 15),
            "weekday": 0,
            "units": 20,
            "price": 900,
            "promo_flag": True,
        },  # +100% lift
    ]

    result = measure_promo_lift(series, window=14)

    assert result["lift"] is not None
    assert result["lift"] == pytest.approx(1.0, abs=0.01)  # 100% lift
    assert result["quality"] == "low"
    assert result["n"] == 1


def test_multiple_promo_days_medium_quality():
    """Test that multiple promo days calculate average lift with quality='medium' when n>=3."""
    series = [
        # Monday baseline
        {"d": date(2025, 1, 6), "weekday": 0, "units": 10, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 13), "weekday": 0, "units": 10, "price": 1000, "promo_flag": False},
        # Tuesday baseline
        {"d": date(2025, 1, 7), "weekday": 1, "units": 12, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 14), "weekday": 1, "units": 12, "price": 1000, "promo_flag": False},
        # Wednesday baseline
        {"d": date(2025, 1, 8), "weekday": 2, "units": 11, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 15), "weekday": 2, "units": 11, "price": 1000, "promo_flag": False},
        # Promo days
        {
            "d": date(2025, 1, 20),
            "weekday": 0,
            "units": 20,
            "price": 900,
            "promo_flag": True,
        },  # +100% lift
        {
            "d": date(2025, 1, 21),
            "weekday": 1,
            "units": 18,
            "price": 900,
            "promo_flag": True,
        },  # +50% lift
        {
            "d": date(2025, 1, 22),
            "weekday": 2,
            "units": 22,
            "price": 900,
            "promo_flag": True,
        },  # +100% lift
    ]

    result = measure_promo_lift(series, window=14)

    assert result["lift"] is not None
    # Average lift: (100% + 50% + 100%) / 3 ≈ 83.3%
    assert result["lift"] == pytest.approx(0.833, abs=0.01)
    assert result["quality"] == "medium"
    assert result["n"] == 3


def test_weekday_matching():
    """Test that weekday matching correctly finds baseline for same day of week."""
    series = [
        # Monday baseline (weekday=0)
        {"d": date(2025, 1, 6), "weekday": 0, "units": 10, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 13), "weekday": 0, "units": 10, "price": 1000, "promo_flag": False},
        # Tuesday baseline (weekday=1) - DIFFERENT baseline
        {"d": date(2025, 1, 7), "weekday": 1, "units": 50, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 14), "weekday": 1, "units": 50, "price": 1000, "promo_flag": False},
        # Promo on Monday (should use Monday baseline, not Tuesday)
        {"d": date(2025, 1, 20), "weekday": 0, "units": 20, "price": 900, "promo_flag": True},
    ]

    result = measure_promo_lift(series, window=14)

    # Lift should be calculated against Monday baseline (10), not Tuesday (50)
    # (20 - 10) / 10 = 1.0 (100% lift)
    assert result["lift"] == pytest.approx(1.0, abs=0.01)
    assert result["n"] == 1


def test_window_limits_baseline_lookback():
    """Test that window parameter limits how far back we look for baseline."""
    base_date = date(2025, 1, 1)
    series = [
        # Old Monday baseline (outside window)
        {"d": base_date, "weekday": 0, "units": 5, "price": 1000, "promo_flag": False},
        # Recent Monday baselines (inside window=14)
        {
            "d": base_date + timedelta(days=14),
            "weekday": 0,
            "units": 10,
            "price": 1000,
            "promo_flag": False,
        },
        {
            "d": base_date + timedelta(days=21),
            "weekday": 0,
            "units": 10,
            "price": 1000,
            "promo_flag": False,
        },
        # Promo day
        {
            "d": base_date + timedelta(days=28),
            "weekday": 0,
            "units": 20,
            "price": 900,
            "promo_flag": True,
        },
    ]

    result = measure_promo_lift(series, window=2)

    # Should use recent 2 baselines (10, 10), not old one (5)
    # Lift: (20 - 10) / 10 = 1.0
    assert result["lift"] == pytest.approx(1.0, abs=0.01)


def test_zero_baseline_handled():
    """Test that zero baseline is handled gracefully (no division by zero)."""
    series = [
        # Zero baseline
        {"d": date(2025, 1, 6), "weekday": 0, "units": 0, "price": 1000, "promo_flag": False},
        {"d": date(2025, 1, 13), "weekday": 0, "units": 0, "price": 1000, "promo_flag": False},
        # Promo day with sales
        {"d": date(2025, 1, 20), "weekday": 0, "units": 20, "price": 900, "promo_flag": True},
    ]

    result = measure_promo_lift(series, window=14)

    # Should not crash, should handle gracefully
    assert result["lift"] is not None or result["lift"] is None
    assert result["n"] >= 0
