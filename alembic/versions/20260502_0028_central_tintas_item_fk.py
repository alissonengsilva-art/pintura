"""central tintas catalog item link and generic response fields

Revision ID: 20260502_0028
Revises: 20260502_0027
Create Date: 2026-05-02 13:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260502_0028"
down_revision = "20260502_0027"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    table = "central_tintas_itens"

    if not _has_column(table, "operational_module_item_id"):
        op.add_column(table, sa.Column("operational_module_item_id", sa.Integer(), nullable=True))
        op.create_index(op.f("ix_central_tintas_itens_operational_module_item_id"), table, ["operational_module_item_id"], unique=False)
        op.create_foreign_key(
            "fk_central_tintas_itens_operational_module_item_id",
            table,
            "operational_module_items",
            ["operational_module_item_id"],
            ["id"],
            ondelete="SET NULL",
        )

    for col_name, col_type in (
        ("controle", sa.String(length=200)),
        ("parametro", sa.String(length=120)),
        ("valor", sa.String(length=120)),
        ("observacao", sa.Text()),
        ("status", sa.String(length=30)),
    ):
        if not _has_column(table, col_name):
            op.add_column(table, sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    table = "central_tintas_itens"

    for col_name in ("status", "observacao", "valor", "parametro", "controle"):
        if _has_column(table, col_name):
            op.drop_column(table, col_name)

    if _has_column(table, "operational_module_item_id"):
        op.drop_constraint("fk_central_tintas_itens_operational_module_item_id", table, type_="foreignkey")
        op.drop_index(op.f("ix_central_tintas_itens_operational_module_item_id"), table_name=table)
        op.drop_column(table, "operational_module_item_id")
