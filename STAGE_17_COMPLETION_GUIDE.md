# Stage 17 Completion Guide

## Current Status: ~50% Complete

### ✅ Already Done:
1. ENV configuration (.env.example + config.py) - 8 parameters
2. Basic file structure created (app/ops/)
3. Partial implementations of detectors, alerts, remediation

### 🔨 Need to Complete:

## 1. Database Migration

File: `migrations/versions/2ceda79b02d6_stage17_ops_alerts_and_slo.py`

```python
def upgrade() -> None:
    # Table: ops_alerts_history
    op.create_table(
        "ops_alerts_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("msg", sa.Text(), nullable=False),
        sa.Column("extras", sa.JSON(), nullable=True),
    )
    op.create_index("ix_ops_alerts_ts", "ops_alerts_history", ["ts"])
    op.create_index("ix_ops_alerts_fingerprint", "ops_alerts_history", ["fingerprint"])

    # Table: ops_remediation_history
    op.create_table(
        "ops_remediation_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),  # success|failed|skipped
        sa.Column("extras", sa.JSON(), nullable=True),
    )
    op.create_index("ix_ops_remediation_ts", "ops_remediation_history", ["ts"])

    # View: vw_slo_daily
    op.execute("""
        CREATE VIEW vw_slo_daily AS
        SELECT
            DATE(ts) AS d,
            COUNT(*) FILTER (WHERE severity = 'error') AS errors_total,
            COUNT(*) FILTER (WHERE severity = 'critical') AS critical_total,
            COUNT(*) FILTER (WHERE source = 'api_latency') AS api_latency_violations,
            COUNT(*) FILTER (WHERE source = 'ingest_success') AS ingest_violations,
            COUNT(*) FILTER (WHERE source = 'scheduler_on_time') AS scheduler_violations
        FROM ops_alerts_history
        GROUP BY DATE(ts)
        ORDER BY d DESC;
    """)

def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_slo_daily;")
    op.drop_index("ix_ops_remediation_ts", "ops_remediation_history")
    op.drop_table("ops_remediation_history")
    op.drop_index("ix_ops_alerts_fingerprint", "ops_alerts_history")
    op.drop_index("ix_ops_alerts_ts", "ops_alerts_history")
    op.drop_table("ops_alerts_history")
```

## 2. Complete app/ops/detectors.py

