"""operational module items

Revision ID: 20260419_0012
Revises: 20260417_0011
Create Date: 2026-04-19 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.operational_module_seed import build_operational_module_seed_items


revision: str = "20260419_0012"
down_revision: str | None = "20260417_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_module_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_code", sa.String(length=80), nullable=False),
        sa.Column("setor_tipo", sa.String(length=20), nullable=False),
        sa.Column("operacao", sa.String(length=150), nullable=True),
        sa.Column("controle", sa.String(length=200), nullable=False),
        sa.Column("parametro", sa.String(length=150), nullable=True),
        sa.Column("unidade", sa.String(length=40), nullable=True),
        sa.Column("valor_min", sa.Float(), nullable=True),
        sa.Column("valor_max", sa.Float(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("obrigatorio", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("frequencia", sa.String(length=50), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_operational_module_items_module_code"), "operational_module_items", ["module_code"], unique=False)
    op.create_index(op.f("ix_operational_module_items_setor_tipo"), "operational_module_items", ["setor_tipo"], unique=False)
    op.create_index(op.f("ix_operational_module_items_ordem"), "operational_module_items", ["ordem"], unique=False)
    op.create_index(op.f("ix_operational_module_items_ativo"), "operational_module_items", ["ativo"], unique=False)

    items_table = sa.table(
        "operational_module_items",
        sa.column("module_code", sa.String()),
        sa.column("setor_tipo", sa.String()),
        sa.column("operacao", sa.String()),
        sa.column("controle", sa.String()),
        sa.column("parametro", sa.String()),
        sa.column("unidade", sa.String()),
        sa.column("valor_min", sa.Float()),
        sa.column("valor_max", sa.Float()),
        sa.column("ordem", sa.Integer()),
        sa.column("obrigatorio", sa.Boolean()),
        sa.column("ativo", sa.Boolean()),
        sa.column("frequencia", sa.String()),
        sa.column("observacao", sa.Text()),
    )
    op.bulk_insert(items_table, build_operational_module_seed_items())


def downgrade() -> None:
    op.drop_index(op.f("ix_operational_module_items_ativo"), table_name="operational_module_items")
    op.drop_index(op.f("ix_operational_module_items_ordem"), table_name="operational_module_items")
    op.drop_index(op.f("ix_operational_module_items_setor_tipo"), table_name="operational_module_items")
    op.drop_index(op.f("ix_operational_module_items_module_code"), table_name="operational_module_items")
    op.drop_table("operational_module_items")
