"""add temperatura forno operational module

Revision ID: 20260413_0004
Revises: 20260413_0003
Create Date: 2026-04-13 02:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0004"
down_revision: str | None = "20260413_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "temperatura_forno_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="rascunho"),
        sa.Column("observacoes_gerais", sa.Text(), nullable=True),
        sa.Column("total_zonas_fora_padrao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_temperatura_forno_lancamentos_data_referencia",
        "temperatura_forno_lancamentos",
        ["data_referencia"],
    )
    op.create_index(
        "ix_temperatura_forno_lancamentos_status",
        "temperatura_forno_lancamentos",
        ["status"],
    )

    op.create_table(
        "temperatura_forno_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lancamento_id",
            sa.Integer(),
            sa.ForeignKey("temperatura_forno_lancamentos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("zona_numero", sa.Integer(), nullable=False),
        sa.Column("valor_temperatura", sa.Float(), nullable=True),
        sa.Column("faixa_min", sa.Float(), nullable=False),
        sa.Column("faixa_max", sa.Float(), nullable=False),
        sa.Column("fora_padrao", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lancamento_id", "zona_numero", name="uq_temperatura_forno_lancamento_zona"),
    )
    op.create_index("ix_temperatura_forno_itens_lancamento_id", "temperatura_forno_itens", ["lancamento_id"])
    op.create_index("ix_temperatura_forno_itens_zona_numero", "temperatura_forno_itens", ["zona_numero"])


def downgrade() -> None:
    op.drop_index("ix_temperatura_forno_itens_zona_numero", table_name="temperatura_forno_itens")
    op.drop_index("ix_temperatura_forno_itens_lancamento_id", table_name="temperatura_forno_itens")
    op.drop_table("temperatura_forno_itens")
    op.drop_index("ix_temperatura_forno_lancamentos_status", table_name="temperatura_forno_lancamentos")
    op.drop_index("ix_temperatura_forno_lancamentos_data_referencia", table_name="temperatura_forno_lancamentos")
    op.drop_table("temperatura_forno_lancamentos")
