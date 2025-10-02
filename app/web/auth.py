"""Telegram WebApp authentication.

Validates initData signature using HMAC-SHA256 with bot token.
See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import urllib.parse

from app.core.config import get_settings


def validate_init_data(init_data: str) -> dict[str, str]:
    """Validate Telegram WebApp initData signature.

    Args:
        init_data: Raw initData string from Telegram WebApp

    Returns:
        Dict with parsed fields (user, auth_date, etc.)

    Raises:
        ValueError: If signature is invalid

    """
    settings = get_settings()

    # Parse query string
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    data = {k: v for k, v in pairs}

    # Extract hash
    received_hash = data.pop("hash", "")
    if not received_hash:
        raise ValueError("Missing hash in initData")

    # Build check string (sorted key=value pairs)
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    # Generate secret key from bot token
    secret_key = hashlib.sha256(settings.telegram_token.encode()).digest()

    # Calculate expected hash
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    # Constant-time comparison
    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Invalid initData signature")

    return data
