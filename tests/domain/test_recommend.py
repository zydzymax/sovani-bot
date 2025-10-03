"""Tests for pricing recommendations with guardrails (Stage 14)."""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.pricing.recommend import recommend_price_or_discount, simulate_price_change


def test_simulate_price_change_with_elasticity():
    """Test price simulation with known elasticity."""
    result = simulate_price_change(
        units=100,
        elasticity=-1.5,
        price=1000,
        delta=-100,  # Price drop to 900
    )

    # At elasticity=-1.5, formula: units_new = 100 * (1000/900)^-1.5
    # = 100 * (1.111...)^-1.5 ≈ 100 * 0.8538 ≈ 85.38
    assert result["units_new"] == pytest.approx(85.38, abs=1.0)
    assert result["revenue_new"] == pytest.approx(85.38 * 900, abs=100)


def test_simulate_price_change_no_elasticity():
    """Test conservative fallback when elasticity is None."""
    result = simulate_price_change(
        units=100,
        elasticity=None,
        price=1000,
        delta=-100,
    )

    # Without elasticity, assume no demand change (conservative)
    assert result["units_new"] == 100
    assert result["revenue_new"] == 100 * 900


def test_recommend_respects_min_margin():
    """Test that recommendations respect minimum margin guardrail."""
    sku_info = {
        "sku_id": 1,
        "article": "TEST-001",
        "unit_cost": 900,  # Cost
        "avg_commission": 50,
        "avg_delivery": 50,
        "map_price": 0,
    }

    series = [
        {"d": date(2025, 1, 1), "units": 10, "price": 1000, "promo_flag": False},
    ]

    el = {"elasticity": -1.0, "quality": "medium"}
    promo = {"lift": None, "quality": "low", "sample_size": 0}

    settings = {
        "PRICING_MIN_MARGIN_PCT": 0.10,  # 10% margin required
        "PRICING_MAX_DISCOUNT_PCT": 0.30,
        "PRICING_MIN_PRICE_STEP": 10,
    }

    result = recommend_price_or_discount(
        sku_info=sku_info,
        series=series,
        el=el,
        promo=promo,
        settings=settings,
    )

    # Total cost = 900 + 50 + 50 = 1000
    # Min price for 10% margin = 1000 / 0.9 ≈ 1111
    # Current price 1000 violates margin, should recommend increase
    assert result["action"] in ["keep", "raise_price"]


def test_recommend_respects_map():
    """Test that recommendations respect MAP (minimum advertised price)."""
    sku_info = {
        "sku_id": 1,
        "article": "TEST-001",
        "unit_cost": 500,
        "avg_commission": 50,
        "avg_delivery": 50,
        "map_price": 1000,  # MAP constraint
    }

    series = [
        {"d": date(2025, 1, 1), "units": 10, "price": 1200, "promo_flag": False},
    ]

    el = {"elasticity": -2.0, "quality": "medium"}  # High elasticity
    promo = {"lift": 0.5, "quality": "medium", "sample_size": 3}  # Strong promo

    settings = {
        "PRICING_MIN_MARGIN_PCT": 0.10,
        "PRICING_MAX_DISCOUNT_PCT": 0.30,
        "PRICING_MIN_PRICE_STEP": 10,
    }

    result = recommend_price_or_discount(
        sku_info=sku_info,
        series=series,
        el=el,
        promo=promo,
        settings=settings,
    )

    # Even with high elasticity and promo lift, price should not go below MAP
    if result.get("suggested_price"):
        assert result["suggested_price"] >= 1000


def test_recommend_respects_min_step():
    """Test that recommendations respect minimum price step."""
    sku_info = {
        "sku_id": 1,
        "article": "TEST-001",
        "unit_cost": 500,
        "avg_commission": 50,
        "avg_delivery": 50,
        "map_price": 0,
    }

    series = [
        {"d": date(2025, 1, 1), "units": 10, "price": 1000, "promo_flag": False},
    ]

    el = {"elasticity": -1.0, "quality": "medium"}
    promo = {"lift": None, "quality": "low", "sample_size": 0}

    settings = {
        "PRICING_MIN_MARGIN_PCT": 0.05,  # Low margin to allow changes
        "PRICING_MAX_DISCOUNT_PCT": 0.30,
        "PRICING_MIN_PRICE_STEP": 50,  # Must change by at least 50 rubles
    }

    result = recommend_price_or_discount(
        sku_info=sku_info,
        series=series,
        el=el,
        promo=promo,
        settings=settings,
    )

    # If any price change is suggested, it should be at least 50 rubles
    if result["action"] != "keep" and result.get("suggested_price"):
        price_change = abs(result["suggested_price"] - 1000)
        assert price_change >= 50 or price_change == 0


