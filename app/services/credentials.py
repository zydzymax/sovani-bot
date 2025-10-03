"""Credentials encryption service (Stage 19)."""

from __future__ import annotations

import base64
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_cipher() -> Fernet | None:
    """Get Fernet cipher if encryption key is configured.

    Returns:
        Fernet cipher or None if encryption disabled

    """
    settings = get_settings()
    key = settings.org_tokens_encryption_key

    if not key:
        return None

    try:
        # Key should be base64-encoded 32-byte key
        key_bytes = base64.urlsafe_b64decode(key.encode())
        return Fernet(key_bytes)
    except Exception as e:
        logger.error(f"Failed to initialize Fernet cipher: {e}")
        return None


def encrypt_token(plaintext: str | None) -> str | None:
    """Encrypt a token if encryption is enabled.

    Args:
        plaintext: Token to encrypt

    Returns:
        Encrypted token (base64) or plaintext if encryption disabled

    """
    if not plaintext:
        return plaintext

    cipher = _get_cipher()
    if not cipher:
        logger.warning("Encryption key not configured, storing token in plaintext")
        return plaintext

    try:
        encrypted_bytes = cipher.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted_bytes).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        return plaintext


def decrypt_token(ciphertext: str | None) -> str | None:
    """Decrypt a token if encryption is enabled.

    Args:
        ciphertext: Encrypted token (base64)

    Returns:
        Decrypted token or ciphertext if encryption disabled/fails

    """
    if not ciphertext:
        return ciphertext

    cipher = _get_cipher()
    if not cipher:
        # No encryption key configured, assume plaintext
        return ciphertext

    try:
        # Try to decrypt (assume it's encrypted)
        encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode())
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()
    except (InvalidToken, Exception):
        # If decryption fails, assume it's plaintext (backward compatibility)
        logger.debug("Token appears to be plaintext (decryption failed), returning as-is")
        return ciphertext


def encrypt_credentials(creds: dict[str, Any]) -> dict[str, Any]:
    """Encrypt all sensitive fields in credentials dict.

    Args:
        creds: Credentials dict with token fields

    Returns:
        Dict with encrypted tokens

    """
    sensitive_fields = [
        "wb_feedbacks_token",
        "wb_stats_token",
        "wb_adv_token",
        "ozon_api_key",
        "ozon_client_id",
    ]

    encrypted = creds.copy()
    for field in sensitive_fields:
        if encrypted.get(field):
            encrypted[field] = encrypt_token(encrypted[field])

    return encrypted


def decrypt_credentials(creds: dict[str, Any]) -> dict[str, Any]:
    """Decrypt all sensitive fields in credentials dict.

    Args:
        creds: Credentials dict with encrypted token fields

    Returns:
        Dict with decrypted tokens

    """
    sensitive_fields = [
        "wb_feedbacks_token",
        "wb_stats_token",
        "wb_adv_token",
        "ozon_api_key",
        "ozon_client_id",
    ]

    decrypted = creds.copy()
    for field in sensitive_fields:
        if decrypted.get(field):
            decrypted[field] = decrypt_token(decrypted[field])

    return decrypted
