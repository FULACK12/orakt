"""Add per-document local-AI analysis cache.

Revision ID: 20260729_0005
Revises: 20260729_0004
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0005"
down_revision: str | None = "20260729_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Create the validated local-AI result cache."""
    op.create_table(
        "document_analyses",
        sa.Column("document_id", id_type, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("extractor_name", sa.String(length=255), nullable=False),
        sa.Column("extraction", sa.JSON(), nullable=False),
        sa.Column(
            "embedding_provider",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("embeddings", sa.JSON(), nullable=False),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_cluster_job_id", id_type, nullable=True),
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
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_analyses_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["last_cluster_job_id"],
            ["cluster_jobs.id"],
            name=(
                "fk_document_analyses_last_cluster_job_id_cluster_jobs"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "document_id",
            name="pk_document_analyses",
        ),
    )
    op.create_index(
        "ix_document_analyses_last_cluster_job_id",
        "document_analyses",
        ["last_cluster_job_id"],
    )


def downgrade() -> None:
    """Remove the local-AI result cache."""
    op.drop_index(
        "ix_document_analyses_last_cluster_job_id",
        table_name="document_analyses",
    )
    op.drop_table("document_analyses")
