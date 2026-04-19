"""unify ed items into operational module items

Revision ID: 20260419_0014
Revises: 20260419_0013
Create Date: 2026-04-19 01:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260419_0014"
down_revision: str | None = "20260419_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _setor_tipo(row: sa.Row) -> str:
    setor_padrao = str(row.setor_padrao or "").strip().upper()
    responsavel = str(row.responsavel_padrao or "").strip().upper()
    if setor_padrao in {"PT/ED", "PTED"} or "PT/ED" in responsavel or "PTED" in responsavel:
        return "PTED"
    return "LABORATORIO"


def upgrade() -> None:
    op.add_column("operational_module_items", sa.Column("norma", sa.String(length=120), nullable=True))
    op.add_column("operational_module_items", sa.Column("responsavel_padrao", sa.String(length=120), nullable=True))
    op.add_column("operational_module_items", sa.Column("turno_padrao", sa.String(length=80), nullable=True))
    op.add_column("operational_module_items", sa.Column("numero_coleta", sa.Integer(), nullable=True))
    op.add_column("operational_module_items", sa.Column("legacy_item_ed_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_operational_module_items_legacy_item_ed_id"), "operational_module_items", ["legacy_item_ed_id"], unique=False)

    op.add_column("ed_lancamento_itens", sa.Column("operational_module_item_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_ed_lancamento_itens_operational_module_item_id"), "ed_lancamento_itens", ["operational_module_item_id"], unique=False)
    op.create_foreign_key(
        "fk_ed_lancamento_itens_operational_module_item_id",
        "ed_lancamento_itens",
        "operational_module_items",
        ["operational_module_item_id"],
        ["id"],
    )
    op.alter_column("ed_lancamento_itens", "item_ed_id", existing_type=sa.Integer(), nullable=True)

    bind = op.get_bind()
    metadata = sa.MetaData()

    itens_ed = sa.Table("itens_ed", metadata, autoload_with=bind)
    operational_items = sa.Table("operational_module_items", metadata, autoload_with=bind)
    ed_lancamento_itens = sa.Table("ed_lancamento_itens", metadata, autoload_with=bind)

    legacy_rows = bind.execute(sa.select(itens_ed).order_by(itens_ed.c.ordem_exibicao, itens_ed.c.id)).fetchall()
    existing_rows = bind.execute(
        sa.select(operational_items).where(operational_items.c.module_code == "ed")
    ).fetchall()
    existing_map = {
        (row.ordem, row.operacao, row.controle): row
        for row in existing_rows
    }

    for row in legacy_rows:
        payload = {
            "module_code": "ed",
            "setor_tipo": _setor_tipo(row),
            "operacao": row.operacao_equipamento,
            "controle": row.descricao_controle,
            "norma": row.norma,
            "parametro": row.parametro,
            "unidade": None,
            "valor_min": None,
            "valor_max": None,
            "ordem": row.ordem_exibicao,
            "obrigatorio": True,
            "ativo": row.ativo,
            "frequencia": row.frequencia,
            "responsavel_padrao": row.responsavel_padrao,
            "turno_padrao": row.turno_padrao,
            "numero_coleta": row.numero_coleta,
            "legacy_item_ed_id": row.id,
            "observacao": row.observacao,
        }
        existing = existing_map.get((row.ordem_exibicao, row.operacao_equipamento, row.descricao_controle))
        if existing is None:
            bind.execute(sa.insert(operational_items).values(**payload))
        else:
            bind.execute(
                sa.update(operational_items)
                .where(operational_items.c.id == existing.id)
                .values(**payload)
            )

    bind.execute(
        sa.text(
            """
            UPDATE ed_lancamento_itens
            SET operational_module_item_id = (
                SELECT omi.id
                FROM operational_module_items omi
                WHERE omi.module_code = 'ed'
                  AND omi.legacy_item_ed_id = ed_lancamento_itens.item_ed_id
                LIMIT 1
            )
            WHERE item_ed_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_ed_lancamento_itens_operational_module_item_id", "ed_lancamento_itens", type_="foreignkey")
    op.drop_index(op.f("ix_ed_lancamento_itens_operational_module_item_id"), table_name="ed_lancamento_itens")
    op.drop_column("ed_lancamento_itens", "operational_module_item_id")
    op.alter_column("ed_lancamento_itens", "item_ed_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index(op.f("ix_operational_module_items_legacy_item_ed_id"), table_name="operational_module_items")
    op.drop_column("operational_module_items", "legacy_item_ed_id")
    op.drop_column("operational_module_items", "numero_coleta")
    op.drop_column("operational_module_items", "turno_padrao")
    op.drop_column("operational_module_items", "responsavel_padrao")
    op.drop_column("operational_module_items", "norma")
