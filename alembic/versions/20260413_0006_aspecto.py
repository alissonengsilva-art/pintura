"""add aspecto operational module

Revision ID: 20260413_0006
Revises: 20260413_0005
Create Date: 2026-04-13 05:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260413_0006"
down_revision: str | None = "20260413_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aspecto_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("turno", sa.String(length=80), nullable=False),
        sa.Column("modelo", sa.String(length=120), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("total_registros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_quantidade", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_aspecto_lancamentos_data_referencia", "aspecto_lancamentos", ["data_referencia"])
    op.create_index("ix_aspecto_lancamentos_turno", "aspecto_lancamentos", ["turno"])
    op.create_index("ix_aspecto_lancamentos_modelo", "aspecto_lancamentos", ["modelo"])

    op.create_table(
        "aspecto_registros",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lancamento_id",
            sa.Integer(),
            sa.ForeignKey("aspecto_lancamentos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("turno", sa.String(length=80), nullable=False),
        sa.Column("modelo", sa.String(length=120), nullable=False),
        sa.Column("responsavel_nome", sa.String(length=120), nullable=False),
        sa.Column("cis", sa.String(length=80), nullable=False),
        sa.Column("cod_posicao", sa.String(length=80), nullable=False),
        sa.Column("local", sa.String(length=120), nullable=False),
        sa.Column("anomalia", sa.String(length=160), nullable=False),
        sa.Column("lado", sa.String(length=40), nullable=False),
        sa.Column("geracao", sa.String(length=80), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_aspecto_registros_lancamento_id", "aspecto_registros", ["lancamento_id"])
    op.create_index("ix_aspecto_registros_data_referencia", "aspecto_registros", ["data_referencia"])
    op.create_index("ix_aspecto_registros_turno", "aspecto_registros", ["turno"])
    op.create_index("ix_aspecto_registros_modelo", "aspecto_registros", ["modelo"])
    op.create_index("ix_aspecto_registros_cis", "aspecto_registros", ["cis"])
    op.create_index("ix_aspecto_registros_anomalia", "aspecto_registros", ["anomalia"])


def downgrade() -> None:
    op.drop_index("ix_aspecto_registros_anomalia", table_name="aspecto_registros")
    op.drop_index("ix_aspecto_registros_cis", table_name="aspecto_registros")
    op.drop_index("ix_aspecto_registros_modelo", table_name="aspecto_registros")
    op.drop_index("ix_aspecto_registros_turno", table_name="aspecto_registros")
    op.drop_index("ix_aspecto_registros_data_referencia", table_name="aspecto_registros")
    op.drop_index("ix_aspecto_registros_lancamento_id", table_name="aspecto_registros")
    op.drop_table("aspecto_registros")
    op.drop_index("ix_aspecto_lancamentos_modelo", table_name="aspecto_lancamentos")
    op.drop_index("ix_aspecto_lancamentos_turno", table_name="aspecto_lancamentos")
    op.drop_index("ix_aspecto_lancamentos_data_referencia", table_name="aspecto_lancamentos")
    op.drop_table("aspecto_lancamentos")
