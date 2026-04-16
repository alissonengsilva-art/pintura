"""operational module records

Revision ID: 20260416_0010
Revises: 20260413_0009
Create Date: 2026-04-16 08:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260416_0010"
down_revision = "20260413_0009"
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not table_exists("operational_module_records"):
        op.create_table(
            "operational_module_records",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("module_code", sa.String(length=80), nullable=False),
            sa.Column("data_referencia", sa.Date(), nullable=False),
            sa.Column("turno", sa.String(length=80), nullable=True),
            sa.Column("context_key", sa.String(length=255), nullable=False),
            sa.Column("status_geral", sa.String(length=20), nullable=False),
            sa.Column("context_data", sa.JSON(), nullable=False),
            sa.Column("legacy_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("module_code", "context_key", name="uq_operational_module_context"),
        )
        op.create_index(op.f("ix_operational_module_records_module_code"), "operational_module_records", ["module_code"], unique=False)
        op.create_index(op.f("ix_operational_module_records_data_referencia"), "operational_module_records", ["data_referencia"], unique=False)
        op.create_index(op.f("ix_operational_module_records_turno"), "operational_module_records", ["turno"], unique=False)

    if not table_exists("operational_module_sector_records"):
        op.create_table(
            "operational_module_sector_records",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("registro_mestre_id", sa.Integer(), nullable=False),
            sa.Column("setor_tipo", sa.String(length=20), nullable=False),
            sa.Column("responsavel_nome", sa.String(length=120), nullable=True),
            sa.Column("observacoes_setor", sa.Text(), nullable=True),
            sa.Column("status_setor", sa.String(length=20), nullable=False),
            sa.Column("metricas", sa.JSON(), nullable=False),
            sa.Column("iniciado_em", sa.DateTime(), nullable=True),
            sa.Column("atualizado_em", sa.DateTime(), nullable=True),
            sa.Column("concluido_em", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["registro_mestre_id"], ["operational_module_records.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("registro_mestre_id", "setor_tipo", name="uq_operational_module_sector"),
        )
        op.create_index(op.f("ix_operational_module_sector_records_registro_mestre_id"), "operational_module_sector_records", ["registro_mestre_id"], unique=False)

    if not table_exists("operational_module_sector_entries"):
        op.create_table(
            "operational_module_sector_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("setor_registro_id", sa.Integer(), nullable=False),
            sa.Column("referencia", sa.String(length=120), nullable=False),
            sa.Column("ordem", sa.Integer(), nullable=False),
            sa.Column("valor_texto", sa.String(length=255), nullable=True),
            sa.Column("valor_numero", sa.Float(), nullable=True),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.Column("fora_padrao", sa.Boolean(), nullable=True),
            sa.Column("dados", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["setor_registro_id"], ["operational_module_sector_records.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_operational_module_sector_entries_setor_registro_id"), "operational_module_sector_entries", ["setor_registro_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_operational_module_sector_entries_setor_registro_id"), table_name="operational_module_sector_entries")
    op.drop_table("operational_module_sector_entries")
    op.drop_index(op.f("ix_operational_module_sector_records_registro_mestre_id"), table_name="operational_module_sector_records")
    op.drop_table("operational_module_sector_records")
    op.drop_index(op.f("ix_operational_module_records_turno"), table_name="operational_module_records")
    op.drop_index(op.f("ix_operational_module_records_data_referencia"), table_name="operational_module_records")
    op.drop_index(op.f("ix_operational_module_records_module_code"), table_name="operational_module_records")
    op.drop_table("operational_module_records")
