"""create central_tintas_registros table

Revision ID: 20260502_0030
Revises: 20260502_0029
Create Date: 2026-05-02 20:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260502_0030"
down_revision = "20260502_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "central_tintas_registros",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_hora", sa.DateTime(), nullable=False),
        sa.Column("responsavel", sa.String(length=120), nullable=True),
        sa.Column("turno", sa.String(length=20), nullable=True),
        sa.Column("tinta", sa.String(length=120), nullable=True),
        sa.Column("lote", sa.String(length=80), nullable=True),
        sa.Column("ph", sa.String(length=40), nullable=True),
        sa.Column("viscosidade", sa.String(length=80), nullable=True),
        sa.Column("sujidade", sa.String(length=120), nullable=True),
        sa.Column("acoes_corretivas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(op.f("ix_central_tintas_registros_data_hora"), "central_tintas_registros", ["data_hora"], unique=False)
    op.create_index(op.f("ix_central_tintas_registros_responsavel"), "central_tintas_registros", ["responsavel"], unique=False)
    op.create_index(op.f("ix_central_tintas_registros_turno"), "central_tintas_registros", ["turno"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_central_tintas_registros_turno"), table_name="central_tintas_registros")
    op.drop_index(op.f("ix_central_tintas_registros_responsavel"), table_name="central_tintas_registros")
    op.drop_index(op.f("ix_central_tintas_registros_data_hora"), table_name="central_tintas_registros")
    op.drop_table("central_tintas_registros")
