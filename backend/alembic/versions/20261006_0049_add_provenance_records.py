"""Add isolated devnet provenance commitments. No changes to source records."""

import sqlalchemy as sa

from alembic import op

revision = "20261006_0049"
down_revision = "20261005_0048"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "provenance_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("object_key", sa.String(64), nullable=False),
        sa.Column("object_type", sa.String(16), nullable=False),
        sa.Column("object_id", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("source_set_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("canonical_payload", sa.JSON(), nullable=False),
        sa.Column("memo", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("publisher", sa.String(64)),
        sa.Column("unsigned_transaction", sa.Text()),
        sa.Column("signed_transaction", sa.Text()),
        sa.Column("signature", sa.String(100), unique=True),
        sa.Column("last_valid_block_height", sa.Integer()),
        sa.Column("receipt", sa.JSON()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("object_key", "revision", name="uq_provenance_revision"),
        sa.UniqueConstraint("object_key", "payload_hash", name="uq_provenance_payload"),
        sa.CheckConstraint("revision >= 1", name="provenance_revision_positive"),
        sa.CheckConstraint(
            "status IN ('prepared','submitted','finalized')", name="provenance_status"
        ),
    )


def downgrade():
    op.drop_table("provenance_records")
