"""add tensao retificadores operational module

Revision ID: 20260413_0005
Revises: 20260413_0004
Create Date: 2026-04-13 03:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0005"
down_revision: str | None = "20260413_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tensao_retificadores_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("turno", sa.String(length=80), nullable=False),
        sa.Column("modelo", sa.String(length=120), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="rascunho"),
        sa.Column("observacoes_gerais", sa.Text(), nullable=True),
        sa.Column("total_zonas_fora_padrao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_tensao_retificadores_lancamentos_data_referencia",
        "tensao_retificadores_lancamentos",
        ["data_referencia"],
    )
    op.create_index(
        "ix_tensao_retificadores_lancamentos_turno",
        "tensao_retificadores_lancamentos",
        ["turno"],
    )
    op.create_index(
        "ix_tensao_retificadores_lancamentos_modelo",
        "tensao_retificadores_lancamentos",
        ["modelo"],
    )
    op.create_index(
        "ix_tensao_retificadores_lancamentos_status",
        "tensao_retificadores_lancamentos",
        ["status"],
    )

    op.create_table(
        "tensao_retificadores_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lancamento_id",
            sa.Integer(),
            sa.ForeignKey("tensao_retificadores_lancamentos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("zona_numero", sa.Integer(), nullable=False),
        sa.Column("valor_tensao", sa.Float(), nullable=True),
        sa.Column("fora_padrao", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lancamento_id", "zona_numero", name="uq_tensao_retificadores_lancamento_zona"),
    )
    op.create_index("ix_tensao_retificadores_itens_lancamento_id", "tensao_retificadores_itens", ["lancamento_id"])
    op.create_index("ix_tensao_retificadores_itens_zona_numero", "tensao_retificadores_itens", ["zona_numero"])


def downgrade() -> None:
    op.drop_index("ix_tensao_retificadores_itens_zona_numero", table_name="tensao_retificadores_itens")
    op.drop_index("ix_tensao_retificadores_itens_lancamento_id", table_name="tensao_retificadores_itens")
    op.drop_table("tensao_retificadores_itens")
    op.drop_index("ix_tensao_retificadores_lancamentos_status", table_name="tensao_retificadores_lancamentos")
    op.drop_index("ix_tensao_retificadores_lancamentos_modelo", table_name="tensao_retificadores_lancamentos")
    op.drop_index("ix_tensao_retificadores_lancamentos_turno", table_name="tensao_retificadores_lancamentos")
    op.drop_index("ix_tensao_retificadores_lancamentos_data_referencia", table_name="tensao_retificadores_lancamentos")
    op.drop_table("tensao_retificadores_lancamentos")
