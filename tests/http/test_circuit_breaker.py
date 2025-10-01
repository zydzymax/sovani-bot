"""Tests for circuit breaker."""

import time

from app.clients.circuit_breaker import CircuitBreaker


def test_cb_open_and_half_open():
    """Test circuit breaker opens after failures and transitions to half-open."""
    cb = CircuitBreaker(fail_threshold=2, reset_timeout=0.05)

    # Initial state: closed
    assert cb.allow()
    assert cb.state == "closed"

    # Trigger failures
    cb.on_failure()
    cb.on_failure()

    # Should be open now
    assert not cb.allow()
    assert cb.state == "open"

    # Wait for reset timeout
    time.sleep(0.06)

    # Should transition to half-open
    assert cb.allow()
    assert cb.state == "half-open"

    # Success should close circuit
    cb.on_success()
    assert cb.allow()
    assert cb.state == "closed"


def test_cb_remains_closed_on_success():
    """Test circuit breaker stays closed with successes."""
    cb = CircuitBreaker(fail_threshold=3, reset_timeout=1.0)

    for _ in range(10):
        cb.on_success()
        assert cb.state == "closed"
        assert cb.allow()


def test_cb_counts_failures():
    """Test circuit breaker counts failures correctly."""
    cb = CircuitBreaker(fail_threshold=5, reset_timeout=1.0)

    # Not enough failures yet
    for i in range(4):
        cb.on_failure()
        assert cb.allow()
        assert cb.fail_count == i + 1

    # 5th failure should open
    cb.on_failure()
    assert not cb.allow()
    assert cb.state == "open"


def test_cb_success_resets_failures():
    """Test that success resets failure count."""
    cb = CircuitBreaker(fail_threshold=3, reset_timeout=1.0)

    cb.on_failure()
    cb.on_failure()
    assert cb.fail_count == 2

    cb.on_success()
    assert cb.fail_count == 0
    assert cb.state == "closed"
