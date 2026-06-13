"""repair operational_module_items schema for imported databases

Revision ID: 20260613_0035
Revises: 20260603_0034
Create Date: 2026-06-13 09:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260613_0035"
down_revision: str | None = "20260603_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table_name)}


def _existing_indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    table_name = "operational_module_items"
    existing_columns = _existing_columns(table_name)
    existing_indexes = _existing_indexes(table_name)

    columns_to_add: list[tuple[str, sa.Column]] = [
        ("prioridade", sa.Column("prioridade", sa.String(length=20), nullable=False, server_default="medio")),
        ("dia_semana", sa.Column("dia_semana", sa.Integer(), nullable=True)),
        ("dia_mes", sa.Column("dia_mes", sa.Integer(), nullable=True)),
        ("responsavel_padrao", sa.Column("responsavel_padrao", sa.String(length=120), nullable=True)),
        ("turno_padrao", sa.Column("turno_padrao", sa.String(length=80), nullable=True)),
        ("numero_coleta", sa.Column("numero_coleta", sa.Integer(), nullable=True)),
        ("legacy_item_ed_id", sa.Column("legacy_item_ed_id", sa.Integer(), nullable=True)),
        ("observacao", sa.Column("observacao", sa.Text(), nullable=True)),
        ("created_at", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())),
        ("updated_at", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())),
    ]

    for column_name, column in columns_to_add:
        if column_name not in existing_columns:
            op.add_column(table_name, column)
            existing_columns.add(column_name)

    legacy_item_index = op.f("ix_operational_module_items_legacy_item_ed_id")
    if "legacy_item_ed_id" in existing_columns and legacy_item_index not in existing_indexes:
        op.create_index(legacy_item_index, table_name, ["legacy_item_ed_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE operational_module_items
            SET prioridade = CASE
                WHEN prioridade IS NULL OR TRIM(prioridade) = '' THEN 'medio'
                WHEN LOWER(TRIM(prioridade)) IN ('baixo', 'medio', 'alto') THEN LOWER(TRIM(prioridade))
                ELSE 'medio'
            END
            """
        )
    )


def downgrade() -> None:
    return None
