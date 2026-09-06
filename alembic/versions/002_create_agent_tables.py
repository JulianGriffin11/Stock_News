"""Create item_summaries, digest_runs, and emails.

Revision ID: 002_create_agent_tables
Revises: 001_create_raw_items
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_create_agent_tables"
down_revision: Union[str, Sequence[str], None] = "001_create_raw_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "item_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("raw_item_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("key_numbers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["raw_item_id"],
            ["raw_items.id"],
            name="fk_item_summaries_raw_item_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_item_id", name="uq_item_summaries_raw_item_id"),
    )
    op.create_index("ix_item_summaries_item_type", "item_summaries", ["item_type"])
    op.create_index("ix_item_summaries_created_at", "item_summaries", ["created_at"])

    op.create_table(
        "digest_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("ranked_item_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rank_rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("week_start", name="uq_digest_runs_week_start"),
    )

    op.create_table(
        "emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("digest_run_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resend_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["digest_run_id"],
            ["digest_runs.id"],
            name="fk_emails_digest_run_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("digest_run_id", name="uq_emails_digest_run_id"),
    )


def downgrade() -> None:
    op.drop_table("emails")
    op.drop_table("digest_runs")
    op.drop_index("ix_item_summaries_created_at", table_name="item_summaries")
    op.drop_index("ix_item_summaries_item_type", table_name="item_summaries")
    op.drop_table("item_summaries")
