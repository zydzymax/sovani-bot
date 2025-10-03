"""stage18 reviews SLA ttfr and reply_kind

Revision ID: 96a2ffdd5b16
Revises: 2ceda79b02d6
Create Date: 2025-10-02 21:55:18.261755

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "96a2ffdd5b16"
down_revision: Union[str, None] = "2ceda79b02d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add SLA tracking fields to reviews table
    op.add_column(
        "reviews", sa.Column("first_reply_at_utc", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("reviews", sa.Column("reply_kind", sa.String(length=10), nullable=True))

    # Create indexes for efficient SLA queries
    op.create_index("idx_reviews_created", "reviews", ["created_at_utc"])
    op.create_index("idx_reviews_first_reply", "reviews", ["first_reply_at_utc"])

    # Backfill first_reply_at_utc for existing replied reviews
    # Note: This is a best-effort backfill. Without historical timestamps,
    # we can't determine exact TTFR for old reviews.
    # In production, you might have logs/audit tables to pull real timestamps from.

    # For now, leave NULL for existing reviews - they won't count in SLA calculations
    # Future replies will be tracked accurately

    # Create vw_reviews_sla view
    # PostgreSQL-first design: Use EXTRACT(EPOCH FROM ...) for timestamp diff
    # This works in both PostgreSQL and SQLite 3.38+
    op.execute(
        """
        CREATE VIEW vw_reviews_sla AS
        SELECT
            r.id AS review_id,
            r.marketplace,
            r.sku_id,
            s.article,
            r.created_at_utc,
            r.rating,
            (COALESCE(length(NULLIF(r.text, '')), 0) >= 40 OR r.has_media = 1) AS ai_needed,
            r.first_reply_at_utc,
            CAST((EXTRACT(EPOCH FROM r.first_reply_at_utc) - EXTRACT(EPOCH FROM r.created_at_utc)) / 60.0 AS REAL) AS ttfr_minutes,
            CASE
                WHEN r.first_reply_at_utc IS NOT NULL
                    AND (EXTRACT(EPOCH FROM r.first_reply_at_utc) - EXTRACT(EPOCH FROM r.created_at_utc)) / 3600.0 <= 24  -- SLA_FIRST_REPLY_HOURS
                THEN 1
                ELSE 0
            END AS within_sla,
            r.reply_status,
            r.reply_kind,
            r.org_id
        FROM reviews r
        JOIN sku s ON s.id = r.sku_id
    """
    )


def downgrade() -> None:
    # Drop view
    op.execute("DROP VIEW IF EXISTS vw_reviews_sla")

    # Drop indexes
    op.drop_index("idx_reviews_first_reply", "reviews")
    op.drop_index("idx_reviews_created", "reviews")

    # Drop columns
    op.drop_column("reviews", "reply_kind")
    op.drop_column("reviews", "first_reply_at_utc")
