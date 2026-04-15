"""add poder penetracao operational module

Revision ID: 20260413_0008
Revises: 20260413_0007
Create Date: 2026-04-13 07:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0008"
down_revision: str | None = "20260413_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "poder_penetracao_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("semana_referencia", sa.String(length=20), nullable=False),
        sa.Column("modelo", sa.String(length=120), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("cis", sa.String(length=120), nullable=True),
        sa.Column("velocidade", sa.String(length=80), nullable=True),
        sa.Column("tipo", sa.String(length=80), nullable=True),
        sa.Column("menor_valor", sa.Float(), nullable=True),
        sa.Column("total_pontos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_aprovados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_reprovados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("percentual_aprovacao", sa.Float(), nullable=False, server_default="0"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("acao_corretiva", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="rascunho"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_poder_penetracao_lancamentos_data_referencia", "poder_penetracao_lancamentos", ["data_referencia"])
    op.create_index("ix_poder_penetracao_lancamentos_semana_referencia", "poder_penetracao_lancamentos", ["semana_referencia"])
    op.create_index("ix_poder_penetracao_lancamentos_modelo", "poder_penetracao_lancamentos", ["modelo"])
    op.create_index("ix_poder_penetracao_lancamentos_status", "poder_penetracao_lancamentos", ["status"])
    op.create_index("ix_poder_penetracao_lancamentos_cis", "poder_penetracao_lancamentos", ["cis"])

    op.create_table(
        "poder_penetracao_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lancamento_id",
            sa.Integer(),
            sa.ForeignKey("poder_penetracao_lancamentos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ponto_numero", sa.Integer(), nullable=False),
        sa.Column("valor_medido", sa.Float(), nullable=True),
        sa.Column("aprovado", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lancamento_id", "ponto_numero", name="uq_poder_penetracao_lancamento_ponto"),
    )
    op.create_index("ix_poder_penetracao_itens_lancamento_id", "poder_penetracao_itens", ["lancamento_id"])
    op.create_index("ix_poder_penetracao_itens_ponto_numero", "poder_penetracao_itens", ["ponto_numero"])


def downgrade() -> None:
    op.drop_index("ix_poder_penetracao_itens_ponto_numero", table_name="poder_penetracao_itens")
    op.drop_index("ix_poder_penetracao_itens_lancamento_id", table_name="poder_penetracao_itens")
    op.drop_table("poder_penetracao_itens")
    op.drop_index("ix_poder_penetracao_lancamentos_cis", table_name="poder_penetracao_lancamentos")
    op.drop_index("ix_poder_penetracao_lancamentos_status", table_name="poder_penetracao_lancamentos")
    op.drop_index("ix_poder_penetracao_lancamentos_modelo", table_name="poder_penetracao_lancamentos")
    op.drop_index("ix_poder_penetracao_lancamentos_semana_referencia", table_name="poder_penetracao_lancamentos")
    op.drop_index("ix_poder_penetracao_lancamentos_data_referencia", table_name="poder_penetracao_lancamentos")
    op.drop_table("poder_penetracao_lancamentos")
