"""Tests for credentials encryption service (Stage 19 Hardening)."""

from __future__ import annotations

import base64
from unittest.mock import patch

from cryptography.fernet import Fernet

from app.services.credentials import (
    decrypt_credentials,
    decrypt_token,
    encrypt_credentials,
    encrypt_token,
)


def test_encrypt_token_with_key() -> None:
    """Test token encryption when key is configured."""
    # Generate a real Fernet key
    key = Fernet.generate_key()
    key_b64 = base64.urlsafe_b64encode(key).decode()

    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = key_b64

        plaintext = "secret_token_12345"
        encrypted = encrypt_token(plaintext)

        assert encrypted is not None
        assert encrypted != plaintext
        assert len(encrypted) > len(plaintext)


def test_decrypt_token_with_key() -> None:
    """Test token decryption when key is configured."""
    key = Fernet.generate_key()
    key_b64 = base64.urlsafe_b64encode(key).decode()

    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = key_b64

        plaintext = "secret_token_67890"
        encrypted = encrypt_token(plaintext)
        decrypted = decrypt_token(encrypted)

        assert decrypted == plaintext


def test_encrypt_token_without_key() -> None:
    """Test token encryption when no key is configured (plaintext fallback)."""
    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = ""

        plaintext = "token_no_encryption"
        encrypted = encrypt_token(plaintext)

        assert encrypted == plaintext  # No encryption, passthrough


def test_decrypt_token_without_key() -> None:
    """Test token decryption when no key is configured (plaintext fallback)."""
    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = ""

        plaintext = "token_plaintext"
        decrypted = decrypt_token(plaintext)

        assert decrypted == plaintext  # No decryption, passthrough


def test_encrypt_token_handles_none() -> None:
    """Test encrypt_token handles None input."""
    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = ""

        result = encrypt_token(None)
        assert result is None


def test_decrypt_token_handles_none() -> None:
    """Test decrypt_token handles None input."""
    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = ""

        result = decrypt_token(None)
        assert result is None


def test_encrypt_credentials_encrypts_sensitive_fields() -> None:
    """Test encrypt_credentials encrypts all sensitive fields."""
    key = Fernet.generate_key()
    key_b64 = base64.urlsafe_b64encode(key).decode()

    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = key_b64

        creds = {
            "wb_feedbacks_token": "wb_secret_123",
            "ozon_api_key": "ozon_secret_456",
            "other_field": "not_encrypted",
        }

        encrypted = encrypt_credentials(creds)

        # Sensitive fields should be encrypted
        assert encrypted["wb_feedbacks_token"] != "wb_secret_123"
        assert encrypted["ozon_api_key"] != "ozon_secret_456"

        # Non-sensitive field unchanged
        assert encrypted["other_field"] == "not_encrypted"


def test_decrypt_credentials_decrypts_sensitive_fields() -> None:
    """Test decrypt_credentials decrypts all sensitive fields."""
    key = Fernet.generate_key()
    key_b64 = base64.urlsafe_b64encode(key).decode()

    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = key_b64

        creds = {
            "wb_feedbacks_token": "wb_original",
            "ozon_api_key": "ozon_original",
        }

        encrypted = encrypt_credentials(creds)
        decrypted = decrypt_credentials(encrypted)

        assert decrypted["wb_feedbacks_token"] == "wb_original"
        assert decrypted["ozon_api_key"] == "ozon_original"


def test_encrypt_decrypt_round_trip() -> None:
    """Test full encryption → decryption round trip."""
    key = Fernet.generate_key()
    key_b64 = base64.urlsafe_b64encode(key).decode()

    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = key_b64

        original = {
            "wb_feedbacks_token": "test_wb_token",
            "wb_stats_token": "test_stats_token",
            "ozon_client_id": "test_client_id",
            "ozon_api_key": "test_api_key",
        }

        encrypted = encrypt_credentials(original)
        decrypted = decrypt_credentials(encrypted)

        assert decrypted == original


def test_decrypt_handles_plaintext_backward_compat() -> None:
    """Test decrypt_token handles plaintext (backward compatibility)."""
    # When decryption fails (plaintext stored before encryption was enabled),
    # it should return the value as-is
    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = ""

        plaintext = "old_plaintext_token"
        decrypted = decrypt_token(plaintext)

        assert decrypted == plaintext


def test_encrypt_credentials_preserves_structure() -> None:
    """Test encrypt_credentials preserves dict structure."""
    key = Fernet.generate_key()
    key_b64 = base64.urlsafe_b64encode(key).decode()

    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = key_b64

        creds = {
            "wb_feedbacks_token": "token1",
            "wb_ads_token": None,
            "ozon_api_key": "token2",
            "extra_field": "value",
        }

        encrypted = encrypt_credentials(creds)

        # All keys preserved
        assert set(encrypted.keys()) == set(creds.keys())

        # None values preserved
        assert encrypted["wb_ads_token"] is None


def test_decrypt_credentials_handles_empty_dict() -> None:
    """Test decrypt_credentials handles empty credentials dict."""
    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = ""

        result = decrypt_credentials({})
        assert result == {}


def test_encrypt_token_invalid_key_fallback() -> None:
    """Test encrypt_token falls back to plaintext on invalid key."""
    with patch("app.services.credentials.get_settings") as mock_settings:
        mock_settings.return_value.org_tokens_encryption_key = "invalid_key_format"

        plaintext = "test_token"
        encrypted = encrypt_token(plaintext)

        # Should fall back to plaintext on error
        assert encrypted == plaintext
