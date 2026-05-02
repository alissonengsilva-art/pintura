"""sigilatura responses link to operational items

Revision ID: 20260502_0027
Revises: 20260502_0026
Create Date: 2026-05-02 12:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260502_0027"
down_revision = "20260502_0026"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def _add_fk_column(table: str) -> None:
    col = "operational_module_item_id"
    if _has_column(table, col):
        return
    op.add_column(table, sa.Column(col, sa.Integer(), nullable=True))
    op.create_index(op.f(f"ix_{table}_{col}"), table, [col], unique=False)
    op.create_foreign_key(
        f"fk_{table}_{col}",
        table,
        "operational_module_items",
        [col],
        ["id"],
        ondelete="SET NULL",
    )


def _drop_fk_column(table: str) -> None:
    col = "operational_module_item_id"
    if not _has_column(table, col):
        return
    op.drop_constraint(f"fk_{table}_{col}", table, type_="foreignkey")
    op.drop_index(op.f(f"ix_{table}_{col}"), table_name=table)
    op.drop_column(table, col)


def upgrade() -> None:
    for table in (
        "sigilatura_respostas",
        "sigilatura_espessura_pvc",
        "sigilatura_temperatura_forno",
        "sigilatura_escorrimento",
    ):
        _add_fk_column(table)


def downgrade() -> None:
    for table in (
        "sigilatura_escorrimento",
        "sigilatura_temperatura_forno",
        "sigilatura_espessura_pvc",
        "sigilatura_respostas",
    ):
        _drop_fk_column(table)
