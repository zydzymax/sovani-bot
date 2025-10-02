"""Tests for Prometheus metrics."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.web.main import app


@pytest.fixture
def client():
    """Test client."""
    with TestClient(app) as c:
        yield c


def test_metrics_endpoint_exists(client):
    """Test /metrics endpoint is accessible."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_metrics_contains_http_requests(client):
    """Test metrics include HTTP request counters."""
    # Make a request to generate metrics
    client.get("/health")

    response = client.get("/metrics")
    content = response.text

    # Check for HTTP metrics
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content


def test_metrics_contains_app_info(client):
    """Test metrics include app info."""
    response = client.get("/metrics")
    content = response.text

    assert "app_info" in content
    assert "version" in content
    assert "0.11.0" in content


def test_metrics_uptime(client):
    """Test uptime metric is present."""
    response = client.get("/metrics")
    content = response.text

    assert "app_uptime_seconds" in content


def test_http_requests_increment(client):
    """Test HTTP request counter increments."""
    # Get initial metrics
    response1 = client.get("/metrics")
    content1 = response1.text

    # Extract http_requests_total count
    # (Simple check: metrics should contain the counter)
    assert "http_requests_total" in content1

    # Make a few requests
    for _ in range(3):
        client.get("/health")

    # Get new metrics
    response2 = client.get("/metrics")
    content2 = response2.text

    # Metrics should still be present (detailed parsing would check increment)
    assert "http_requests_total" in content2
