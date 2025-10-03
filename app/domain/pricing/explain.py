"""Explainability for pricing recommendations."""

from __future__ import annotations

import hashlib


def build_pricing_explanation(
    sku: str,
    price: float | None,
    elasticity: float | None,
    lift: float | None,
    guardrails: dict,
    expected_profit: float,
    action: str,
) -> tuple[str, str]:
    """Generate human-readable explanation and SHA256 hash.

    Args:
        sku: SKU identifier (article)
        price: Current or suggested price
        elasticity: Price elasticity estimate
        lift: Promo lift estimate
        guardrails: Guardrail checks (min_margin_ok, map_ok, etc)
        expected_profit: Expected profit change
        action: Recommended action (raise/lower/keep)

    Returns:
        Tuple of (explanation_text, rationale_hash)

    """
    # Format elasticity
    e = f"{elasticity:+.2f}" if elasticity is not None else "—"

    # Format promo lift
    l = f"{lift:+.0%}" if lift is not None else "—"

    # Format price
    p = f"{price:.0f}" if price else "—"

    # Format guardrails
    g = []
    if guardrails:
        for k, v in guardrails.items():
            g.append(f"{k}={'✓' if v else '✗'}")

    # Build explanation text
    txt = (
        f"SKU {sku}: текущая цена {p}₽, эластичность≈{e}, promo lift≈{l}, "
        f"ограничения[{', '.join(g) if g else '—'}], действие={action}, "
        f"ожидаемая прибыль={expected_profit:.2f}₽"
    )

    # Generate SHA256 hash
    h = hashlib.sha256(txt.encode("utf-8")).hexdigest()

    return txt, h