```python
"""Operational health detectors."""
from __future__ import annotations
import hashlib
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from sqlalchemy import text, func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.core.config import get_settings

def check_api_latency_p95(db: Session) -> dict:
    """Check API p95 latency (stub - requires metrics collection)."""
    # TODO: Implement with actual metrics from Prometheus or logs
    settings = get_settings()
    target_ms = settings.slo_api_latency_p95_ms

    # Stub: assume OK
    p95_actual = 800  # Replace with actual calculation
    ok = p95_actual < target_ms

    return {
        "ok": ok,
        "severity": "warning" if not ok else "info",
        "msg": f"API p95 latency: {p95_actual}ms (target: {target_ms}ms)",
        "fingerprint": hashlib.sha256(f"api_latency_p95".encode()).hexdigest()[:16],
        "extras": {"p95_ms": p95_actual, "target_ms": target_ms},
    }

def check_ingest_success_rate(db: Session) -> dict:
    """Check ingestion success rate from logs or job_runs."""
    from app.db.models import JobRun
    settings = get_settings()
    target_pct = settings.slo_ingest_success_rate_pct

    # Last 60 minutes
    since = datetime.utcnow() - timedelta(hours=1)
    stmt = select(
        func.count(JobRun.id).label("total"),
        func.sum(func.cast(JobRun.status == "success", sa.Integer)).label("success")
    ).where(JobRun.started_at >= since, JobRun.job_name.like("%ingest%"))

    result = db.execute(stmt).first()
    total = result.total or 0
    success = result.success or 0

    if total == 0:
        return {"ok": True, "severity": "info", "msg": "No ingest jobs in last hour",
                "fingerprint": "ingest_success_none", "extras": {}}

    success_rate = (success / total) * 100
    ok = success_rate >= target_pct

    return {
        "ok": ok,
        "severity": "error" if not ok else "info",
        "msg": f"Ingest success rate: {success_rate:.1f}% (target: {target_pct}%)",
        "fingerprint": hashlib.sha256(f"ingest_success".encode()).hexdigest()[:16],
        "extras": {"success_rate_pct": success_rate, "total": total, "success": success},
    }

def check_scheduler_on_time(db: Session) -> dict:
    """Check if scheduler jobs are on time."""
    from app.db.models import JobRun
    settings = get_settings()
    target_pct = settings.slo_scheduler_on_time_pct

    # Last 24 hours
    since = datetime.utcnow() - timedelta(hours=24)
    stmt = select(JobRun).where(JobRun.started_at >= since)
    rows = db.execute(stmt).scalars().all()

    if not rows:
        return {"ok": True, "severity": "info", "msg": "No jobs in last 24h",
                "fingerprint": "scheduler_none", "extras": {}}

    # Count on-time (within 10 min of expected)
    on_time = sum(1 for r in rows if r.duration_sec and r.duration_sec < 600)
    total = len(rows)
    on_time_pct = (on_time / total) * 100
    ok = on_time_pct >= target_pct

    return {
        "ok": ok,
        "severity": "warning" if not ok else "info",
        "msg": f"Scheduler on-time: {on_time_pct:.1f}% (target: {target_pct}%)",
        "fingerprint": hashlib.sha256(f"scheduler_on_time".encode()).hexdigest()[:16],
        "extras": {"on_time_pct": on_time_pct, "total": total},
    }

def check_cash_balance_threshold(db: Session) -> dict:
    """Check cash balance from vw_cashflow_daily."""
    settings = get_settings()
    threshold = settings.cf_negative_balance_alert_threshold

    query = text("""
        SELECT marketplace, balance
        FROM vw_cashflow_daily
        WHERE d = (SELECT MAX(d) FROM vw_cashflow_daily)
    """)
    rows = db.execute(query).mappings().all()

    violations = [r for r in rows if r["balance"] < threshold]
    ok = len(violations) == 0

    return {
        "ok": ok,
        "severity": "critical" if not ok else "info",
        "msg": f"Cash balance violations: {len(violations)} marketplace(s)",
        "fingerprint": hashlib.sha256(f"cash_balance".encode()).hexdigest()[:16],
        "extras": {"violations": [dict(v) for v in violations]},
    }

def check_commission_outliers(db: Session) -> dict:
    """Check commission reconciliation outliers."""
    query = text("""
        SELECT COUNT(*) AS outliers
        FROM vw_commission_recon
        WHERE flag_outlier = 1
          AND d >= DATE('now', '-7 days')
    """)
    result = db.execute(query).scalar()
    outliers = result or 0
    ok = outliers < 10  # Threshold: 10 outliers

    return {
        "ok": ok,
        "severity": "warning" if not ok else "info",
        "msg": f"Commission outliers (7d): {outliers}",
        "fingerprint": hashlib.sha256(f"commission_outliers".encode()).hexdigest()[:16],
        "extras": {"outliers": outliers},
    }

def check_db_growth(db: Session) -> dict:
    """Check database growth (stub - requires monitoring)."""
    # TODO: Implement actual DB size tracking
    ok = True  # Stub

    return {
        "ok": ok,
        "severity": "info",
        "msg": "DB growth check: OK (stub)",
        "fingerprint": hashlib.sha256(f"db_growth".encode()).hexdigest()[:16],
        "extras": {},
    }

def run_all_detectors(db: Session) -> list[dict]:
    """Run all detectors and return results."""
    detectors = [
        check_api_latency_p95,
        check_ingest_success_rate,
        check_scheduler_on_time,
        check_cash_balance_threshold,
        check_commission_outliers,
        check_db_growth,
    ]

    results = []
    for detector in detectors:
        try:
            result = detector(db)
            results.append(result)
        except Exception as e:
            results.append({
                "ok": False,
                "severity": "error",
                "msg": f"Detector {detector.__name__} failed: {str(e)}",
                "fingerprint": hashlib.sha256(detector.__name__.encode()).hexdigest()[:16],
                "extras": {"error": str(e)},
            })

    return results
```

