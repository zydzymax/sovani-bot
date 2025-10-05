"""Configuration management with pydantic-settings.

Provides type-safe configuration with environment variable validation.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Telegram ===
    telegram_token: str = Field(..., description="Telegram Bot API token")
    manager_chat_id: int = Field(0, description="Telegram chat ID for manager notifications")

    # === Wildberries API (6 tokens) ===
    wb_feedbacks_token: str = Field(..., description="WB token for feedbacks/reviews/chat")
    wb_ads_token: str = Field(..., description="WB token for advertising/promotion")
    wb_stats_token: str = Field(..., description="WB token for stats and financials")
    wb_supply_token: str = Field(..., description="WB token for supplies and returns")
    wb_analytics_token: str = Field(..., description="WB token for analytics and documents")
    wb_content_token: str = Field(..., description="WB token for content, prices, discounts")

    # WB Private Key for JWT signing
    wb_private_key_path: str = Field(
        "/root/sovani_bot/wb_private_key.pem",
        description="Path to WB private key for JWT",
    )

    # === Ozon API ===
    ozon_client_id: str = Field(..., description="Ozon API Client ID")
    ozon_api_key_admin: str = Field(..., description="Ozon API Key (admin scope)")

    # Ozon Performance API (for advertising)
    ozon_perf_client_id: str | None = Field(None, description="Ozon Performance Client ID")
    ozon_perf_client_secret: str | None = Field(None, description="Ozon Performance Client Secret")

    # === OpenAI ===
    openai_api_key: str = Field(..., description="OpenAI API key for ChatGPT")
    openai_model: str = Field("gpt-4o-mini", description="OpenAI model to use")

    # === ChatGPT (legacy compatibility) ===
    chatgpt_api_key: str | None = Field(None, description="Legacy ChatGPT API key")

    # === Database ===
    database_url: str = Field(
        "sqlite:///./sovani_bot.db",
        description="Database URL (SQLite for now, Postgres later)",
    )

    # === Business defaults ===
    default_cost_price: float = Field(600.0, description="Default product cost price in RUB")
    cost_price: float = Field(600.0, description="Product cost price (legacy compatibility)")

    # === Review settings ===
    review_check_hour: int = Field(6, description="Hour to check reviews (0-23)")
    review_check_minute: int = Field(0, description="Minute to check reviews")

    # === Stock settings ===
    wb_min_stock_days: int = Field(14, description="Minimum stock coverage for WB in days")
    ozon_min_stock_days: int = Field(21, description="Minimum stock coverage for Ozon in days")
    ozon_high_stock_days: int = Field(45, description="High stock coverage for Ozon in days")

    # === Application settings ===
    app_timezone: str = Field("Europe/Moscow", description="Application timezone", validation_alias="TZ")
    http_timeout_seconds: int = Field(30, description="HTTP request timeout in seconds")

    # === HTTP/Rate limits (per host) ===
    wb_rate_per_min: int = Field(60, description="WB API rate limit per minute")
    wb_rate_capacity: int = Field(60, description="WB API rate limit capacity")
    ozon_rate_per_min: int = Field(300, description="Ozon API rate limit per minute")
    ozon_rate_capacity: int = Field(300, description="Ozon API rate limit capacity")

    # === Circuit breaker settings ===
    cb_fail_threshold: int = Field(5, description="Circuit breaker failure threshold")
    cb_reset_timeout: float = Field(30.0, description="Circuit breaker reset timeout in seconds")
    http_max_retries: int = Field(3, description="Maximum HTTP retry attempts")
    http_backoff_base: float = Field(0.75, description="HTTP retry backoff base delay")
    http_backoff_max: float = Field(8.0, description="HTTP retry backoff max delay")

    # === Web API & RBAC (Stage 10) ===
    allowed_tg_user_ids: str = Field("", description="Comma-separated admin user IDs")
    readonly_tg_user_ids: str = Field("", description="Comma-separated viewer user IDs")
    tma_origin: str = Field("*", description="TMA origin for CORS")

    # === Monitoring & Alerts (Stage 11) ===
    alert_threshold_disk: int = Field(90, description="Disk usage alert threshold (%)")
    alert_threshold_memory: int = Field(90, description="Memory usage alert threshold (%)")
    alert_threshold_job_failures: int = Field(
        3, description="Consecutive job failures before alert"
    )

    @property
    def effective_chatgpt_key(self) -> str | None:
        """Return ChatGPT API key with fallback to OpenAI key."""
        return self.chatgpt_api_key or self.openai_api_key

    @property
    def admin_user_ids(self) -> set[str]:
        """Get set of admin user IDs."""
        return set(self.allowed_tg_user_ids.split(",")) if self.allowed_tg_user_ids else set()

    @property
    def viewer_user_ids(self) -> set[str]:
        """Get set of viewer user IDs."""
        return set(self.readonly_tg_user_ids.split(",")) if self.readonly_tg_user_ids else set()

    # === Supply Planner (Stage 13) ===
    planner_safety_coeff: float = Field(1.2, description="Safety stock coefficient")
    planner_min_batch: int = Field(5, description="Minimum batch size")
    planner_multiplicity: int = Field(1, description="Order quantity multiplicity")
    planner_max_per_slot: int = Field(500, description="Max quantity per slot")
    warehouse_capacity_json: str = Field("{}", description="Warehouse capacity limits (JSON)")
    cashflow_limit: float = Field(0.0, description="Cash flow budget limit (0=unlimited)")
    planner_solver: str = Field("heuristic", description="Planner algorithm: heuristic or pulp")

    # === Pricing & Promo (Stage 14) ===
    pricing_min_margin_pct: float = Field(0.10, description="Minimum profit margin")
    pricing_max_discount_pct: float = Field(0.30, description="Maximum allowed discount")
    pricing_min_price_step: int = Field(10, description="Minimum price change step (rubles)")
    pricing_map_json: str = Field("{}", description="Minimum advertised price by SKU (JSON)")
    promo_min_window_days: int = Field(7, description="Minimum promo comparison window")
    promo_max_window_days: int = Field(28, description="Maximum promo comparison window")
    pricing_explain_service_level: float = Field(0.88, description="Service level for explanations")

    # === BI Export (Stage 15) ===
    bi_export_max_rows: int = Field(100000, description="Maximum rows per BI export")
    bi_export_default_limit: int = Field(5000, description="Default limit for BI exports")
    bi_readonly_db_user: str = Field("bi_reader", description="Read-only DB user for BI tools")

    # === Cashflow & PnL Pro (Stage 16) ===
    cf_default_settlement_lag_days: int = Field(7, description="Payment lag from MP to seller")
    cf_negative_balance_alert_threshold: int = Field(
        -10000, description="Alert threshold for negative cash balance"
    )
    pnl_cost_fallback_strategy: str = Field(
        "latest", description="Cost strategy: latest or moving_avg_28"
    )
    pnl_refunds_recognition: str = Field("post_event", description="Refund recognition method")
    scenario_max_lookahead_days: int = Field(28, description="Max what-if scenario horizon")
    scenario_price_step: int = Field(10, description="Price step for simulations")
    scenario_supply_leadtime_days: int = Field(5, description="Average supply lead time")

    # === Alerts & Playbooks (Stage 17) ===
    alert_chat_ids: str = Field("", description="Comma-separated Telegram chat IDs for alerts")
    alert_dedup_window_sec: int = Field(300, description="Alert deduplication window (seconds)")
    alert_min_severity: str = Field("warning", description="Min severity: warning|error|critical")
    slo_api_latency_p95_ms: int = Field(1200, description="SLO: API p95 latency (ms)")
    slo_ingest_success_rate_pct: float = Field(99.0, description="SLO: Ingest success rate (%)")
    slo_scheduler_on_time_pct: float = Field(98.0, description="SLO: Scheduler on-time (%)")
    auto_remediation_enabled: bool = Field(True, description="Enable auto-remediation")
    auto_remediation_max_retries: int = Field(3, description="Max remediation retries")

    # === Reviews SLA (Stage 18) ===
    sla_first_reply_hours: int = Field(24, description="SLA target: first reply within N hours")
    sla_escalate_after_hours: int = Field(12, description="Escalate after N hours without reply")
    sla_notify_chat_ids: str = Field("", description="Comma-separated chat IDs for SLA escalations")
    sla_backlog_limit: int = Field(200, description="Maximum reviews in backlog check")
    sla_batch_size: int = Field(30, description="Reviews per escalation message batch")

    # === Multi-Tenant SaaS (Stage 19) ===
    dev_mode: bool = Field(False, description="Enable development mode (DEV impersonation endpoints)")
    default_org_name: str = Field(
        "SoVAni Default", description="Default organization name for new users"
    )
    tenant_enforcement_enabled: bool = Field(
        True, description="Enforce org_id scoping on all queries"
    )
    org_export_default_limit: int = Field(5000, description="Default row limit for exports per org")
    org_export_max_rows: int = Field(100000, description="Maximum export rows per org")
    org_rate_limit_rps: int = Field(10, description="Max requests per second per organization")
    org_max_jobs_enqueued: int = Field(50, description="Max concurrent jobs per organization")
    org_tokens_encryption_key: str = Field(
        "", description="Base64 encryption key for MP credentials"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Raises:
        RuntimeError: If required environment variables are missing.

    """
    try:
        return Settings()
    except ValidationError as e:
        missing_fields = []
        for error in e.errors():
            if error["type"] == "missing":
                field_name = error["loc"][0]
                missing_fields.append(field_name.upper())

        error_msg = (
            f"Configuration error: Missing required environment variables: "
            f"{', '.join(missing_fields)}\n"
            f"Please set them in .env file or export as environment variables.\n"
            f"See .env.example for reference."
        )
        raise RuntimeError(error_msg) from e


