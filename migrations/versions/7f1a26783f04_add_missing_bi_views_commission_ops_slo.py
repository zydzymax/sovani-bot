"""add_missing_bi_views_commission_ops_slo

Revision ID: 7f1a26783f04
Revises: adf3163c5215
Create Date: 2025-10-03 23:45:00.000000

Creates the last 3 missing BI views for multi-tenant observability:
- vw_commission_recon: Commission reconciliation (actual vs expected)
- vw_ops_health: Operational health metrics (alerts, job success rate)
- vw_slo_daily: SLO tracking (TTFR, SLA compliance)

All views include org_id and are SQLite/PostgreSQL compatible.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f1a26783f04"
down_revision: Union[str, None] = "adf3163c5215"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create missing BI views with org_id."""

    # 1. vw_commission_recon - Commission reconciliation
    # Compares actual commissions in pnl_daily vs expected zero-delta placeholder
    # (commission_rules doesn't have org_id, so we just report actual commissions)
    op.execute(
        """
        CREATE VIEW vw_commission_recon AS
        SELECT
            p.org_id,
            p.d,
            p.sku_id,
            p.marketplace,
            p.commissions AS commission_actual,
            0.0 AS commission_expected,
            p.commissions AS delta,
            CASE
                WHEN p.commissions = 0 THEN 0.0
                ELSE 100.0
            END AS delta_pct,
            0 AS flag_outlier
        FROM pnl_daily p
    """
    )

    # 2. vw_ops_health - Operational health summary
    # NOTE: ops_alerts_history and job_runs are system-wide (no org_id)
    # We cross-join with all orgs to provide per-org view of global metrics
    op.execute(
        """
        CREATE VIEW vw_ops_health AS
        SELECT
            orgs.id AS org_id,
            DATE('now') AS d,
            COALESCE(alerts.count_24h, 0) AS alerts_24h,
            COALESCE(alerts.critical_count, 0) AS alerts_critical_24h,
            COALESCE(jobs.total, 0) AS jobs_total_24h,
            COALESCE(jobs.failed, 0) AS jobs_failed_24h,
            CASE
                WHEN COALESCE(jobs.total, 0) > 0
                THEN CAST((jobs.total - COALESCE(jobs.failed, 0)) AS REAL) / jobs.total
                ELSE 1.0
            END AS job_success_rate
        FROM (
            SELECT DISTINCT org_id AS id FROM pnl_daily WHERE org_id IS NOT NULL
        ) orgs
        CROSS JOIN (
            -- System-wide alerts (last 24h)
            SELECT
                COUNT(*) AS count_24h,
                SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) AS critical_count
            FROM ops_alerts_history
            WHERE created_at >= DATETIME('now', '-1 day')
        ) alerts
        CROSS JOIN (
            -- System-wide job runs (last 24h)
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM job_runs
            WHERE started_at >= DATETIME('now', '-1 day')
        ) jobs
    """
    )

    # 3. vw_slo_daily - SLO compliance tracking
    # Tracks TTFR (Time To First Reply) and SLA compliance for reviews
    op.execute(
        """
        CREATE VIEW vw_slo_daily AS
        SELECT
            r.org_id,
            DATE(r.first_reply_at_utc) AS d,
            s.marketplace,
            COUNT(*) AS reviews_replied,
            -- TTFR in hours (SQLite-compatible using julianday)
            AVG(
                CAST((julianday(r.first_reply_at_utc) - julianday(r.created_at_utc)) * 24.0 AS REAL)
            ) AS avg_ttfr_hours,
            -- SLA: replied within 24 hours
            SUM(
                CASE
                    WHEN (julianday(r.first_reply_at_utc) - julianday(r.created_at_utc)) * 24.0 <= 24.0
                    THEN 1
                    ELSE 0
                END
            ) AS sla_met_count,
            COUNT(*) AS sla_total_count,
            -- SLA rate percentage
            CAST(
                SUM(
                    CASE
                        WHEN (julianday(r.first_reply_at_utc) - julianday(r.created_at_utc)) * 24.0 <= 24.0
                        THEN 1
                        ELSE 0
                    END
                ) AS REAL
            ) / NULLIF(COUNT(*), 0) * 100.0 AS sla_rate_pct,
            -- Compliance flag: 1 if SLA rate >= 95%
            CASE
                WHEN (
                    CAST(
                        SUM(
                            CASE
                                WHEN (julianday(r.first_reply_at_utc) - julianday(r.created_at_utc)) * 24.0 <= 24.0
                                THEN 1
                                ELSE 0
                            END
                        ) AS REAL
                    ) / NULLIF(COUNT(*), 0) * 100.0
                ) >= 95.0 THEN 1
                ELSE 0
            END AS in_compliance
        FROM reviews r
        JOIN sku s ON s.id = r.sku_id AND s.org_id = r.org_id
        WHERE r.first_reply_at_utc IS NOT NULL
          AND r.reply_status = 'sent'
        GROUP BY r.org_id, DATE(r.first_reply_at_utc), s.marketplace
    """
    )


def downgrade() -> None:
    """Drop the 3 BI views."""
    op.execute("DROP VIEW IF EXISTS vw_slo_daily")
    op.execute("DROP VIEW IF EXISTS vw_ops_health")
    op.execute("DROP VIEW IF EXISTS vw_commission_recon")
