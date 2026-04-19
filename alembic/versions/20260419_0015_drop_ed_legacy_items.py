"""drop legacy ed item table after unification

Revision ID: 20260419_0015
Revises: 20260419_0014
Create Date: 2026-04-19 01:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260419_0015"
down_revision: str | None = "20260419_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_item_ed_fk_if_exists() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for fk in inspector.get_foreign_keys("ed_lancamento_itens"):
        constrained = fk.get("constrained_columns") or []
        if "item_ed_id" in constrained and fk.get("name"):
            op.drop_constraint(fk["name"], "ed_lancamento_itens", type_="foreignkey")


def upgrade() -> None:
    _drop_item_ed_fk_if_exists()
    op.drop_index("ix_ed_lancamento_itens_item_ed_id", table_name="ed_lancamento_itens")
    op.drop_column("ed_lancamento_itens", "item_ed_id")
    op.drop_table("itens_ed")


def downgrade() -> None:
    op.create_table(
        "itens_ed",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operacao_equipamento", sa.String(length=150), nullable=False),
        sa.Column("descricao_controle", sa.String(length=200), nullable=False),
        sa.Column("norma", sa.String(length=120), nullable=True),
        sa.Column("parametro", sa.String(length=150), nullable=True),
        sa.Column("frequencia", sa.String(length=50), nullable=True),
        sa.Column("responsavel_padrao", sa.String(length=120), nullable=True),
        sa.Column("setor_padrao", sa.String(length=120), nullable=True),
        sa.Column("turno_padrao", sa.String(length=80), nullable=True),
        sa.Column("numero_coleta", sa.Integer(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ordem_exibicao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("ed_lancamento_itens", sa.Column("item_ed_id", sa.Integer(), nullable=True))
    op.create_index("ix_ed_lancamento_itens_item_ed_id", "ed_lancamento_itens", ["item_ed_id"])
    op.create_foreign_key(
        None,
        "ed_lancamento_itens",
        "itens_ed",
        ["item_ed_id"],
        ["id"],
    )
