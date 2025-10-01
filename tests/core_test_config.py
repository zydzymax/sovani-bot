"""Tests for configuration management."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_settings_loads_from_env(monkeypatch):
    """Test that settings load correctly from environment variables."""
    # Set all required environment variables
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("MANAGER_CHAT_ID", "123456")
    monkeypatch.setenv("WB_FEEDBACKS_TOKEN", "wbX")
    monkeypatch.setenv("WB_ADS_TOKEN", "wbX")
    monkeypatch.setenv("WB_STATS_TOKEN", "wbX")
    monkeypatch.setenv("WB_SUPPLY_TOKEN", "wbX")
    monkeypatch.setenv("WB_ANALYTICS_TOKEN", "wbX")
    monkeypatch.setenv("WB_CONTENT_TOKEN", "wbX")
    monkeypatch.setenv("OZON_CLIENT_ID", "ozon-client")
    monkeypatch.setenv("OZON_API_KEY_ADMIN", "ozon-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

    # Clear cache to force reload
    get_settings.cache_clear()

    s = Settings()
    assert s.telegram_token == "123:abc"
    assert s.manager_chat_id == 123456
    assert s.database_url.startswith("sqlite:///")
    assert s.openai_model == "gpt-4o-mini"  # default
    assert s.cost_price == 600.0  # default


def test_settings_missing_required_fields(monkeypatch):
    """Test that missing required fields raise validation error."""
    # Only set some required fields
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.delenv("MANAGER_CHAT_ID", raising=False)
    monkeypatch.delenv("WB_FEEDBACKS_TOKEN", raising=False)

    # Clear cache
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    # Should have multiple missing fields
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any(err["type"] == "missing" for err in errors)


def test_settings_defaults(monkeypatch):
    """Test that optional fields have correct defaults."""
    # Set all required fields
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("MANAGER_CHAT_ID", "0")
    monkeypatch.setenv("WB_FEEDBACKS_TOKEN", "wbX")
    monkeypatch.setenv("WB_ADS_TOKEN", "wbX")
    monkeypatch.setenv("WB_STATS_TOKEN", "wbX")
    monkeypatch.setenv("WB_SUPPLY_TOKEN", "wbX")
    monkeypatch.setenv("WB_ANALYTICS_TOKEN", "wbX")
    monkeypatch.setenv("WB_CONTENT_TOKEN", "wbX")
    monkeypatch.setenv("OZON_CLIENT_ID", "ozon-client")
    monkeypatch.setenv("OZON_API_KEY_ADMIN", "ozon-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")

    get_settings.cache_clear()

    s = Settings()
    assert s.openai_model == "gpt-4o-mini"
    assert s.cost_price == 600.0
    assert s.review_check_hour == 6
    assert s.review_check_minute == 0
    assert s.wb_min_stock_days == 14
    assert s.ozon_min_stock_days == 21
    assert s.app_timezone == "Europe/Moscow"
    assert s.http_timeout_seconds == 30


def test_settings_type_conversion(monkeypatch):
    """Test that string env vars are converted to correct types."""
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("MANAGER_CHAT_ID", "999888")  # String
    monkeypatch.setenv("COST_PRICE", "750.5")  # String
    monkeypatch.setenv("WB_MIN_STOCK_DAYS", "21")  # String
    monkeypatch.setenv("WB_FEEDBACKS_TOKEN", "wbX")
    monkeypatch.setenv("WB_ADS_TOKEN", "wbX")
    monkeypatch.setenv("WB_STATS_TOKEN", "wbX")
    monkeypatch.setenv("WB_SUPPLY_TOKEN", "wbX")
    monkeypatch.setenv("WB_ANALYTICS_TOKEN", "wbX")
    monkeypatch.setenv("WB_CONTENT_TOKEN", "wbX")
    monkeypatch.setenv("OZON_CLIENT_ID", "ozon-client")
    monkeypatch.setenv("OZON_API_KEY_ADMIN", "ozon-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")

    get_settings.cache_clear()

    s = Settings()
    assert isinstance(s.manager_chat_id, int)
    assert s.manager_chat_id == 999888
    assert isinstance(s.cost_price, float)
    assert s.cost_price == 750.5
    assert isinstance(s.wb_min_stock_days, int)
    assert s.wb_min_stock_days == 21


def test_effective_chatgpt_key_fallback(monkeypatch):
    """Test that effective_chatgpt_key falls back to openai_api_key."""
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("MANAGER_CHAT_ID", "0")
    monkeypatch.setenv("WB_FEEDBACKS_TOKEN", "wbX")
    monkeypatch.setenv("WB_ADS_TOKEN", "wbX")
    monkeypatch.setenv("WB_STATS_TOKEN", "wbX")
    monkeypatch.setenv("WB_SUPPLY_TOKEN", "wbX")
    monkeypatch.setenv("WB_ANALYTICS_TOKEN", "wbX")
    monkeypatch.setenv("WB_CONTENT_TOKEN", "wbX")
    monkeypatch.setenv("OZON_CLIENT_ID", "ozon-client")
    monkeypatch.setenv("OZON_API_KEY_ADMIN", "ozon-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-key")
    monkeypatch.delenv("CHATGPT_API_KEY", raising=False)

    get_settings.cache_clear()

    s = Settings()
    assert s.effective_chatgpt_key == "sk-openai-key"

    # Now set CHATGPT_API_KEY explicitly
    monkeypatch.setenv("CHATGPT_API_KEY", "sk-chatgpt-key")
    get_settings.cache_clear()

    s2 = Settings()
    assert s2.effective_chatgpt_key == "sk-chatgpt-key"


def test_get_settings_caching():
    """Test that get_settings returns cached instance."""
    # This test assumes environment is already set up
    try:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2  # Same instance due to @lru_cache
    except RuntimeError:
        # If env vars not set, skip this test
        pytest.skip("Environment variables not set")


def test_legacy_shim_compatibility(monkeypatch):
    """Test that legacy config shim works."""
    from app.core.config import config

    # Set required env vars
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("MANAGER_CHAT_ID", "123456")
    monkeypatch.setenv("WB_FEEDBACKS_TOKEN", "wbX")
    monkeypatch.setenv("WB_ADS_TOKEN", "wbX")
    monkeypatch.setenv("WB_STATS_TOKEN", "wbX")
    monkeypatch.setenv("WB_SUPPLY_TOKEN", "wbX")
    monkeypatch.setenv("WB_ANALYTICS_TOKEN", "wbX")
    monkeypatch.setenv("WB_CONTENT_TOKEN", "wbX")
    monkeypatch.setenv("OZON_CLIENT_ID", "ozon-client")
    monkeypatch.setenv("OZON_API_KEY_ADMIN", "ozon-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")

    get_settings.cache_clear()

    # Test legacy attribute access
    assert config.TELEGRAM_TOKEN == "123:abc"
    assert config.MANAGER_CHAT_ID == 123456
    assert config.WB_FEEDBACKS_TOKEN == "wbX"
    assert config.OZON_CLIENT_ID == "ozon-client"
    assert config.OPENAI_API_KEY == "sk-xxx"
