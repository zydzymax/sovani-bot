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
    [
        "marketplace",
        "classification",
    ],  # classification: typical_positive, typical_negative, typical_neutral, atypical
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

# === Stage 17: Operational Alerts & Playbooks ===

# Alert metrics
alerts_total = Counter(
    "alerts_total",
    "Total operational alerts sent",
    ["source", "severity"],  # severity: warning, error, critical
)

alerts_deduplicated_total = Counter(
    "alerts_deduplicated_total",
    "Total alerts suppressed by deduplication",
    ["source"],
)

# Auto-remediation metrics
auto_remediation_total = Counter(
    "auto_remediation_total",
    "Total auto-remediation actions triggered",
    ["action", "result"],  # result: success, failure, disabled, no_action
)

auto_remediation_duration_seconds = Summary(
    "auto_remediation_duration_seconds",
    "Auto-remediation action execution time",
    ["action"],
)

# SLO violation metrics
slo_violation_total = Counter(
    "slo_violation_total",
    "Total SLO violations detected",
    ["target"],  # target: api_latency, ingest_success_rate, scheduler_on_time
)

# Detector metrics
detector_checks_total = Counter(
    "detector_checks_total",
    "Total detector checks executed",
    ["detector", "result"],  # result: pass, fail
)

detector_check_duration_seconds = Summary(
    "detector_check_duration_seconds",
    "Detector check execution time",
    ["detector"],
)

# === Stage 18: Reviews SLA Metrics ===

# TTFR (Time to First Reply) distribution
reviews_ttfr_seconds = Histogram(
    "reviews_ttfr_seconds",
    "Time to first reply in seconds",
    ["marketplace"],
    buckets=[60, 300, 900, 1800, 3600, 7200, 14400, 28800, 57600, 86400, 172800],  # 1m to 48h
)

# SLA compliance
reviews_sla_within_total = Counter(
    "reviews_sla_within_total",
    "Reviews replied within/outside SLA",
    ["status"],  # status: ok (within SLA) | fail (outside SLA)
)

# Reply kind tracking
reviews_answer_kind_total = Counter(
    "reviews_answer_kind_total",
    "Reviews by answer kind",
    ["kind"],  # kind: template | ai
)

# Overdue reviews gauge
reviews_overdue_total = Gauge(
    "reviews_overdue_total",
    "Number of overdue reviews without first reply",
)

# Escalation notifications
reviews_escalation_sent_total = Counter(
    "reviews_escalation_sent_total",
    "Total escalation notifications sent",
)

# === Stage 19: Multi-Tenant Security Metrics ===

# Tenant scoping violations
tenant_unscoped_query_total = Counter(
    "tenant_unscoped_query_total",
    "Total queries attempted without proper org_id scoping",
    ["error_type"],  # error_type: missing_org_id, missing_filter
)
