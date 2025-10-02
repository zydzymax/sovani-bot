"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


# Dashboard schemas
class DashboardSummary(BaseModel):
    """Dashboard summary metrics."""

    revenue_net: float = Field(..., description="Net revenue (after refunds, promo, etc.)")
    profit: float = Field(..., description="Total profit")
    margin: float = Field(..., description="Profit margin (%)")
    units: int = Field(..., description="Total units sold")
    refunds_qty: int = Field(..., description="Total refunds quantity")

    class Config:
        from_attributes = True


class SkuMetric(BaseModel):
    """SKU-level metric for top lists."""

    sku_id: int
    sku_key: str | None = None
    article: str | None = None
    marketplace: str | None = None
    metric_value: float
    units: int | None = None

    class Config:
        from_attributes = True


# Reviews schemas
class ReviewDTO(BaseModel):
    """Review data transfer object."""

    review_id: str
    marketplace: str | None = None
    sku_key: str | None = None
    rating: int | None = None
    text: str | None = None
    created_at_utc: str | None = None
    reply_status: str | None = None
    reply_text: str | None = None

    class Config:
        from_attributes = True


class ReplyRequest(BaseModel):
    """Request to reply to a review."""

    text: str = Field(..., min_length=1, max_length=2000)


# Inventory schemas
class StockRow(BaseModel):
    """Stock/inventory row."""

    sku_id: int
    sku_key: str | None = None
    marketplace: str | None = None
    warehouse: str | None = None
    on_hand: int
    in_transit: int
    total: int

    class Config:
        from_attributes = True


# Advice schemas
class AdviceRow(BaseModel):
    """Supply advice row with explainability."""

    sku_id: int
    sku_key: str | None = None
    marketplace: str | None = None
    warehouse: str | None = None
    window_days: int
    recommended_qty: int
    sv: float | None = None
    on_hand: int | None = None
    in_transit: int | None = None
    explain: str | None = Field(None, description="Human-readable rationale")

    class Config:
        from_attributes = True
