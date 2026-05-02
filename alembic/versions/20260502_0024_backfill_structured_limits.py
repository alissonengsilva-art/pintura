"""backfill structured limits from legacy parameter text

Revision ID: 20260502_0024
Revises: 20260502_0023
Create Date: 2026-05-02 12:10:00.000000
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from alembic import op


revision = "20260502_0024"
down_revision = "20260502_0023"
branch_labels = None
depends_on = None

_RANGE_PATTERN = re.compile(r"(-?\d+(?:[\.,]\d+)?)\s*[-–]\s*(-?\d+(?:[\.,]\d+)?)")
_MIN_PATTERN = re.compile(r"(?:>=|>|≥)\s*(-?\d+(?:[\.,]\d+)?)")
_MAX_PATTERN = re.compile(r"(?:<=|<|≤)\s*(-?\d+(?:[\.,]\d+)?)")
_UNIT_PATTERN = re.compile(r"[A-Za-z°ºµ%/]+")


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    items = sa.Table(
        "operational_module_items",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parametro", sa.String(length=150)),
        sa.Column("parametro_exibicao", sa.String(length=120)),
        sa.Column("tipo_validacao", sa.String(length=30)),
        sa.Column("limite_minimo", sa.Numeric(12, 4)),
        sa.Column("limite_maximo", sa.Numeric(12, 4)),
        sa.Column("unidade", sa.String(length=40)),
    )

    rows = list(
        bind.execute(
            sa.select(
                items.c.id,
                items.c.parametro,
                items.c.parametro_exibicao,
                items.c.tipo_validacao,
                items.c.limite_minimo,
                items.c.limite_maximo,
                items.c.unidade,
            )
        )
    )

    for row in rows:
        raw_tipo = str(row.tipo_validacao or "").strip().lower()
        if raw_tipo not in {"", "nenhum", "texto"} and (row.limite_minimo is not None or row.limite_maximo is not None):
            continue

        source = str(row.parametro_exibicao or row.parametro or "").strip()
        if not source:
            continue

        parsed = _parse_parameter(source)
        if parsed["tipo_validacao"] == "nenhum":
            continue

        bind.execute(
            items.update()
            .where(items.c.id == row.id)
            .values(
                tipo_validacao=parsed["tipo_validacao"],
                limite_minimo=parsed["min"],
                limite_maximo=parsed["max"],
                unidade=parsed["unidade"] or (str(row.unidade or "").strip() or None),
            )
        )


def downgrade() -> None:
    # no-op: data backfill is not reverted
    return None


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
        return {"tipo_validacao": "min", "min": _to_float(min_match.group(1)), "max": None, "unidade": unit}

    max_match = _MAX_PATTERN.search(parametro)
    if max_match:
        return {"tipo_validacao": "max", "min": None, "max": _to_float(max_match.group(1)), "unidade": unit}

    return {"tipo_validacao": "texto", "min": None, "max": None, "unidade": unit}


def _extract_unit(value: str) -> str | None:
    stripped = _RANGE_PATTERN.sub("", value)
    stripped = _MIN_PATTERN.sub("", stripped)
    stripped = _MAX_PATTERN.sub("", stripped)
    found = _UNIT_PATTERN.findall(stripped)
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
