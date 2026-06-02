"""add prioridade to operational_module_items

Revision ID: 20260601_0023
Revises: 20260428_0022
Create Date: 2026-06-01 10:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260601_0023"
down_revision: str | None = "20260428_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("operational_module_items")}
    if "prioridade" not in existing:
        op.add_column(
            "operational_module_items",
            sa.Column("prioridade", sa.String(length=20), nullable=False, server_default="medio"),
        )
    op.execute(
        "UPDATE operational_module_items "
        "SET prioridade = 'medio' "
        "WHERE prioridade IS NULL OR prioridade = '' OR prioridade NOT IN ('baixo', 'medio', 'alto')"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("operational_module_items")}
    if "prioridade" in existing:
        op.drop_column("operational_module_items", "prioridade")
