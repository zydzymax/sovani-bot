"""Add JobRun table for scheduler monitoring (Stage 11)

Revision ID: 2d3b8a10c369
Revises: 201473760050
Create Date: 2025-10-02 12:15:08.449666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d3b8a10c369'
down_revision: Union[str, None] = '201473760050'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create job_runs table
    op.create_table(
        'job_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_name', sa.String(length=100), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_job_runs_job_name', 'job_runs', ['job_name'])
    op.create_index('ix_job_runs_started_at', 'job_runs', ['started_at'])
    op.create_index('ix_job_runs_status', 'job_runs', ['status'])
    op.create_index('ix_job_runs_name_started', 'job_runs', ['job_name', 'started_at'])


def downgrade() -> None:
    op.drop_index('ix_job_runs_name_started', table_name='job_runs')
    op.drop_index('ix_job_runs_status', table_name='job_runs')
    op.drop_index('ix_job_runs_started_at', table_name='job_runs')
    op.drop_index('ix_job_runs_job_name', table_name='job_runs')
    op.drop_table('job_runs')
