"""initial schema and seed

Revision ID: 20260413_0001
Revises: 
Create Date: 2026-04-13 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.ed_seed_data import DEFAULT_RESPONSAVEIS, DEFAULT_SETORES, DEFAULT_TURNOS, build_seed_items


revision: str = "20260413_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "responsaveis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=120), nullable=False, unique=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "modelos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=120), nullable=False, unique=True),
        sa.Column("codigo", sa.String(length=50), nullable=True, unique=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "setores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=120), nullable=False, unique=True),
        sa.Column("sigla", sa.String(length=30), nullable=True, unique=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "turnos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=80), nullable=False, unique=True),
        sa.Column("codigo", sa.String(length=30), nullable=True, unique=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
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

    responsaveis_table = sa.table(
        "responsaveis",
        sa.column("nome", sa.String()),
        sa.column("descricao", sa.Text()),
        sa.column("ativo", sa.Boolean()),
    )
    setores_table = sa.table(
        "setores",
        sa.column("nome", sa.String()),
        sa.column("sigla", sa.String()),
        sa.column("ativo", sa.Boolean()),
    )
    turnos_table = sa.table(
        "turnos",
        sa.column("nome", sa.String()),
        sa.column("codigo", sa.String()),
        sa.column("ativo", sa.Boolean()),
    )
    itens_table = sa.table(
        "itens_ed",
        sa.column("operacao_equipamento", sa.String()),
        sa.column("descricao_controle", sa.String()),
        sa.column("norma", sa.String()),
        sa.column("parametro", sa.String()),
        sa.column("frequencia", sa.String()),
        sa.column("responsavel_padrao", sa.String()),
        sa.column("setor_padrao", sa.String()),
        sa.column("turno_padrao", sa.String()),
        sa.column("numero_coleta", sa.Integer()),
        sa.column("ativo", sa.Boolean()),
        sa.column("ordem_exibicao", sa.Integer()),
        sa.column("observacao", sa.Text()),
    )

    op.bulk_insert(responsaveis_table, DEFAULT_RESPONSAVEIS)
    op.bulk_insert(setores_table, DEFAULT_SETORES)
    op.bulk_insert(turnos_table, DEFAULT_TURNOS)
    op.bulk_insert(itens_table, build_seed_items())


def downgrade() -> None:
    op.drop_table("itens_ed")
    op.drop_table("turnos")
    op.drop_table("setores")
    op.drop_table("modelos")
    op.drop_table("responsaveis")
