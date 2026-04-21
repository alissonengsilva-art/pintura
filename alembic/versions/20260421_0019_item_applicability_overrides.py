"""add item applicability overrides per shift

Revision ID: 20260421_0019
Revises: 20260421_0018
Create Date: 2026-04-21 00:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260421_0019"
down_revision: str | None = "20260421_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_item_applicability_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("operational_shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "operational_module_item_id",
            sa.Integer(),
            sa.ForeignKey("operational_module_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("override_status", sa.String(length=20), nullable=False, server_default="automatic"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("shift_id", "operational_module_item_id", name="uq_shift_item_applicability_override"),
    )
    op.create_index(
        op.f("ix_operational_item_applicability_overrides_shift_id"),
        "operational_item_applicability_overrides",
        ["shift_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_item_applicability_overrides_operational_module_item_id"),
        "operational_item_applicability_overrides",
        ["operational_module_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_operational_item_applicability_overrides_operational_module_item_id"),
        table_name="operational_item_applicability_overrides",
    )
    op.drop_index(
        op.f("ix_operational_item_applicability_overrides_shift_id"),
        table_name="operational_item_applicability_overrides",
    )
    op.drop_table("operational_item_applicability_overrides")