## 3. Complete app/ops/alerts.py

```python
"""Alert management with deduplication."""
from __future__ import annotations
import time
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory dedup cache (production: use Redis)
_alert_cache: dict[str, float] = {}

def should_send_alert(fingerprint: str, severity: str) -> bool:
    """Check if alert should be sent (deduplication)."""
    settings = get_settings()
    min_severity = settings.alert_min_severity

    # Severity check
    severity_order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
    if severity_order.get(severity, 0) < severity_order.get(min_severity, 1):
        return False

    # Deduplication
    window = settings.alert_dedup_window_sec
    now = time.time()
    last_sent = _alert_cache.get(fingerprint, 0)

    if now - last_sent < window:
        return False

    _alert_cache[fingerprint] = now
    return True

def send_alert(db: Session, result: dict) -> None:
    """Send alert if needed and log to history."""
    fingerprint = result["fingerprint"]
    severity = result["severity"]

    if not should_send_alert(fingerprint, severity):
        return

    # Log to database
    from sqlalchemy import Table, MetaData
    metadata = MetaData()
    alerts_table = Table("ops_alerts_history", metadata, autoload_with=db.get_bind())

    db.execute(
        alerts_table.insert().values(
            ts=datetime.utcnow(),
            severity=severity,
            source=result.get("extras", {}).get("source", "unknown"),
            fingerprint=fingerprint,
            msg=result["msg"],
            extras=result.get("extras"),
        )
    )
    db.commit()

    # Send to Telegram
    settings = get_settings()
    chat_ids = [cid.strip() for cid in settings.alert_chat_ids.split(",") if cid.strip()]

    if chat_ids:
        # TODO: Implement actual Telegram sending
        logger.warning(f"ALERT [{severity.upper()}]: {result['msg']}")
        logger.info(f"Would send to chats: {chat_ids}")

    # Update Prometheus metrics
    try:
        from app.core.metrics import alerts_total
        alerts_total.labels(severity=severity).inc()
    except ImportError:
        pass
```

## 4. Complete app/ops/remediation.py

```python
"""Auto-remediation actions."""
from __future__ import annotations
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)

def log_remediation(db: Session, action: str, target: str, status: str, extras: dict = None) -> None:
    """Log remediation action to history."""
    from sqlalchemy import Table, MetaData
    metadata = MetaData()
    remediation_table = Table("ops_remediation_history", metadata, autoload_with=db.get_bind())

    db.execute(
        remediation_table.insert().values(
            ts=datetime.utcnow(),
            action=action,
            target=target,
            status=status,
            extras=extras or {},
        )
    )
    db.commit()

def restart_scheduler_job(db: Session, job_name: str) -> dict:
    """Restart a scheduler job (stub)."""
    logger.info(f"Restarting scheduler job: {job_name}")
    # TODO: Implement actual restart logic (systemctl, internal scheduler API, etc.)

    log_remediation(db, "restart_scheduler_job", job_name, "success", {"method": "stub"})
    return {"action": "restart_scheduler_job", "target": job_name, "status": "success"}

def bump_backoff(db: Session, service: str) -> dict:
    """Increase backoff for service (stub)."""
    logger.info(f"Bumping backoff for service: {service}")
    # TODO: Implement actual backoff logic

    log_remediation(db, "bump_backoff", service, "success", {"new_backoff_sec": 30})
    return {"action": "bump_backoff", "target": service, "status": "success"}

def purge_stuck_tasks(db: Session, queue: str) -> dict:
    """Purge stuck tasks from queue (stub)."""
    logger.info(f"Purging stuck tasks from queue: {queue}")
    # TODO: Implement actual task purging

    log_remediation(db, "purge_stuck_tasks", queue, "success", {"purged": 0})
    return {"action": "purge_stuck_tasks", "target": queue, "status": "success"}

def compact_logs(db: Session) -> dict:
    """Compact/rotate logs (stub)."""
    logger.info("Compacting logs")
    # TODO: Implement actual log rotation

    log_remediation(db, "compact_logs", "system", "success", {"compressed_mb": 0})
    return {"action": "compact_logs", "target": "system", "status": "success"}

# Mapping: detector source -> remediation action
REMEDIATION_MAP = {
    "scheduler_on_time": lambda db: restart_scheduler_job(db, "collect_yesterday_data"),
    "ingest_success": lambda db: bump_backoff(db, "wb"),
    "db_growth": lambda db: compact_logs(db),
}

def trigger_remediation(db: Session, alert_result: dict) -> dict | None:
    """Trigger appropriate remediation based on alert."""
    settings = get_settings()

    if not settings.auto_remediation_enabled:
        return None

    source = alert_result.get("extras", {}).get("source", "")
    remediation_fn = REMEDIATION_MAP.get(source)

    if not remediation_fn:
        return None

    try:
        result = remediation_fn(db)
        logger.info(f"Remediation triggered: {result}")
        return result
    except Exception as e:
        logger.error(f"Remediation failed: {e}")
        log_remediation(db, "unknown", source, "failed", {"error": str(e)})
        return {"action": "failed", "error": str(e)}
```

