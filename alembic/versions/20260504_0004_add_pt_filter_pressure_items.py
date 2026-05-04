"""add PT filter pressure module items

Revision ID: 20260504_0004
Revises: 20260504_0003
Create Date: 2026-05-04 15:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260504_0004"
down_revision: str | None = "20260504_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ITEMS = [f"FILTRO {idx}" for idx in range(1, 11)]


def upgrade() -> None:
    bind = op.get_bind()

    existing = bind.execute(
        sa.text(
            """
            SELECT lower(trim(coalesce(controle, ''))) AS controle_key
            FROM operational_module_items
            WHERE module_code = 'pressao-filtros-pt'
            """
        )
    ).mappings().all()
    existing_keys = {str(row.get("controle_key") or "") for row in existing}

    table = sa.table(
        "operational_module_items",
        sa.column("escopo", sa.String()),
        sa.column("modulo", sa.String()),
        sa.column("aba", sa.String()),
        sa.column("module_code", sa.String()),
        sa.column("setor_tipo", sa.String()),
        sa.column("operacao", sa.String()),
        sa.column("controle", sa.String()),
        sa.column("parametro", sa.String()),
        sa.column("parametro_exibicao", sa.String()),
        sa.column("tipo_validacao", sa.String()),
        sa.column("ordem", sa.Integer()),
        sa.column("obrigatorio", sa.Boolean()),
        sa.column("ativo", sa.Boolean()),
        sa.column("frequencia", sa.String()),
        sa.column("frequencia_tipo", sa.String()),
    )

    payload: list[dict[str, object]] = []
    for ordem, label in enumerate(ITEMS, start=1):
        key = label.strip().lower()
        if key in existing_keys:
            continue
        payload.append(
            {
                "escopo": "pt",
                "modulo": "pressao-filtros-pt",
                "aba": "PTED",
                "module_code": "pressao-filtros-pt",
                "setor_tipo": "PTED",
                "operacao": "PRESSAO NOS FILTROS",
                "controle": label,
                "parametro": None,
                "parametro_exibicao": None,
                "tipo_validacao": "nenhum",
                "ordem": ordem,
                "obrigatorio": True,
                "ativo": True,
                "frequencia": "DIARIO",
                "frequencia_tipo": "diario",
            }
        )

    if payload:
        op.bulk_insert(table, payload)


def downgrade() -> None:
    op.execute("DELETE FROM operational_module_items WHERE module_code = 'pressao-filtros-pt'")
