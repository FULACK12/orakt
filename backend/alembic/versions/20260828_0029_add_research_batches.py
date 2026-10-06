"""add durable equity research batches

Revision ID: 20260828_0029
Revises: 20260826_0028
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260828_0029"
down_revision: str | None = "20260826_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_batches",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("template_version", sa.String(length=64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("completed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'partial_failed', 'failed')",
            name=op.f("ck_research_batches_research_batch_status"),
        ),
        sa.CheckConstraint(
            "target_count >= 1", name=op.f("ck_research_batches_research_batch_target_count")
        ),
        sa.CheckConstraint(
            "completed_count >= 0 AND completed_count <= target_count",
            name=op.f("ck_research_batches_research_batch_completed_count"),
        ),
        sa.CheckConstraint(
            "failed_count >= 0 AND failed_count <= target_count",
            name=op.f("ck_research_batches_research_batch_failed_count"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_batches")),
    )
    op.create_index(
        "ix_research_batches_status_created",
        "research_batches",
        ["status", "created_at"],
    )
    op.create_table(
        "research_batch_items",
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("market_region", sa.String(length=16), nullable=False),
        sa.Column("research_scope", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inquiry_id", sa.BigInteger(), nullable=True),
        sa.Column("data_readiness", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("audit_summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "market_region IN ('us', 'china')",
            name=op.f("ck_research_batch_items_research_batch_item_region"),
        ),
        sa.CheckConstraint(
            "research_scope IN ('sec_numeric_evidence', 'market_factor_evidence')",
            name=op.f("ck_research_batch_items_research_batch_item_scope"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name=op.f("ck_research_batch_items_research_batch_item_status"),
        ),
        sa.CheckConstraint(
            "priority >= 0", name=op.f("ck_research_batch_items_research_batch_item_priority")
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name=op.f("ck_research_batch_items_research_batch_item_attempts")
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["research_batches.id"],
            name=op.f("fk_research_batch_items_batch_id_research_batches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inquiry_id"],
            ["research_inquiries.id"],
            name=op.f("fk_research_batch_items_inquiry_id_research_inquiries"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_batch_items")),
        sa.UniqueConstraint(
            "batch_id",
            "market_region",
            "ticker",
            name="uq_research_batch_item_target",
        ),
    )
    op.create_index(
        "ix_research_batch_items_status_priority",
        "research_batch_items",
        ["status", "priority", "created_at"],
    )
    op.create_table(
        "research_report_audit_jobs",
        sa.Column("inquiry_id", sa.BigInteger(), nullable=False),
        sa.Column("audit_version", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("output_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("before_result", sa.JSON(), nullable=True),
        sa.Column("before_evidence_snapshot", sa.JSON(), nullable=True),
        sa.Column("audit_summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "mode IN ('audit_only', 'refresh_and_audit')",
            name=op.f("ck_research_report_audit_jobs_research_report_audit_job_mode"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'superseded')",
            name=op.f("ck_research_report_audit_jobs_research_report_audit_job_status"),
        ),
        sa.CheckConstraint(
            "priority >= 0",
            name=op.f("ck_research_report_audit_jobs_research_report_audit_job_priority"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1",
            name=op.f("ck_research_report_audit_jobs_research_report_audit_job_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["inquiry_id"],
            ["research_inquiries.id"],
            name=op.f("fk_research_report_audit_jobs_inquiry_id_research_inquiries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_report_audit_jobs")),
        sa.UniqueConstraint(
            "inquiry_id",
            "audit_version",
            "source_fingerprint",
            name="uq_research_report_audit_source",
        ),
    )
    op.create_index(
        "ix_research_report_audit_jobs_claim",
        "research_report_audit_jobs",
        ["status", "available_at", "priority"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_report_audit_jobs_claim",
        table_name="research_report_audit_jobs",
    )
    op.drop_table("research_report_audit_jobs")
    op.drop_index(
        "ix_research_batch_items_status_priority",
        table_name="research_batch_items",
    )
    op.drop_table("research_batch_items")
    op.drop_index("ix_research_batches_status_created", table_name="research_batches")
    op.drop_table("research_batches")