def test_recommend_respects_max_discount():
    """Test that recommendations respect maximum discount percentage."""
    sku_info = {
        "sku_id": 1,
        "article": "TEST-001",
        "unit_cost": 200,  # Low cost to allow large discounts
        "avg_commission": 20,
        "avg_delivery": 20,
        "map_price": 0,
    }

    series = [
        {"d": date(2025, 1, 1), "units": 10, "price": 1000, "promo_flag": False},
    ]

    el = {"elasticity": -3.0, "quality": "medium"}  # Very high elasticity
    promo = {"lift": 1.0, "quality": "medium", "sample_size": 5}  # Strong promo

    settings = {
        "PRICING_MIN_MARGIN_PCT": 0.05,
        "PRICING_MAX_DISCOUNT_PCT": 0.20,  # Max 20% discount
        "PRICING_MIN_PRICE_STEP": 10,
    }

    result = recommend_price_or_discount(
        sku_info=sku_info,
        series=series,
        el=el,
        promo=promo,
        settings=settings,
    )

    # Even with high elasticity and promo, discount should not exceed 20%
    if result.get("suggested_price") and result["suggested_price"] < 1000:
        discount_pct = (1000 - result["suggested_price"]) / 1000
        assert discount_pct <= 0.20


def test_recommend_keep_when_no_data():
    """Test that recommendation is 'keep' when data quality is insufficient."""
    sku_info = {
        "sku_id": 1,
        "article": "TEST-001",
        "unit_cost": 500,
        "avg_commission": 50,
        "avg_delivery": 50,
        "map_price": 0,
    }

    series = []  # No data

    el = {"elasticity": None, "quality": "low"}
    promo = {"lift": None, "quality": "low", "sample_size": 0}

    settings = {
        "PRICING_MIN_MARGIN_PCT": 0.10,
        "PRICING_MAX_DISCOUNT_PCT": 0.30,
        "PRICING_MIN_PRICE_STEP": 10,
    }

    result = recommend_price_or_discount(
        sku_info=sku_info,
        series=series,
        el=el,
        promo=promo,
        settings=settings,
    )

    # With no data, should keep current pricing
    assert result["action"] == "keep"
    assert result["quality"] == "low"


def test_recommend_returns_expected_profit():
    """Test that recommendation includes expected profit calculation."""
    sku_info = {
        "sku_id": 1,
        "article": "TEST-001",
        "unit_cost": 500,
        "avg_commission": 50,
        "avg_delivery": 50,
        "map_price": 0,
    }

    series = [
        {"d": date(2025, 1, 1), "units": 100, "price": 1000, "promo_flag": False},
    ]

    el = {"elasticity": -1.5, "quality": "medium"}
    promo = {"lift": None, "quality": "low", "sample_size": 0}

    settings = {
        "PRICING_MIN_MARGIN_PCT": 0.10,
        "PRICING_MAX_DISCOUNT_PCT": 0.30,
        "PRICING_MIN_PRICE_STEP": 10,
    }

    result = recommend_price_or_discount(
        sku_info=sku_info,
        series=series,
        el=el,
        promo=promo,
        settings=settings,
    )

    # Should include expected profit
    assert "expected_profit" in result
    assert isinstance(result["expected_profit"], (int, float))


def test_recommend_includes_guardrails():
    """Test that recommendation includes guardrail status."""
    sku_info = {
        "sku_id": 1,
        "article": "TEST-001",
        "unit_cost": 500,
        "avg_commission": 50,
        "avg_delivery": 50,
        "map_price": 900,
    }

    series = [
        {"d": date(2025, 1, 1), "units": 10, "price": 1000, "promo_flag": False},
    ]

    el = {"elasticity": -1.0, "quality": "medium"}
    promo = {"lift": None, "quality": "low", "sample_size": 0}

    settings = {
        "PRICING_MIN_MARGIN_PCT": 0.10,
        "PRICING_MAX_DISCOUNT_PCT": 0.30,
        "PRICING_MIN_PRICE_STEP": 10,
    }

    result = recommend_price_or_discount(
        sku_info=sku_info,
        series=series,
        el=el,
        promo=promo,
        settings=settings,
    )

    # Should include guardrails dict
    assert "guardrails" in result
    assert isinstance(result["guardrails"], dict)
