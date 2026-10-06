"""add supply-chain site association scope

Revision ID: 20260831_0037
Revises: 20260831_0036
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_0037"
down_revision: str | None = "20260831_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("company_supply_chain_sites") as batch_op:
        batch_op.add_column(
            sa.Column(
                "association_scope",
                sa.String(64),
                server_default="issuer_reported_manufacturing_region",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "company_supply_chain_site_association_scope",
            "association_scope IN ('issuer_reported_manufacturing_region', "
            "'supplier_facility_not_customer_linked', 'customer_linked_facility', "
            "'confirmed_production_line', 'proximity_reference')",
        )


def downgrade() -> None:
    with op.batch_alter_table("company_supply_chain_sites") as batch_op:
        batch_op.drop_constraint(
            "company_supply_chain_site_association_scope",
            type_="check",
        )
        batch_op.drop_column("association_scope")
