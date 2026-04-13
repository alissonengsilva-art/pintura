"""add pressure filters operational module

Revision ID: 20260413_0003
Revises: 20260413_0002
Create Date: 2026-04-13 01:15:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0003"
down_revision: str | None = "20260413_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pressao_filtros_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("turno", sa.String(length=80), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="rascunho"),
        sa.Column("observacoes_gerais", sa.Text(), nullable=True),
        sa.Column("total_filtros_em_alarme", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pressao_filtros_lancamentos_data_referencia", "pressao_filtros_lancamentos", ["data_referencia"])
    op.create_index("ix_pressao_filtros_lancamentos_turno", "pressao_filtros_lancamentos", ["turno"])
    op.create_index("ix_pressao_filtros_lancamentos_status", "pressao_filtros_lancamentos", ["status"])

    op.create_table(
        "pressao_filtros_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lancamento_id", sa.Integer(), sa.ForeignKey("pressao_filtros_lancamentos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filtro_numero", sa.Integer(), nullable=False),
        sa.Column("valor_pressao", sa.Float(), nullable=True),
        sa.Column("em_alarme", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lancamento_id", "filtro_numero", name="uq_pressao_filtros_lancamento_filtro"),
    )
    op.create_index("ix_pressao_filtros_itens_lancamento_id", "pressao_filtros_itens", ["lancamento_id"])
    op.create_index("ix_pressao_filtros_itens_filtro_numero", "pressao_filtros_itens", ["filtro_numero"])


def downgrade() -> None:
    op.drop_index("ix_pressao_filtros_itens_filtro_numero", table_name="pressao_filtros_itens")
    op.drop_index("ix_pressao_filtros_itens_lancamento_id", table_name="pressao_filtros_itens")
    op.drop_table("pressao_filtros_itens")
    op.drop_index("ix_pressao_filtros_lancamentos_status", table_name="pressao_filtros_lancamentos")
    op.drop_index("ix_pressao_filtros_lancamentos_turno", table_name="pressao_filtros_lancamentos")
    op.drop_index("ix_pressao_filtros_lancamentos_data_referencia", table_name="pressao_filtros_lancamentos")
    op.drop_table("pressao_filtros_lancamentos")