# === Legacy compatibility shim ===
# This allows old code to use `from app.core.config import config`
# and access config.TELEGRAM_TOKEN, etc.
class _LegacyConfigShim:
    """Legacy config shim for backward compatibility.

    Provides attribute-style access to settings for legacy code.
    Will be removed in Stage 6 (restructuring).
    """

    def __init__(self):
        self._settings = None

    def _get_settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    # Telegram
    @property
    def TELEGRAM_TOKEN(self) -> str:
        return self._get_settings().telegram_token

    @property
    def MANAGER_CHAT_ID(self) -> int:
        return self._get_settings().manager_chat_id

    # Wildberries
    @property
    def WB_FEEDBACKS_TOKEN(self) -> str:
        return self._get_settings().wb_feedbacks_token

    @property
    def WB_ADS_TOKEN(self) -> str:
        return self._get_settings().wb_ads_token

    @property
    def WB_STATS_TOKEN(self) -> str:
        return self._get_settings().wb_stats_token

    @property
    def WB_SUPPLY_TOKEN(self) -> str:
        return self._get_settings().wb_supply_token

    @property
    def WB_ANALYTICS_TOKEN(self) -> str:
        return self._get_settings().wb_analytics_token

    @property
    def WB_CONTENT_TOKEN(self) -> str:
        return self._get_settings().wb_content_token

    @property
    def WB_PRIVATE_KEY_PATH(self) -> str:
        return self._get_settings().wb_private_key_path

    # Legacy compatibility
    @property
    def WB_API_TOKEN(self) -> str:
        """Legacy: defaults to feedbacks token."""
        return self._get_settings().wb_feedbacks_token

    @property
    def WB_REPORTS_TOKEN(self) -> str:
        """Legacy: defaults to stats token."""
        return self._get_settings().wb_stats_token

    # Ozon
    @property
    def OZON_CLIENT_ID(self) -> str:
        return self._get_settings().ozon_client_id

    @property
    def OZON_API_KEY_ADMIN(self) -> str:
        return self._get_settings().ozon_api_key_admin

    @property
    def OZON_API_KEY(self) -> str:
        """Legacy: defaults to admin key."""
        return self._get_settings().ozon_api_key_admin

    @property
    def OZON_PERF_CLIENT_ID(self) -> str | None:
        return self._get_settings().ozon_perf_client_id

    @property
    def OZON_PERF_CLIENT_SECRET(self) -> str | None:
        return self._get_settings().ozon_perf_client_secret

    # OpenAI
    @property
    def OPENAI_API_KEY(self) -> str:
        return self._get_settings().openai_api_key

    @property
    def OPENAI_MODEL(self) -> str:
        return self._get_settings().openai_model

    @property
    def CHATGPT_API_KEY(self) -> str | None:
        return self._get_settings().effective_chatgpt_key

    # Database
    @property
    def DATABASE_URL(self) -> str:
        return self._get_settings().database_url

    # Business
    @property
    def COST_PRICE(self) -> float:
        return self._get_settings().cost_price

    @property
    def DEFAULT_COST_PRICE(self) -> float:
        return self._get_settings().default_cost_price

    # Reviews
    @property
    def REVIEW_CHECK_HOUR(self) -> int:
        return self._get_settings().review_check_hour

    @property
    def REVIEW_CHECK_MINUTE(self) -> int:
        return self._get_settings().review_check_minute

    # Stock
    @property
    def WB_MIN_STOCK_DAYS(self) -> int:
        return self._get_settings().wb_min_stock_days

    @property
    def OZON_MIN_STOCK_DAYS(self) -> int:
        return self._get_settings().ozon_min_stock_days

    @property
    def OZON_HIGH_STOCK_DAYS(self) -> int:
        return self._get_settings().ozon_high_stock_days

    # App
    @property
    def APP_TIMEZONE(self) -> str:
        return self._get_settings().app_timezone

    @property
    def HTTP_TIMEOUT_SECONDS(self) -> int:
        return self._get_settings().http_timeout_seconds


# Create singleton instance for legacy imports
# DEPRECATED: Stage 6+ code should use get_settings() instead
# Legacy shim kept for backward compatibility with root-level scripts
config = _LegacyConfigShim()

# For compatibility with old code patterns
# DEPRECATED: Stage 6+ code should use get_settings() instead
Config = _LegacyConfigShim


__all__ = ["Settings", "get_settings", "config", "Config"]
