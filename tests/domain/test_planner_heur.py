"""Tests for heuristic supply planner."""

from __future__ import annotations

import pytest

from app.domain.supply.constraints import PlanningCandidate
from app.domain.supply.planner_heur import ceil_to_multiplicity, plan_heuristic


def test_ceil_to_multiplicity():
    """Test rounding to nearest multiple."""
    assert ceil_to_multiplicity(23, 10) == 30
    assert ceil_to_multiplicity(20, 10) == 20
    assert ceil_to_multiplicity(21, 10) == 30
    assert ceil_to_multiplicity(7, 5) == 10
    assert ceil_to_multiplicity(5, 5) == 5
    assert ceil_to_multiplicity(23, 1) == 23  # No rounding if mult=1


def test_heuristic_respects_min_batch():
    """Planner should respect minimum batch size."""
    candidate: PlanningCandidate = {
        "marketplace": "WB",
        "wh_id": 1,
        "wh_name": "Казань",
        "sku_id": 1,
        "article": "TEST-001",
        "nm_id": "12345",
        "ozon_id": None,
        "sv": 2.0,
        "window": 14,
        "on_hand": 20,
        "in_transit": 0,
        "forecast": 28,  # 2 * 14
        "safety": 5,
        "min_batch": 10,
        "multiplicity": 1,
        "max_per_slot": 500,
        "unit_cost": 100.0,
    }

    # Need = 28 + 5 - 20 = 13, but min_batch=10, so should recommend 13
    plans = plan_heuristic([candidate])

    assert len(plans) == 1
    assert plans[0].recommended_qty >= candidate["min_batch"]


def test_heuristic_respects_multiplicity():
    """Planner should round to multiplicity."""
    candidate: PlanningCandidate = {
        "marketplace": "WB",
        "wh_id": 1,
        "wh_name": "Казань",
        "sku_id": 1,
        "article": "TEST-001",
        "nm_id": "12345",
        "ozon_id": None,
        "sv": 2.0,
        "window": 14,
        "on_hand": 10,
        "in_transit": 0,
        "forecast": 28,
        "safety": 5,
        "min_batch": 5,
        "multiplicity": 10,
        "max_per_slot": 500,
        "unit_cost": 100.0,
    }

    # Need = 28 + 5 - 10 = 23 → round to mult=10 → 30
    plans = plan_heuristic([candidate])

    assert len(plans) == 1
    assert plans[0].recommended_qty % candidate["multiplicity"] == 0


def test_heuristic_no_plan_if_no_need():
    """Planner should not recommend if stock is sufficient."""
    candidate: PlanningCandidate = {
        "marketplace": "WB",
        "wh_id": 1,
        "wh_name": "Казань",
        "sku_id": 1,
        "article": "TEST-001",
        "nm_id": "12345",
        "ozon_id": None,
        "sv": 2.0,
        "window": 14,
        "on_hand": 50,  # More than enough
        "in_transit": 10,
        "forecast": 28,
        "safety": 5,
        "min_batch": 5,
        "multiplicity": 1,
        "max_per_slot": 500,
        "unit_cost": 100.0,
    }

    # Need = 28 + 5 - 60 = -27 → 0 (no need)
    plans = plan_heuristic([candidate])

    assert len(plans) == 0


def test_heuristic_respects_max_per_slot():
    """Planner should cap quantity at max_per_slot."""
    candidate: PlanningCandidate = {
        "marketplace": "WB",
        "wh_id": 1,
        "wh_name": "Казань",
        "sku_id": 1,
        "article": "TEST-001",
        "nm_id": "12345",
        "ozon_id": None,
        "sv": 50.0,
        "window": 14,
        "on_hand": 0,
        "in_transit": 0,
        "forecast": 700,  # 50 * 14
        "safety": 100,
        "min_batch": 5,
        "multiplicity": 1,
        "max_per_slot": 200,
        "unit_cost": 100.0,
    }

    # Need = 700 + 100 = 800, but max_per_slot=200
    plans = plan_heuristic([candidate])

    assert len(plans) == 1
    assert plans[0].recommended_qty <= candidate["max_per_slot"]
