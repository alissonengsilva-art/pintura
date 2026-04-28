"""add central tintas flow tables

Revision ID: 20260428_0022
Revises: 20260427_0021
Create Date: 2026-04-28 11:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260428_0022"
down_revision: str | None = "20260427_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "central_tintas_relatorios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_controle", sa.Date(), nullable=False),
        sa.Column("semana", sa.String(length=20), nullable=False),
        sa.Column("mes", sa.String(length=20), nullable=False),
        sa.Column("responsavel", sa.String(length=120), nullable=False),
        sa.Column("turno", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="em_andamento"),
        sa.Column("concluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_central_tintas_relatorios_data_controle"), "central_tintas_relatorios", ["data_controle"], unique=False)
    op.create_index(op.f("ix_central_tintas_relatorios_turno"), "central_tintas_relatorios", ["turno"], unique=False)
    op.create_index(op.f("ix_central_tintas_relatorios_status"), "central_tintas_relatorios", ["status"], unique=False)

    op.create_table(
        "central_tintas_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("central_tintas_id", sa.Integer(), sa.ForeignKey("central_tintas_relatorios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tinta", sa.String(length=120), nullable=True),
        sa.Column("lote", sa.String(length=80), nullable=True),
        sa.Column("ph", sa.String(length=40), nullable=True),
        sa.Column("viscosidade", sa.String(length=80), nullable=True),
        sa.Column("sujidade", sa.String(length=120), nullable=True),
        sa.Column("acoes_corretivas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_central_tintas_itens_central_tintas_id"), "central_tintas_itens", ["central_tintas_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_central_tintas_itens_central_tintas_id"), table_name="central_tintas_itens")
    op.drop_table("central_tintas_itens")

    op.drop_index(op.f("ix_central_tintas_relatorios_status"), table_name="central_tintas_relatorios")
    op.drop_index(op.f("ix_central_tintas_relatorios_turno"), table_name="central_tintas_relatorios")
    op.drop_index(op.f("ix_central_tintas_relatorios_data_controle"), table_name="central_tintas_relatorios")
    op.drop_table("central_tintas_relatorios")
