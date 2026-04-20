"""add setor to responsaveis

Revision ID: 20260420_0016
Revises: 20260419_0015
Create Date: 2026-04-20 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260420_0016"
down_revision: str | None = "20260419_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("responsaveis", sa.Column("setor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_responsaveis_setor_id_setores",
        "responsaveis",
        "setores",
        ["setor_id"],
        ["id"],
    )

    op.execute(
        sa.text(
            """
            UPDATE responsaveis r
            JOIN setores s
              ON s.nome = CASE
                WHEN r.nome = 'Laboratório' THEN 'Laboratório'
                WHEN r.nome = 'Condutor PT/ED' THEN 'PT/ED'
                WHEN r.nome = 'Fornecedor/Laboratório' THEN 'Fornecedor'
                ELSE NULL
              END
            SET r.setor_id = s.id
            WHERE r.setor_id IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_responsaveis_setor_id_setores", "responsaveis", type_="foreignkey")
    op.drop_column("responsaveis", "setor_id")
