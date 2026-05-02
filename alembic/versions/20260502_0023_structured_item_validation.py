"""structured item validation fields

Revision ID: 20260502_0023
Revises: 20260428_0022
Create Date: 2026-05-02 10:30:00.000000
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260502_0023"
down_revision = "20260428_0022"
branch_labels = None
depends_on = None


_RANGE_PATTERN = re.compile(r"(-?\d+(?:[\.,]\d+)?)\s*[-–]\s*(-?\d+(?:[\.,]\d+)?)")
_MIN_PATTERN = re.compile(r"(?:>=|>|≥)\s*(-?\d+(?:[\.,]\d+)?)")
_MAX_PATTERN = re.compile(r"(?:<=|<|≤)\s*(-?\d+(?:[\.,]\d+)?)")
_UNIT_PATTERN = re.compile(r"[A-Za-z°ºµ%/]+")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("operational_module_items")}

    if "tipo_validacao" not in existing_columns:
        op.add_column("operational_module_items", sa.Column("tipo_validacao", sa.String(length=30), nullable=True))
    if "limite_minimo" not in existing_columns:
        op.add_column("operational_module_items", sa.Column("limite_minimo", sa.Numeric(precision=12, scale=4), nullable=True))
    if "limite_maximo" not in existing_columns:
        op.add_column("operational_module_items", sa.Column("limite_maximo", sa.Numeric(precision=12, scale=4), nullable=True))
    if "parametro_exibicao" not in existing_columns:
        op.add_column("operational_module_items", sa.Column("parametro_exibicao", sa.String(length=120), nullable=True))

    metadata = sa.MetaData()
    items = sa.Table(
        "operational_module_items",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parametro", sa.String(length=150)),
        sa.Column("unidade", sa.String(length=40)),
        sa.Column("valor_min", sa.Float()),
        sa.Column("valor_max", sa.Float()),
        sa.Column("tipo_validacao", sa.String(length=30)),
        sa.Column("limite_minimo", sa.Numeric(12, 4)),
        sa.Column("limite_maximo", sa.Numeric(12, 4)),
        sa.Column("parametro_exibicao", sa.String(length=120)),
    )

    rows = list(bind.execute(sa.select(items.c.id, items.c.parametro, items.c.unidade, items.c.valor_min, items.c.valor_max)))
    for row in rows:
        parametro = str(row.parametro or "").strip()
        parsed = _parse_parameter(parametro)
        unidade = parsed["unidade"] or (str(row.unidade or "").strip() or None)
        min_value = parsed["min"] if parsed["min"] is not None else row.valor_min
        max_value = parsed["max"] if parsed["max"] is not None else row.valor_max

        if parsed["tipo_validacao"] == "nenhum" and (row.valor_min is not None or row.valor_max is not None):
            if row.valor_min is not None and row.valor_max is not None:
                parsed["tipo_validacao"] = "range"
            elif row.valor_min is not None:
                parsed["tipo_validacao"] = "min"
            elif row.valor_max is not None:
                parsed["tipo_validacao"] = "max"

        bind.execute(
            items.update()
            .where(items.c.id == row.id)
            .values(
                tipo_validacao=parsed["tipo_validacao"],
                limite_minimo=min_value,
                limite_maximo=max_value,
                unidade=unidade,
                parametro_exibicao=parametro or None,
            )
        )

    bind.execute(
        sa.text(
            """
            UPDATE operational_module_items
            SET tipo_validacao = 'nenhum'
            WHERE tipo_validacao IS NULL OR tipo_validacao = ''
            """
        )
    )
    op.alter_column("operational_module_items", "tipo_validacao", existing_type=sa.String(length=30), nullable=False, server_default="nenhum")
    op.alter_column("operational_module_items", "tipo_validacao", existing_type=sa.String(length=30), server_default=None)


def downgrade() -> None:
    op.drop_column("operational_module_items", "parametro_exibicao")
    op.drop_column("operational_module_items", "limite_maximo")
    op.drop_column("operational_module_items", "limite_minimo")
    op.drop_column("operational_module_items", "tipo_validacao")


def _parse_parameter(parametro: str) -> dict[str, object | None]:
    if not parametro:
        return {"tipo_validacao": "nenhum", "min": None, "max": None, "unidade": None}

    unit = _extract_unit(parametro)
    range_match = _RANGE_PATTERN.search(parametro)
    if range_match:
        start = _to_float(range_match.group(1))
        end = _to_float(range_match.group(2))
        if start is not None and end is not None:
            return {
                "tipo_validacao": "range",
                "min": min(start, end),
                "max": max(start, end),
                "unidade": unit,
            }

    min_match = _MIN_PATTERN.search(parametro)
    if min_match:
        limit = _to_float(min_match.group(1))
        return {"tipo_validacao": "min", "min": limit, "max": None, "unidade": unit}

    max_match = _MAX_PATTERN.search(parametro)
    if max_match:
        limit = _to_float(max_match.group(1))
        return {"tipo_validacao": "max", "min": None, "max": limit, "unidade": unit}

    return {"tipo_validacao": "texto", "min": None, "max": None, "unidade": unit}


def _extract_unit(value: str) -> str | None:
    numbers_removed = _RANGE_PATTERN.sub("", value)
    numbers_removed = _MIN_PATTERN.sub("", numbers_removed)
    numbers_removed = _MAX_PATTERN.sub("", numbers_removed)
    found = _UNIT_PATTERN.findall(numbers_removed)
    if not found:
        return None
    return "".join(found).strip() or None


def _to_float(value: str | None) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", ".")
        return float(Decimal(raw))
    except (InvalidOperation, ValueError):
        return None
