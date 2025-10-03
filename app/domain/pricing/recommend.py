"""Price and discount recommendations with guardrails."""

from __future__ import annotations


def simulate_price_change(
    units: float,
    elasticity: float | None,
    price: float,
    delta: float,
) -> dict:
    """Simulate demand change with price adjustment.

    Model: units_new = units * (price / (price + delta)) ** elasticity

    Args:
        units: Current units sold
        elasticity: Price elasticity (negative for normal goods)
        price: Current price
        delta: Price change (positive = increase, negative = decrease)

    Returns:
        Dict with units_new and revenue_new

    """
    if not elasticity:
        # Conservative: no elasticity data, assume no demand change
        units_new = units
    else:
        new_price = max(0.01, price + delta)
        units_new = units * (price / new_price) ** elasticity

    revenue = (price + delta) * units_new

    return {
        "units_new": max(0.0, units_new),
        "revenue_new": max(0.0, revenue),
    }


def recommend_price_or_discount(
    *,
    sku_info: dict,
    series: list[dict],
    el: dict,
    promo: dict,
    settings: dict,
) -> dict:
    """Generate price/discount recommendation with guardrails.

    Guardrails:
    - min_margin: (price - cost - comm - delivery) / price >= MIN_MARGIN_PCT
    - MAP: price >= MAP[sku]
    - step: |delta| >= MIN_PRICE_STEP
    - max_discount: discount_pct <= MAX_DISCOUNT_PCT

    Args:
        sku_info: SKU metadata (sku_id, unit_cost, map_price, etc)
        series: Price-demand time series
        el: Elasticity estimate
        promo: Promo lift estimate
        settings: Config settings (margins, steps, etc)

    Returns:
        Recommendation dict with suggested_price, guardrails, expected_profit

    """
    # Extract current price from valid observations
    valid = [r for r in series if r["units"] > 0 and 10 <= r["price"] <= 100000]

    if not valid:
        return {
            "sku_id": sku_info["sku_id"],
            "current_price": None,
            "suggested_price": None,
            "suggested_discount_pct": None,
            "expected_units": 0,
            "expected_profit": 0,
            "guardrails": {"reason": "no_valid_price"},
            "quality": "low",
            "reason_code": "no_price",
            "action": "keep",
        }

    # Current price: average from recent observations
    current_price = sum(r["price"] for r in valid) / len(valid)

    # Extract cost parameters
    unit_cost = float(sku_info.get("unit_cost", 0.0))
    avg_commission = float(sku_info.get("avg_commission", 0.0))
    avg_delivery = float(sku_info.get("avg_delivery", 0.0))

    # Guardrail thresholds
    min_margin = float(settings["PRICING_MIN_MARGIN_PCT"])
    min_step = float(settings["PRICING_MIN_PRICE_STEP"])
    max_discount = float(settings["PRICING_MAX_DISCOUNT_PCT"])
    map_price = float(sku_info.get("map_price", 0.0) or 0.0)

    # Baseline units: median from valid observations
    base_units_list = sorted(r["units"] for r in valid)
    base_units = base_units_list[len(base_units_list) // 2] if base_units_list else 0.0

    # Candidate price changes: raise or lower by step
    candidates = [
        ("lower", -min_step),
        ("raise", +min_step),
    ]

    best = None

    for action, delta in candidates:
        sim = simulate_price_change(base_units, el.get("elasticity"), current_price, delta)
        price_new = current_price + delta

        if price_new <= 0:
            continue

        # Check guardrails
        margin = (
            (price_new - unit_cost - avg_commission - avg_delivery) / price_new if price_new else 0
        )

        guard = {
            "min_margin_ok": margin >= min_margin,
            "map_ok": (price_new >= map_price) if map_price else True,
            "step_ok": abs(delta) >= min_step,
            "max_discount_ok": (
                (abs(delta) / current_price) <= max_discount if delta < 0 else True
            ),
        }

        # Skip if any guardrail violated
        if not all(guard.values()):
            continue

        # Calculate expected profit
        expected_profit = (price_new - unit_cost - avg_commission - avg_delivery) * sim["units_new"]

        cand = {
            "sku_id": sku_info["sku_id"],
            "current_price": round(current_price, 2),
            "suggested_price": round(price_new, 2),
            "suggested_discount_pct": abs(delta) / current_price if delta < 0 else 0.0,
            "expected_units": round(sim["units_new"], 2),
            "expected_profit": round(expected_profit, 2),
            "guardrails": guard,
            "quality": el.get("quality") or "low",
            "reason_code": "elasticity_based" if el.get("elasticity") else "no_elasticity",
            "action": action,
        }

        # Keep best by expected profit
        if not best or cand["expected_profit"] > best["expected_profit"]:
            best = cand

    # If no candidate passed guardrails, recommend keeping current price
    if not best:
        return {
            "sku_id": sku_info["sku_id"],
            "current_price": round(current_price, 2),
            "suggested_price": None,
            "suggested_discount_pct": None,
            "expected_units": float(base_units),
            "expected_profit": 0.0,
            "guardrails": {"blocked": True},
            "quality": el.get("quality") or "low",
            "reason_code": "guardrails_block",
            "action": "keep",
        }

    return best
