"""Prometheus metrics for monitoring."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Summary

# HTTP Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests in progress",
    ["method", "endpoint"],
)

# Scheduler Job metrics
scheduler_jobs_total = Counter(
    "scheduler_jobs_total",
    "Total scheduled jobs executed",
    ["job_name", "status"],  # status: success, failed
)

scheduler_job_duration_seconds = Summary(
    "scheduler_job_duration_seconds",
    "Scheduler job execution duration",
    ["job_name"],
)

scheduler_jobs_in_progress = Gauge(
    "scheduler_jobs_in_progress",
    "Number of scheduled jobs currently running",
)

# Database metrics
db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# External API metrics
external_api_requests_total = Counter(
    "external_api_requests_total",
    "Total external API requests",
    ["service", "endpoint", "status"],  # service: wb, ozon, openai
)

external_api_duration_seconds = Histogram(
    "external_api_duration_seconds",
    "External API request duration",
    ["service", "endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# Business metrics
reviews_processed_total = Counter(
    "reviews_processed_total",
    "Total reviews processed",
    ["marketplace", "status"],  # status: template, custom_ai
)

reviews_classified_total = Counter(
    "reviews_classified_total",
    "Total reviews classified by type",
    ["marketplace", "classification"],  # classification: typical_positive, typical_negative, typical_neutral, atypical
)

advice_generated_total = Counter(
    "advice_generated_total",
    "Total supply advice generated",
    ["marketplace"],
)

# System metrics
app_uptime_seconds = Gauge(
    "app_uptime_seconds",
    "Application uptime in seconds",
)

app_info = Gauge(
    "app_info",
    "Application info",
    ["version", "environment"],
)

# Error metrics
errors_total = Counter(
    "errors_total",
    "Total errors by type",
    ["error_type", "component"],
)
