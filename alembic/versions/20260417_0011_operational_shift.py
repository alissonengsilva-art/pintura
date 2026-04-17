"""operational shift tables

Revision ID: 20260417_0011
Revises: 20260416_0010
Create Date: 2026-04-17 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260417_0011"
down_revision = "20260416_0010"
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # 1. Criar tabela operational_shifts (Turno Operacional - entidade-mãe)
    if not table_exists("operational_shifts"):
        op.create_table(
            "operational_shifts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("data_referencia", sa.Date(), nullable=False),
            sa.Column("turno", sa.String(length=80), nullable=True),
            sa.Column("responsavel_pted", sa.String(length=120), nullable=True),
            sa.Column("responsavel_lab", sa.String(length=120), nullable=True),
            sa.Column("status_geral", sa.String(length=20), nullable=False, server_default="NAO_INICIADO"),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("data_referencia", "turno", name="uq_operational_shift_context"),
        )
        op.create_index(
            op.f("ix_operational_shifts_data_referencia"),
            "operational_shifts",
            ["data_referencia"],
            unique=False,
        )
        op.create_index(
            op.f("ix_operational_shifts_turno"),
            "operational_shifts",
            ["turno"],
            unique=False,
        )

    # 2. Criar tabela operational_shift_modules (previsão de módulos no turno)
    if not table_exists("operational_shift_modules"):
        op.create_table(
            "operational_shift_modules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("shift_id", sa.Integer(), nullable=False),
            sa.Column("module_code", sa.String(length=80), nullable=False),
            sa.Column("previsao", sa.String(length=20), nullable=False, server_default="PREVISTO"),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.Column("atualizado_em", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["shift_id"],
                ["operational_shifts.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("shift_id", "module_code", name="uq_shift_module"),
        )
        op.create_index(
            op.f("ix_operational_shift_modules_shift_id"),
            "operational_shift_modules",
            ["shift_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_operational_shift_modules_module_code"),
            "operational_shift_modules",
            ["module_code"],
            unique=False,
        )

    # 3. Adicionar coluna shift_id na tabela operational_module_records
    if table_exists("operational_module_records"):
        if not column_exists("operational_module_records", "shift_id"):
            op.add_column(
                "operational_module_records",
                sa.Column("shift_id", sa.Integer(), nullable=True),
            )
            op.create_index(
                op.f("ix_operational_module_records_shift_id"),
                "operational_module_records",
                ["shift_id"],
                unique=False,
            )
            op.create_foreign_key(
                "fk_operational_module_records_shift_id",
                "operational_module_records",
                "operational_shifts",
                ["shift_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    # Remove FK e coluna shift_id
    if table_exists("operational_module_records"):
        if column_exists("operational_module_records", "shift_id"):
            op.drop_constraint(
                "fk_operational_module_records_shift_id",
                "operational_module_records",
                type_="foreignkey",
            )
            op.drop_index(
                op.f("ix_operational_module_records_shift_id"),
                table_name="operational_module_records",
            )
            op.drop_column("operational_module_records", "shift_id")

    # Remove tabela operational_shift_modules
    if table_exists("operational_shift_modules"):
        op.drop_table("operational_shift_modules")

    # Remove tabela operational_shifts
    if table_exists("operational_shifts"):
        op.drop_table("operational_shifts")
