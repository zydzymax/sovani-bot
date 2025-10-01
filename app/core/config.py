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
    app_timezone: str = Field("Europe/Moscow", description="Application timezone")
    http_timeout_seconds: int = Field(30, description="HTTP request timeout in seconds")

    @property
    def effective_chatgpt_key(self) -> str | None:
        """Return ChatGPT API key with fallback to OpenAI key."""
        return self.chatgpt_api_key or self.openai_api_key


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
config = _LegacyConfigShim()

# For compatibility with old code patterns
Config = _LegacyConfigShim


__all__ = ["Settings", "get_settings", "config", "Config"]
