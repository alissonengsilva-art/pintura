"""add frequency fields to operational module items

Revision ID: 20260421_0018
Revises: 20260420_0017
Create Date: 2026-04-21 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260421_0018"
down_revision: str | None = "20260420_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "operational_module_items",
        sa.Column("frequencia_tipo", sa.String(length=20), nullable=False, server_default="diario"),
    )
    op.add_column("operational_module_items", sa.Column("dia_semana", sa.Integer(), nullable=True))
    op.add_column("operational_module_items", sa.Column("dia_mes", sa.Integer(), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE operational_module_items
            SET frequencia_tipo = CASE
                WHEN UPPER(COALESCE(frequencia, '')) = 'SEMANAL' THEN 'semanal'
                WHEN UPPER(COALESCE(frequencia, '')) = 'MENSAL' THEN 'mensal'
                WHEN UPPER(COALESCE(frequencia, '')) IN ('SOB_DEMANDA', 'SOB DEMANDA') THEN 'sob_demanda'
                ELSE 'diario'
            END
            """
        )
    )

    op.alter_column("operational_module_items", "frequencia_tipo", server_default=None)


def downgrade() -> None:
    op.drop_column("operational_module_items", "dia_mes")
    op.drop_column("operational_module_items", "dia_semana")
    op.drop_column("operational_module_items", "frequencia_tipo")
