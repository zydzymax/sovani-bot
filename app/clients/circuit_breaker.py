"""Simple circuit breaker pattern implementation.

Provides circuit breaker to prevent cascading failures in distributed systems.
"""

from __future__ import annotations

import time


class CircuitBreaker:
    """Very simple CB: open after N failures, half-open after timeout."""

    def __init__(self, fail_threshold: int = 5, reset_timeout: float = 30.0):
        """Initialize circuit breaker.

        Args:
            fail_threshold: Number of failures before opening circuit
            reset_timeout: Seconds to wait before attempting half-open state

        """
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.fail_count = 0
        self.state = "closed"  # closed|open|half-open
        self.opened_at = 0.0

    def on_success(self) -> None:
        """Record successful operation, reset failure count."""
        self.fail_count = 0
        self.state = "closed"

    def on_failure(self) -> None:
        """Record failed operation, possibly open circuit."""
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold and self.state != "open":
            self.state = "open"
            self.opened_at = time.monotonic()

    def allow(self) -> bool:
        """Check if request is allowed through circuit breaker.

        Returns:
            True if request allowed, False if circuit is open

        """
        if self.state == "closed":
            return True

        if self.state == "open":
            if time.monotonic() - self.opened_at >= self.reset_timeout:
                self.state = "half-open"
                return True
            return False

        # half-open - allow attempt
        return True


__all__ = ["CircuitBreaker"]
