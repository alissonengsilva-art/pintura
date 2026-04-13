"""add ed operational launch tables

Revision ID: 20260413_0002
Revises: 20260413_0001
Create Date: 2026-04-13 00:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0002"
down_revision: str | None = "20260413_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ed_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("tipo_dia", sa.String(length=20), nullable=False),
        sa.Column("setor", sa.String(length=120), nullable=False),
        sa.Column("turno", sa.String(length=80), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="rascunho"),
        sa.Column("observacoes_gerais", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ed_lancamentos_data_referencia", "ed_lancamentos", ["data_referencia"])
    op.create_index("ix_ed_lancamentos_status", "ed_lancamentos", ["status"])
    op.create_index("ix_ed_lancamentos_setor_turno", "ed_lancamentos", ["setor", "turno"])

    op.create_table(
        "ed_lancamento_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lancamento_id", sa.Integer(), sa.ForeignKey("ed_lancamentos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_ed_id", sa.Integer(), sa.ForeignKey("itens_ed.id"), nullable=False),
        sa.Column("valor_informado", sa.String(length=150), nullable=True),
        sa.Column("observacao_item", sa.Text(), nullable=True),
        sa.Column("fora_parametro", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ed_lancamento_itens_lancamento_id", "ed_lancamento_itens", ["lancamento_id"])
    op.create_index("ix_ed_lancamento_itens_item_ed_id", "ed_lancamento_itens", ["item_ed_id"])


def downgrade() -> None:
    op.drop_index("ix_ed_lancamento_itens_item_ed_id", table_name="ed_lancamento_itens")
    op.drop_index("ix_ed_lancamento_itens_lancamento_id", table_name="ed_lancamento_itens")
    op.drop_table("ed_lancamento_itens")
    op.drop_index("ix_ed_lancamentos_setor_turno", table_name="ed_lancamentos")
    op.drop_index("ix_ed_lancamentos_status", table_name="ed_lancamentos")
    op.drop_index("ix_ed_lancamentos_data_referencia", table_name="ed_lancamentos")
    op.drop_table("ed_lancamentos")
