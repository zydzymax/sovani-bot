"""Tests for Telegram WebApp authentication."""

from __future__ import annotations

import hashlib
import hmac
import urllib.parse

import pytest

from app.web.auth import validate_init_data


def generate_valid_init_data(bot_token: str, user_id: str = "123456") -> str:
    """Generate valid initData for testing."""
    # Create data dict
    data = {
        "auth_date": "1234567890",
        "user": f'{{"id":{user_id},"username":"testuser"}}',
        "query_id": "test_query_id",
    }

    # Sort and create check string
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    # Generate hash
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_value = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    # Add hash to data
    data["hash"] = hash_value

    # Return as query string
    return urllib.parse.urlencode(data)


def test_validate_init_data_success(monkeypatch):
    """Test successful initData validation."""
    bot_token = "test_bot_token_123"

    # Mock settings
    class MockSettings:
        telegram_token = bot_token

    monkeypatch.setattr("app.web.auth.get_settings", lambda: MockSettings())

    init_data = generate_valid_init_data(bot_token)
    result = validate_init_data(init_data)

    assert "user" in result
    assert "auth_date" in result
    assert "query_id" in result


def test_validate_init_data_missing_hash():
    """Test validation fails when hash is missing."""
    init_data = "auth_date=1234567890&user=%7B%7D"

    with pytest.raises(ValueError, match="Missing hash"):
        validate_init_data(init_data)


def test_validate_init_data_invalid_hash(monkeypatch):
    """Test validation fails with invalid signature."""
    bot_token = "test_bot_token_123"

    class MockSettings:
        telegram_token = bot_token

    monkeypatch.setattr("app.web.auth.get_settings", lambda: MockSettings())

    # Create init_data with wrong hash
    init_data = "auth_date=1234567890&user=%7B%7D&hash=invalid_hash_12345"

    with pytest.raises(ValueError, match="Invalid initData signature"):
        validate_init_data(init_data)


def test_validate_init_data_tampered_data(monkeypatch):
    """Test validation fails when data is tampered."""
    bot_token = "test_bot_token_123"

    class MockSettings:
        telegram_token = bot_token

    monkeypatch.setattr("app.web.auth.get_settings", lambda: MockSettings())

    # Generate valid init_data
    init_data = generate_valid_init_data(bot_token, user_id="123456")

    # Tamper with user_id
    init_data = init_data.replace("123456", "999999")

    with pytest.raises(ValueError, match="Invalid initData signature"):
        validate_init_data(init_data)
