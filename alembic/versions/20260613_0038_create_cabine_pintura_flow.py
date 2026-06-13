"""create cabine pintura flow

Revision ID: 20260613_0038
Revises: 20260613_0037
Create Date: 2026-06-13 12:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.services.cabine_pintura_seed import build_cabine_pintura_seed_items

revision = "20260613_0038"
down_revision = "20260613_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("cabine_pintura_relatorios"):
        op.create_table(
            "cabine_pintura_relatorios",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("data_controle", sa.Date(), nullable=False),
            sa.Column("semana", sa.String(length=20), nullable=False),
            sa.Column("mes", sa.String(length=20), nullable=False),
            sa.Column("responsavel", sa.String(length=120), nullable=False),
            sa.Column("turno", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="em_andamento"),
            sa.Column("concluded_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_cabine_pintura_relatorios_data_controle", "cabine_pintura_relatorios", ["data_controle"])
        op.create_index("ix_cabine_pintura_relatorios_turno", "cabine_pintura_relatorios", ["turno"])
        op.create_index("ix_cabine_pintura_relatorios_status", "cabine_pintura_relatorios", ["status"])

    if not inspector.has_table("cabine_pintura_itens"):
        op.create_table(
            "cabine_pintura_itens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("cabine_pintura_id", sa.Integer(), sa.ForeignKey("cabine_pintura_relatorios.id", ondelete="CASCADE"), nullable=False),
            sa.Column("operational_module_item_id", sa.Integer(), sa.ForeignKey("operational_module_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("modulo", sa.String(length=80), nullable=True),
            sa.Column("operacao_equipamento", sa.String(length=160), nullable=True),
            sa.Column("descricao_controle", sa.String(length=220), nullable=True),
            sa.Column("norma", sa.String(length=160), nullable=True),
            sa.Column("parametro", sa.String(length=180), nullable=True),
            sa.Column("valor", sa.String(length=120), nullable=True),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_cabine_pintura_itens_cabine_pintura_id", "cabine_pintura_itens", ["cabine_pintura_id"])
        op.create_index("ix_cabine_pintura_itens_operational_module_item_id", "cabine_pintura_itens", ["operational_module_item_id"])
        op.create_index("ix_cabine_pintura_itens_modulo", "cabine_pintura_itens", ["modulo"])

    metadata = sa.MetaData()
    op_items = sa.Table("operational_module_items", metadata, autoload_with=bind)
    existing_rows = list(
        bind.execute(
            sa.select(
                op_items.c.id,
                op_items.c.aba,
                op_items.c.operacao,
                op_items.c.controle,
                op_items.c.norma,
                op_items.c.parametro,
                op_items.c.parametro_exibicao,
            ).where(op_items.c.module_code == "cabine-pintura")
        ).mappings()
    )
    existing_map = {
        (
            str(row["aba"] or "").strip().lower(),
            str(row["operacao"] or "").strip().lower(),
            str(row["controle"] or "").strip().lower(),
            str(row["norma"] or "").strip().lower(),
            str(row["parametro"] or row["parametro_exibicao"] or "").strip().lower(),
        ): int(row["id"])
        for row in existing_rows
    }

    for ordem, row in enumerate(build_cabine_pintura_seed_items(), start=1):
        key = (
            str(row["aba"] or "").strip().lower(),
            str(row["operacao"] or "").strip().lower(),
            str(row["controle"] or "").strip().lower(),
            str(row["norma"] or "").strip().lower(),
            str(row["parametro"] or row["parametro_exibicao"] or "").strip().lower(),
        )
        values = {**row, "ordem": ordem}
        existing_id = existing_map.get(key)
        if existing_id is None:
            bind.execute(op_items.insert().values(**values))
            continue
        bind.execute(op_items.update().where(op_items.c.id == existing_id).values(**values))


def downgrade() -> None:
    # Fluxo preservado por compatibilidade operacional.
    pass