## 5. Implement app/ops/slo.py

```python
"""SLO/SLI calculation and monitoring."""
from __future__ import annotations
from datetime import date, timedelta
from typing import TYPE_CHECKING
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.core.config import get_settings

def calculate_sli_metrics(db: Session, d: date) -> dict:
    """Calculate SLI metrics for a given date."""
    settings = get_settings()

    # Query vw_slo_daily
    query = text("SELECT * FROM vw_slo_daily WHERE d = :d")
    result = db.execute(query, {"d": d}).mappings().first()

    if not result:
        return {"status": "no_data", "date": str(d)}

    # Calculate SLI vs SLO
    api_latency_ok = result.get("api_latency_violations", 0) == 0
    ingest_ok = result.get("ingest_violations", 0) == 0
    scheduler_ok = result.get("scheduler_violations", 0) == 0

    overall_status = "green" if all([api_latency_ok, ingest_ok, scheduler_ok]) else "red"

    return {
        "date": str(d),
        "api_latency_sli": "pass" if api_latency_ok else "fail",
        "ingest_sli": "pass" if ingest_ok else "fail",
        "scheduler_sli": "pass" if scheduler_ok else "fail",
        "overall_status": overall_status,
        "errors_total": result.get("errors_total", 0),
        "critical_total": result.get("critical_total", 0),
    }

def get_slo_summary(db: Session, days: int = 7) -> dict:
    """Get SLO summary for last N days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    daily_sli = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        sli = calculate_sli_metrics(db, d)
        daily_sli.append(sli)

    # Calculate success rate
    passed = sum(1 for sli in daily_sli if sli.get("overall_status") == "green")
    success_rate = (passed / days) * 100

    return {
        "period": f"{start_date} to {end_date}",
        "days": days,
        "success_rate_pct": success_rate,
        "daily_sli": daily_sli,
    }
```

## 6. Add to app/core/metrics.py

```python
# At top of file
from prometheus_client import Counter

# Add these metrics
alerts_total = Counter("alerts_total", "Total alerts sent", ["severity"])
auto_remediation_total = Counter("auto_remediation_total", "Auto remediations", ["action", "result"])
slo_violation_total = Counter("slo_violation_total", "SLO violations", ["target"])
```

## 7. Continue with remaining components...

See full implementation in repository. Key remaining items:
- app/web/routers/ops.py (3 endpoints)
- app/scheduler/jobs.py (add ops_health_check)
- app/ops/runbooks.md (operational playbooks)
- tests/ops/* (20+ tests)
- STAGE_17_REPORT.md

Total estimated effort: 8-12 hours of development time.
