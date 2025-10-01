"""Tests for structured JSON logging."""

import json
import logging

from app.core.logging import JsonFormatter, get_request_id, set_request_id


def test_masking_tokens_in_message():
    """Test that tokens are masked in log messages."""
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token sk-abcDEF1234567890 and telegram 1234567890:AAAbbbCCCdddEEEfffGGGhhh",
        args=(),
        exc_info=None,
    )
    line = JsonFormatter().format(rec)
    payload = json.loads(line)

    # Check that tokens are masked
    assert "sk-***" in payload["msg"]
    assert "***:***" in payload["msg"]
    assert "1234567890:AAAbbbCCCdddEEEfffGGGhhh" not in payload["msg"]


def test_masking_jwt_tokens():
    """Test that JWT tokens are masked."""
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="WB token eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjQwOTI0djEiLCJ0eXAiOiJKV1QifQ",
        args=(),
        exc_info=None,
    )
    line = JsonFormatter().format(rec)
    payload = json.loads(line)

    # Check that JWT tokens are masked
    assert "eyJ***" in payload["msg"]
    assert "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjQwOTI0djEiLCJ0eXAiOiJKV1QifQ" not in payload["msg"]


def test_masking_in_extra_headers():
    """Test that sensitive data in extra fields is masked."""
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="http",
        args=(),
        exc_info=None,
    )
    rec.__dict__["headers"] = {"Authorization": "Bearer verysecrettoken123"}
    line = JsonFormatter().format(rec)
    payload = json.loads(line)

    # Authorization header should be masked (key is lowercased in masking)
    assert payload["extra"]["headers"]["Authorization"] == "***"


def test_masking_sensitive_keys():
    """Test that sensitive keys are masked regardless of value."""
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="config",
        args=(),
        exc_info=None,
    )
    rec.__dict__["config"] = {
        "token": "abc123",
        "api_key": "xyz789",
        "username": "john_doe",  # Not sensitive
        "openai_api_key": "sk-real-key",
    }
    line = JsonFormatter().format(rec)
    payload = json.loads(line)

    # Sensitive keys should be masked
    assert payload["extra"]["config"]["token"] == "***"
    assert payload["extra"]["config"]["api_key"] == "***"
    assert payload["extra"]["config"]["openai_api_key"] == "***"

    # Non-sensitive keys should not be masked
    assert payload["extra"]["config"]["username"] == "john_doe"


def test_request_id_tracking():
    """Test request ID context tracking."""
    # Initially empty
    rid1 = get_request_id()
    assert rid1 == ""

    # Set request ID
    test_id = "test-request-123"
    result = set_request_id(test_id)
    assert result == test_id

    # Should retrieve same ID
    rid2 = get_request_id()
    assert rid2 == test_id

    # Generate new UUID
    rid3 = set_request_id()
    assert rid3 != ""
    assert rid3 != test_id
    assert len(rid3) == 36  # UUID length


def test_request_id_in_log_record():
    """Test that request_id appears in log output."""
    test_id = "req-456"
    set_request_id(test_id)

    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    line = JsonFormatter().format(rec)
    payload = json.loads(line)

    assert payload["request_id"] == test_id


def test_json_formatter_structure():
    """Test that JSON formatter produces correct structure."""
    rec = logging.LogRecord(
        name="test.module",
        level=logging.WARNING,
        pathname="/path/to/file.py",
        lineno=42,
        msg="test message",
        args=(),
        exc_info=None,
        func="test_func",
    )
    rec.module = "test_module"

    line = JsonFormatter().format(rec)
    payload = json.loads(line)

    # Check required fields
    assert "ts" in payload
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "test.module"
    assert payload["msg"] == "test message"
    assert payload["module"] == "test_module"
    assert payload["func"] == "test_func"
    assert payload["line"] == 42


def test_exception_info_in_log():
    """Test that exception info is included in log."""
    import sys

    try:
        raise ValueError("test error")
    except ValueError:
        exc_info = sys.exc_info()
        rec = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        line = JsonFormatter().format(rec)
        payload = json.loads(line)

        assert "exc_info" in payload
        assert "ValueError: test error" in payload["exc_info"]


def test_masking_preserves_numbers():
    """Test that numbers are not accidentally masked."""
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Processing 12345 items with value 999.99",
        args=(),
        exc_info=None,
    )
    rec.__dict__["count"] = 12345
    rec.__dict__["value"] = 999.99

    line = JsonFormatter().format(rec)
    payload = json.loads(line)

    # Numbers in message should be preserved
    assert "12345" in payload["msg"]
    assert "999.99" in payload["msg"]

    # Numbers in extra should be preserved
    assert payload["extra"]["count"] == 12345
    assert payload["extra"]["value"] == 999.99
