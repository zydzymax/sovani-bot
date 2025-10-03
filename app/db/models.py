"""SQLAlchemy ORM models for SoVAni Bot.

This module defines the database schema for:
- Reference data (SKUs, Warehouses, Cost History, Commission Rules)
- Fact tables (Daily Sales, Daily Stock, Reviews, Cashflows)
- Derived/Calculated tables (Metrics, Supply Recommendations)

All dates are stored in UTC. Display timezone conversion happens in presentation layer.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# =============================================================================
# Reference Tables (Справочники)
# =============================================================================


class SKU(Base):
    """Stock Keeping Unit - товарные позиции на маркетплейсах.

    Stores both WB (nm_id) and Ozon (ozon_id) identifiers.
    """

    __tablename__ = "sku"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(10), index=True)  # "WB" | "OZON"
    nm_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Wildberries nmId
    ozon_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Ozon product_id
    article: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Артикул продавца
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Бренд/торговая марка
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Категория товара

    __table_args__ = (
        UniqueConstraint("marketplace", "nm_id", name="uq_sku_wb_nm_id"),
        UniqueConstraint("marketplace", "ozon_id", name="uq_sku_ozon_id"),
    )


class Warehouse(Base):
    """Склад/регион маркетплейса.

    Stores warehouse/fulfillment center information.
    """

    __tablename__ = "warehouse"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(10), index=True)  # "WB" | "OZON"
    code: Mapped[str] = mapped_column(String(50))  # Код склада (например, "Коледино")
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Полное название
    region: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Регион (для группировки)

    __table_args__ = (UniqueConstraint("marketplace", "code", name="uq_wh_code"),)


class CostPriceHistory(Base):
    """История себестоимости товаров.

    Stores cost price history with date ranges (dt_from).
    Current cost for date D is the latest record where dt_from <= D.
    """

    __tablename__ = "cost_price_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("sku.id", ondelete="CASCADE"), index=True)
    dt_from: Mapped[date] = mapped_column(Date, index=True)  # Дата начала действия себестоимости
    cost_price: Mapped[float] = mapped_column(Float)  # Себестоимость (в рублях за единицу)

    __table_args__ = (UniqueConstraint("sku_id", "dt_from", name="uq_cost_from"),)


class CommissionRule(Base):
    """Правила комиссий маркетплейсов.

    Stores commission rules as JSON (can vary by category, date, etc).
    """

    __tablename__ = "commission_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(String(10), index=True)  # "WB" | "OZON"
    dt_from: Mapped[date] = mapped_column(Date, index=True)  # Дата начала действия
    rule_json: Mapped[dict] = mapped_column(
        JSON
    )  # Правила в JSON (по категориям, диапазонам цен и т.д.)


# =============================================================================
# Fact Tables (Ежедневные срезы)
# =============================================================================


class DailySales(Base):
    """Ежедневные продажи (агрегированные).

    Stores daily aggregated sales data from WB/Ozon APIs.
    Idempotent upserts using src_hash.
    """

    __tablename__ = "daily_sales"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    d: Mapped[date] = mapped_column(Date, index=True)  # Дата (UTC)
    sku_id: Mapped[int] = mapped_column(ForeignKey("sku.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouse.id", ondelete="RESTRICT"), index=True, nullable=True
    )

    # Quantities
    qty: Mapped[int] = mapped_column(Integer, default=0)  # Количество проданных единиц
    refunds_qty: Mapped[int] = mapped_column(Integer, default=0)  # Количество возвратов

    # Revenue and costs
    revenue_gross: Mapped[float] = mapped_column(Float, default=0.0)  # Валовая выручка (из API)
    refunds_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Сумма возвратов
    promo_cost: Mapped[float] = mapped_column(Float, default=0.0)  # Затраты на промо/скидки
    delivery_cost: Mapped[float] = mapped_column(Float, default=0.0)  # Логистика/доставка
    commission_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Комиссия маркетплейса

    # Metadata
    channel: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "FBO" | "FBS"
    src_hash: Mapped[str] = mapped_column(String(64))  # SHA256 hash для идемпотентности

    __table_args__ = (
        UniqueConstraint("d", "sku_id", "warehouse_id", name="uq_sales_day_sku_wh"),
        Index("ix_sales_sku_day", "sku_id", "d"),
    )


class DailyStock(Base):
    """Ежедневные остатки (агрегированные).

    Stores daily stock snapshots from WB/Ozon APIs.
    """

    __tablename__ = "daily_stock"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    d: Mapped[date] = mapped_column(Date, index=True)  # Дата среза (UTC)
    sku_id: Mapped[int] = mapped_column(ForeignKey("sku.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.id", ondelete="RESTRICT"), index=True
    )

    # Stock quantities
    on_hand: Mapped[int] = mapped_column(Integer, default=0)  # Остаток на складе (доступно)
    in_transit: Mapped[int] = mapped_column(Integer, default=0)  # В пути/в резерве

    # Metadata
    src_hash: Mapped[str] = mapped_column(String(64))  # SHA256 hash для идемпотентности

    __table_args__ = (
        UniqueConstraint("d", "sku_id", "warehouse_id", name="uq_stock_day_sku_wh"),
        Index("ix_stock_sku_day", "sku_id", "d"),
    )


class Review(Base):
    """Отзывы покупателей.

    Stores customer reviews from WB/Ozon.
    """

    __tablename__ = "reviews"

    review_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )  # Уникальный ID отзыва от API
    marketplace: Mapped[str] = mapped_column(String(10), index=True)  # "WB" | "OZON"
    sku_id: Mapped[int | None] = mapped_column(
        ForeignKey("sku.id", ondelete="SET NULL"), nullable=True
    )

    # Review details
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), index=True
    )  # Дата создания (UTC)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Оценка 1-5
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)  # Есть ли фото/видео
    text: Mapped[str | None] = mapped_column(String, nullable=True)  # Текст отзыва

    # Reply status
    reply_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # "pending" | "sent" | "failed"
    reply_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # ID ответа (если есть)
    reply_text: Mapped[str | None] = mapped_column(String, nullable=True)  # Текст ответа
    replied_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )  # Дата ответа (UTC)


class Cashflow(Base):
    """Денежные потоки (выплаты, расходы на рекламу, логистику и т.д.).

    Stores financial transactions (payouts, ad spend, fees, etc).
    """

    __tablename__ = "cashflows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    d: Mapped[date] = mapped_column(Date, index=True)  # Дата транзакции (UTC)
    marketplace: Mapped[str] = mapped_column(String(10), index=True)  # "WB" | "OZON"

    # Transaction details
    type: Mapped[str] = mapped_column(
        String(50)
    )  # "payout" | "advertising" | "logistics" | "return" | "penalty" | etc
    amount: Mapped[float] = mapped_column(
        Float
    )  # Сумма (положительная для поступлений, отрицательная для расходов)
    ref_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Референс ID (номер выплаты, ID кампании и т.д.)

    # Metadata
    src_hash: Mapped[str] = mapped_column(String(64))  # SHA256 hash для идемпотентности

    __table_args__ = (Index("ix_cash_market_day", "marketplace", "d"),)


# =============================================================================
# Derived/Calculated Tables (Производные метрики)
# =============================================================================


class MetricsDaily(Base):
    """Ежедневные метрики (рассчитываемые).

    Stores calculated daily metrics: net revenue, COGS, profit, margin, rolling velocity.
    """

    __tablename__ = "metrics_daily"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    d: Mapped[date] = mapped_column(Date, index=True)  # Дата расчёта (UTC)
    sku_id: Mapped[int] = mapped_column(ForeignKey("sku.id", ondelete="RESTRICT"), index=True)

    # Financial metrics
    revenue_net: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # Чистая выручка (gross - возвраты - промо - доставка - комиссия)
    cogs: Mapped[float] = mapped_column(Float, default=0.0)  # Себестоимость
    profit: Mapped[float] = mapped_column(Float, default=0.0)  # Прибыль (revenue_net - cogs)
    margin: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # Маржинальность % (profit / revenue_net * 100)

    # Rolling velocity (Sales Velocity - единиц в день)
    sv7: Mapped[float] = mapped_column(Float, default=0.0)  # За последние 7 дней
    sv14: Mapped[float] = mapped_column(Float, default=0.0)  # За последние 14 дней
    sv28: Mapped[float] = mapped_column(Float, default=0.0)  # За последние 28 дней

    # Inventory metrics
    stock_cover_days: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # Запас (дней) при текущей скорости продаж

    __table_args__ = (UniqueConstraint("d", "sku_id", name="uq_metrics_day_sku"),)


class AdviceSupply(Base):
    """Рекомендации по пополнению запасов.

    Stores supply recommendations based on velocity and safety stock calculations.
    """

    __tablename__ = "advice_supply"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    d: Mapped[date] = mapped_column(Date, index=True)  # Дата расчёта рекомендации (UTC)
    sku_id: Mapped[int] = mapped_column(ForeignKey("sku.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.id", ondelete="RESTRICT"), index=True
    )

    # Recommendation parameters
    window_days: Mapped[int] = mapped_column(Integer)  # Окно планирования (14 или 28 дней)
    recommended_qty: Mapped[int] = mapped_column(Integer)  # Рекомендуемое количество для заказа

    # Metadata
    rationale_hash: Mapped[str] = mapped_column(
        String(64)
    )  # Hash расчёта (для отслеживания изменений)

    __table_args__ = (
        UniqueConstraint(
            "d",
            "sku_id",
            "warehouse_id",
            "window_days",
            name="uq_advice_day_sku_wh_win",
        ),
    )


# =============================================================================
# Monitoring Tables (Stage 11)
# =============================================================================


class JobRun(Base):
    """Scheduler job execution log for monitoring.

    Tracks all scheduled job runs with status, duration, and errors.
    Used for observability and alerting.
    """

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(
        String(100), index=True
    )  # e.g., "sync_wb_orders", "check_reviews"
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # "success", "failed", "running"
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    job_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Extra context (e.g., records processed)

    __table_args__ = (Index("ix_job_runs_name_started", "job_name", "started_at"),)


class PricingAdvice(Base):
    """Pricing and discount recommendations (Stage 14).

    Stores price/discount recommendations with guardrails and explanations.
    """

    __tablename__ = "pricing_advice"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    d: Mapped[date] = mapped_column(Date, index=True)  # Date of advice
    sku_id: Mapped[int] = mapped_column(ForeignKey("sku.id", ondelete="CASCADE"), index=True)

    # Recommendations
    suggested_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_profit: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Quality and rationale
    quality: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "low" | "medium"
    rationale_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Action reason

    __table_args__ = (UniqueConstraint("d", "sku_id", name="uq_pricing_advice_d_sku"),)
