"""add espessura ed operational module

Revision ID: 20260413_0007
Revises: 20260413_0006
Create Date: 2026-04-13 06:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0007"
down_revision: str | None = "20260413_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "espessura_ed_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("turno", sa.String(length=80), nullable=False),
        sa.Column("modelo", sa.String(length=120), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("cis", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="rascunho"),
        sa.Column("observacoes_gerais", sa.Text(), nullable=True),
        sa.Column("total_pontos_preenchidos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_espessura_ed_lancamentos_data_referencia", "espessura_ed_lancamentos", ["data_referencia"])
    op.create_index("ix_espessura_ed_lancamentos_turno", "espessura_ed_lancamentos", ["turno"])
    op.create_index("ix_espessura_ed_lancamentos_modelo", "espessura_ed_lancamentos", ["modelo"])
    op.create_index("ix_espessura_ed_lancamentos_status", "espessura_ed_lancamentos", ["status"])
    op.create_index("ix_espessura_ed_lancamentos_cis", "espessura_ed_lancamentos", ["cis"])

    op.create_table(
        "espessura_ed_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lancamento_id",
            sa.Integer(),
            sa.ForeignKey("espessura_ed_lancamentos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ponto_numero", sa.Integer(), nullable=False),
        sa.Column("valor_espessura", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lancamento_id", "ponto_numero", name="uq_espessura_ed_lancamento_ponto"),
    )
    op.create_index("ix_espessura_ed_itens_lancamento_id", "espessura_ed_itens", ["lancamento_id"])
    op.create_index("ix_espessura_ed_itens_ponto_numero", "espessura_ed_itens", ["ponto_numero"])


def downgrade() -> None:
    op.drop_index("ix_espessura_ed_itens_ponto_numero", table_name="espessura_ed_itens")
    op.drop_index("ix_espessura_ed_itens_lancamento_id", table_name="espessura_ed_itens")
    op.drop_table("espessura_ed_itens")
    op.drop_index("ix_espessura_ed_lancamentos_cis", table_name="espessura_ed_lancamentos")
    op.drop_index("ix_espessura_ed_lancamentos_status", table_name="espessura_ed_lancamentos")
    op.drop_index("ix_espessura_ed_lancamentos_modelo", table_name="espessura_ed_lancamentos")
    op.drop_index("ix_espessura_ed_lancamentos_turno", table_name="espessura_ed_lancamentos")
    op.drop_index("ix_espessura_ed_lancamentos_data_referencia", table_name="espessura_ed_lancamentos")
    op.drop_table("espessura_ed_lancamentos")
