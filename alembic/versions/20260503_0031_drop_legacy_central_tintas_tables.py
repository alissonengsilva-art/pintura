"""drop legacy central tintas tables

Revision ID: 20260503_0031
Revises: 20260502_0030
Create Date: 2026-05-03 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260503_0031"
down_revision: str | None = "20260502_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    if _has_table("central_tintas_itens"):
        op.drop_table("central_tintas_itens")

    if _has_table("central_tintas_relatorios"):
        op.drop_table("central_tintas_relatorios")


def downgrade() -> None:
    if not _has_table("central_tintas_relatorios"):
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

    if not _has_table("central_tintas_itens"):
        op.create_table(
            "central_tintas_itens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("central_tintas_id", sa.Integer(), sa.ForeignKey("central_tintas_relatorios.id", ondelete="CASCADE"), nullable=False),
            sa.Column("operational_module_item_id", sa.Integer(), sa.ForeignKey("operational_module_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("controle", sa.String(length=200), nullable=True),
            sa.Column("parametro", sa.String(length=120), nullable=True),
            sa.Column("valor", sa.String(length=120), nullable=True),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=True),
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
        op.create_index(op.f("ix_central_tintas_itens_operational_module_item_id"), "central_tintas_itens", ["operational_module_item_id"], unique=False)
