"""stage17 ops alerts and slo

Revision ID: 2ceda79b02d6
Revises: f54e77fed756
Create Date: 2025-10-02 18:59:32.082483

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2ceda79b02d6"
down_revision: Union[str, None] = "f54e77fed756"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === ops_alerts_history ===
    op.create_table(
        "ops_alerts_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("source", sa.String(100), nullable=False, comment="Detector name"),
        sa.Column("severity", sa.String(20), nullable=False, comment="warning|error|critical"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "fingerprint", sa.String(64), nullable=False, comment="MD5 hash for deduplication"
        ),
        sa.Column("extras_json", sa.Text, nullable=True, comment="JSON extras"),
        sa.Column(
            "sent_to_chat_ids", sa.String(200), nullable=True, comment="Comma-separated chat IDs"
        ),
    )
    op.create_index("idx_ops_alerts_created", "ops_alerts_history", ["created_at"])
    op.create_index("idx_ops_alerts_fingerprint", "ops_alerts_history", ["fingerprint"])

    # === ops_remediation_history ===
    op.create_table(
        "ops_remediation_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "triggered_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("alert_id", sa.Integer, nullable=True, comment="FK to ops_alerts_history"),
        sa.Column("action_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, comment="success|failure"),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("idx_ops_remed_triggered", "ops_remediation_history", ["triggered_at"])

    # === vw_slo_daily ===
    # Daily SLO aggregation: ingest success rate, scheduler on-time, API latency (placeholder)
    op.execute(
        """
        CREATE VIEW vw_slo_daily AS
        SELECT
            d,
            -- Ingest success rate (from daily_sales existence)
            (SELECT COUNT(*) FROM daily_sales WHERE d = main.d) AS ingest_success_count,
            (SELECT COUNT(*) FROM daily_sales WHERE d = main.d) AS ingest_total_count,
            CASE
                WHEN (SELECT COUNT(*) FROM daily_sales WHERE d = main.d) = 0 THEN 0.0
                ELSE 100.0
            END AS ingest_success_rate_pct,

            -- Scheduler on-time (placeholder - requires scheduler job logging)
            0 AS scheduler_jobs_on_time,
            0 AS scheduler_jobs_total,
            100.0 AS scheduler_on_time_pct,

            -- API latency p95 (placeholder - requires metrics collection)
            0.0 AS api_latency_p95_ms
        FROM (
            SELECT DISTINCT d FROM daily_sales
            UNION
            SELECT DISTINCT d FROM pnl_daily
        ) AS main
        ORDER BY d DESC
    """
    )

    # === vw_ops_health ===
    # Current operational health summary
    op.execute(
        """
        CREATE VIEW vw_ops_health AS
        SELECT
            (SELECT COUNT(*) FROM ops_alerts_history WHERE created_at > datetime('now', '-1 hour')) AS alerts_last_hour,
            (SELECT COUNT(*) FROM ops_alerts_history WHERE created_at > datetime('now', '-24 hours') AND severity = 'critical') AS critical_last_24h,
            (SELECT COUNT(*) FROM ops_remediation_history WHERE triggered_at > datetime('now', '-1 hour')) AS remediations_last_hour,
            (SELECT COUNT(*) FROM ops_remediation_history WHERE triggered_at > datetime('now', '-24 hours') AND status = 'failure') AS remediation_failures_24h
    """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_ops_health")
    op.execute("DROP VIEW IF EXISTS vw_slo_daily")
    op.drop_index("idx_ops_remed_triggered", "ops_remediation_history")
    op.drop_table("ops_remediation_history")
    op.drop_index("idx_ops_alerts_fingerprint", "ops_alerts_history")
    op.drop_index("idx_ops_alerts_created", "ops_alerts_history")
    op.drop_table("ops_alerts_history")
