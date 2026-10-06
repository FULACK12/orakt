"""Create source, document, event and evidence-link tables.

Revision ID: 20260729_0001
Revises:
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_type = sa.Enum(
    "rss",
    "news",
    "official",
    "government",
    "central_bank",
    "research",
    "api",
    name="source_type",
    native_enum=False,
    create_constraint=True,
)
event_status = sa.Enum(
    "confirmed",
    "partially_confirmed",
    "rumour",
    "denied",
    name="event_status",
    native_enum=False,
    create_constraint=True,
)
document_stance = sa.Enum(
    "supports",
    "contradicts",
    "neutral",
    name="document_stance",
    native_enum=False,
    create_constraint=True,
)
id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    """Create the first four application tables."""
    op.create_table(
        "sources",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("source_type", source_type, server_default=sa.text("'rss'"), nullable=False),
        sa.Column("ownership", sa.String(length=255), nullable=True),
        sa.Column(
            "credibility_baseline",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.500"),
            nullable=False,
        ),
        sa.Column(
            "political_bias_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
            "credibility_baseline >= 0 AND credibility_baseline <= 1",
            name="credibility_baseline_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint("name", "country", name="uq_sources_name_country"),
    )

    op.create_table(
        "documents",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("source_id", id_type, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("credibility_score", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("raw_object_path", sa.Text(), nullable=True),
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
            "credibility_score IS NULL OR "
            "(credibility_score >= 0 AND credibility_score <= 1)",
            name="credibility_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_documents_source_id_sources",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint("content_hash", name="uq_documents_content_hash"),
        sa.UniqueConstraint("url", name="uq_documents_url"),
    )
    op.create_index(
        "ix_documents_source_published_at",
        "documents",
        ["source_id", "published_at"],
    )
    op.create_index("ix_documents_published_at", "documents", ["published_at"])

    op.create_table(
        "events",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "status",
            event_status,
            server_default=sa.text("'partially_confirmed'"),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.000"),
            nullable=False,
        ),
        sa.Column(
            "novelty",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.000"),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.000"),
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
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
            "confidence >= 0 AND confidence <= 1",
            name="confidence_range",
        ),
        sa.CheckConstraint(
            "end_at IS NULL OR end_at >= start_at",
            name="time_range",
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="latitude_range",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="longitude_range",
        ),
        sa.CheckConstraint(
            "novelty >= 0 AND novelty <= 1",
            name="novelty_range",
        ),
        sa.CheckConstraint(
            "severity >= 0 AND severity <= 1",
            name="severity_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_events"),
    )
    op.create_index("ix_events_country_start_at", "events", ["country_code", "start_at"])
    op.create_index("ix_events_type_start_at", "events", ["event_type", "start_at"])
    op.create_index("ix_events_status_updated_at", "events", ["status", "updated_at"])

    op.create_table(
        "event_documents",
        sa.Column("event_id", id_type, nullable=False),
        sa.Column("document_id", id_type, nullable=False),
        sa.Column(
            "relevance_score",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("1.000"),
            nullable=False,
        ),
        sa.Column(
            "stance",
            document_stance,
            server_default=sa.text("'neutral'"),
            nullable=False,
        ),
        sa.Column(
            "is_primary_source",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="relevance_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_event_documents_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="fk_event_documents_event_id_events",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "event_id",
            "document_id",
            name="pk_event_documents",
        ),
    )
    op.create_index(
        "ix_event_documents_document_id",
        "event_documents",
        ["document_id"],
    )


def downgrade() -> None:
    """Remove the first four application tables."""
    op.drop_index("ix_event_documents_document_id", table_name="event_documents")
    op.drop_table("event_documents")
    op.drop_index("ix_events_status_updated_at", table_name="events")
    op.drop_index("ix_events_type_start_at", table_name="events")
    op.drop_index("ix_events_country_start_at", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_documents_published_at", table_name="documents")
    op.drop_index("ix_documents_source_published_at", table_name="documents")
    op.drop_table("documents")
    op.drop_table("sources")
