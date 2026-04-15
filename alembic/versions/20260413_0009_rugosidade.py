"""add rugosidade operational module

Revision ID: 20260413_0009
Revises: 20260413_0008
Create Date: 2026-04-13 08:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0009"
down_revision: str | None = "20260413_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rugosidade_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("sequencia", sa.String(length=40), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="rascunho"),
        sa.Column("observacoes_gerais", sa.Text(), nullable=True),
        sa.Column("total_modelos_fora_padrao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_rugosidade_lancamentos_data_referencia", "rugosidade_lancamentos", ["data_referencia"])
    op.create_index("ix_rugosidade_lancamentos_sequencia", "rugosidade_lancamentos", ["sequencia"])
    op.create_index("ix_rugosidade_lancamentos_status", "rugosidade_lancamentos", ["status"])

    op.create_table(
        "rugosidade_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lancamento_id",
            sa.Integer(),
            sa.ForeignKey("rugosidade_lancamentos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("modelo_codigo", sa.String(length=20), nullable=False),
        sa.Column("valor_rugosidade", sa.Float(), nullable=True),
        sa.Column("limite_referencia", sa.Float(), nullable=False, server_default="14"),
        sa.Column("fora_padrao", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lancamento_id", "modelo_codigo", name="uq_rugosidade_lancamento_modelo"),
    )
    op.create_index("ix_rugosidade_itens_lancamento_id", "rugosidade_itens", ["lancamento_id"])
    op.create_index("ix_rugosidade_itens_modelo_codigo", "rugosidade_itens", ["modelo_codigo"])


def downgrade() -> None:
    op.drop_index("ix_rugosidade_itens_modelo_codigo", table_name="rugosidade_itens")
    op.drop_index("ix_rugosidade_itens_lancamento_id", table_name="rugosidade_itens")
    op.drop_table("rugosidade_itens")
    op.drop_index("ix_rugosidade_lancamentos_status", table_name="rugosidade_lancamentos")
    op.drop_index("ix_rugosidade_lancamentos_sequencia", table_name="rugosidade_lancamentos")
    op.drop_index("ix_rugosidade_lancamentos_data_referencia", table_name="rugosidade_lancamentos")
    op.drop_table("rugosidade_lancamentos")
