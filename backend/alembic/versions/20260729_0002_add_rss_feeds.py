"""Add configurable RSS feeds and raw document metadata.

Revision ID: 20260729_0002
Revises: 20260729_0001
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0002"
down_revision: str | None = "20260729_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Create RSS endpoint state and document metadata storage."""
    op.add_column(
        "documents",
        sa.Column(
            "raw_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.create_table(
        "rss_feeds",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("source_id", id_type, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("license_name", sa.String(length=255), nullable=False),
        sa.Column("license_url", sa.Text(), nullable=True),
        sa.Column(
            "rate_limit_per_minute",
            sa.Numeric(precision=8, scale=3),
            server_default=sa.text("1.000"),
            nullable=False,
        ),
        sa.Column(
            "fetch_interval_seconds",
            sa.Integer(),
            server_default=sa.text("900"),
            nullable=False,
        ),
        sa.Column(
            "request_timeout_seconds",
            sa.Numeric(precision=6, scale=2),
            server_default=sa.text("30.00"),
            nullable=False,
        ),
        sa.Column(
            "user_agent",
            sa.String(length=255),
            server_default=sa.text("'NEWS-App/0.3'"),
            nullable=False,
        ),
        sa.Column("etag", sa.String(length=512), nullable=True),
        sa.Column("last_modified", sa.String(length=255), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="consecutive_failures_nonnegative",
        ),
        sa.CheckConstraint(
            "fetch_interval_seconds >= 60",
            name="fetch_interval_seconds_minimum",
        ),
        sa.CheckConstraint(
            "rate_limit_per_minute > 0 AND rate_limit_per_minute <= 60",
            name="rate_limit_per_minute_range",
        ),
        sa.CheckConstraint(
            "request_timeout_seconds >= 1 AND request_timeout_seconds <= 120",
            name="request_timeout_seconds_range",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_rss_feeds_source_id_sources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rss_feeds"),
        sa.UniqueConstraint("url", name="uq_rss_feeds_url"),
    )
    op.create_index(
        "ix_rss_feeds_enabled_last_fetched_at",
        "rss_feeds",
        ["enabled", "last_fetched_at"],
    )


def downgrade() -> None:
    """Remove RSS endpoint state and raw document metadata."""
    op.drop_index("ix_rss_feeds_enabled_last_fetched_at", table_name="rss_feeds")
    op.drop_table("rss_feeds")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("raw_metadata")

