"""add PT operation and PT module catalog rows

Revision ID: 20260504_0003
Revises: 20260504_0032
Create Date: 2026-05-04 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260504_0003"
down_revision: str | None = "20260504_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PT_RAW_ROWS = [
    ("Desengraxante 0", "ALCALINIDADE LIVRE", "SGU JPM04", "2,0 a 5,0 mL", 1),
    ("Desengraxante 0", "ALCALINIDADE LIVRE", "SGU JPM04", "2,0 a 5,0 mL", 2),
    ("Desengraxante 0", "pH", "", "10 a 12", 1),
    ("Desengraxante 0", "pH", "", "10 a 12", 2),
    ("Desengraxante 0", "TEMPERATURA DO BANHO", "CICLO AM I005", "36 - 42 C", 1),
    ("Desengraxante 0", "TEMPERATURA DO BANHO", "CICLO AM I005", "36 - 42 C", 2),
    ("Desengraxante 0", "PRESSAO NOS BICOS (RAMPA SPRAY)", "CICLO AM I001 E I014", "0,5 -1,0 bar", 1),
    ("Desengraxante 1", "ALCALINIDADE LIVRE", "SGU JPM04", "2,0 a 5,0 mL", 1),
    ("Desengraxante 1", "ALCALINIDADE LIVRE", "SGU JPM04", "2,0 a 5,0 mL", 2),
    ("Desengraxante 1", "pH", "", "10 a 12", 1),
    ("Desengraxante 1", "pH", "", "10 a 12", 2),
    ("Desengraxante 1", "TEMPERATURA DO BANHO", "CICLO AM I005", "36 - 42 C", 1),
    ("Desengraxante 1", "TEMPERATURA DO BANHO", "CICLO AM I005", "36 - 42 C", 2),
    ("Desengraxante 1", "PRESSAO NOS BICOS (RAMPA SPRAY)", "CICLO AM I001 E I014", "1,0 - 3,0 bar", 1),
    ("Desengraxante 2", "ALCALINIDADE LIVRE", "SGU JPM04", "2,0 a 5,0 mL", 1),
    ("Desengraxante 2", "ALCALINIDADE LIVRE", "SGU JPM04", "2,0 a 5,0 mL", 2),
    ("Desengraxante 2", "pH", "", "10 a 12", 1),
    ("Desengraxante 2", "pH", "", "10 a 12", 2),
    ("Desengraxante 2", "TEMPERATURA DO BANHO", "CICLO AM I005", "36 - 42 C", 1),
    ("Desengraxante 2", "TEMPERATURA DO BANHO", "CICLO AM I005", "36 - 42 C", 2),
    ("Desengraxante 2", "PRESSAO NOS BICOS (RAMPA DE AGITACAO)", "CICLO AM I001 E I014", "0,1-0,5 bar", 1),
    ("Ativacao", "pH", "SGU JPM06", "8 a 10", 1),
    ("Ativacao", "pH", "SGU JPM06", "8 a 10", 2),
    ("Ativacao", "CONCENTRACAO Zn", "SGU JPM06", "2,3 a 4,6 mL", 1),
    ("Ativacao", "CONCENTRACAO Zn", "SGU JPM06", "2,3 a 4,6 mL", 2),
    ("Ativacao", "PRESSAO NOS BICOS (RAMPA SPRAY)", "CICLO AM I001 E I014", "1,0 -2,0 bar", 1),
    ("Ativacao", "PRESSAO NOS BICOS (RAMPA DE AGITACAO)", "CICLO AM I001 E I014", "0,3-0,7 bar", 1),
    ("Fosfatacao", "ACIDEZ LIVRE", "SGU JPM02", "0,7 a 1,2 mL", 1),
    ("Fosfatacao", "ACIDEZ LIVRE", "SGU JPM02", "0,7 a 1,2 mL", 2),
    ("Fosfatacao", "ACIDEZ LIVRE", "SGU JPM02", "0,7 a 1,2 mL", 3),
    ("Fosfatacao", "ACIDEZ LIVRE", "SGU JPM02", "0,7 a 1,2 mL", 4),
    ("Fosfatacao", "ACIDEZ TOTAL", "SGU JPM03", ">17 mL", 1),
    ("Fosfatacao", "ACIDEZ TOTAL", "SGU JPM03", ">17 mL", 2),
    ("Fosfatacao", "ACIDEZ TOTAL", "SGU JPM03", ">17 mL", 3),
    ("Fosfatacao", "ACIDEZ TOTAL", "SGU JPM03", ">17 mL", 4),
    ("Fosfatacao", "ACELERANTE", "SGU JPM01", "2,5 a 5 mL (0,8 a 1,6)", 1),
    ("Fosfatacao", "ACELERANTE", "SGU JPM01", "2,5 a 5 mL (0,8 a 1,6)", 2),
    ("Fosfatacao", "ACELERANTE", "SGU JPM01", "2,5 a 5 mL (0,8 a 1,6)", 3),
    ("Fosfatacao", "ACELERANTE", "SGU JPM01", "2,5 a 5 mL (0,8 a 1,6)", 4),
    ("Fosfatacao", "TEMPERATURA DO BANHO", "CICLO AM I005", "38 a 42 C", 1),
    ("Fosfatacao", "TEMPERATURA DO BANHO", "CICLO AM I005", "38 a 42 C", 2),
    ("Fosfatacao", "TEMPERATURA DO BANHO", "CICLO AM I005", "38 a 42 C", 3),
    ("Fosfatacao", "TEMPERATURA DO BANHO", "CICLO AM I005", "38 a 42 C", 4),
    ("Fosfatacao (STG 6)", "PRESSAO NOS BICOS (RAMPA DE AGITACAO MEIO DO TANQUE)", "", "1,0-3,0 bar", 1),
    ("Fosfatacao (STG 6)", "PRESSAO NOS BICOS (RAMPA DE AGITACAO FUNDO DO TANQUE)", "CICLO AM I001 E I014", "0,1-1,0 bar", 1),
    ("LAVAGEM ESTAGIO 3", "PRESSAO NOS BICOS (RAMPA SPRAY)", "CICLO AM I001 E I014", "1,0 - 2,0 bar", 1),
    ("LAVAGEM ESTAGIO 4", "PRESSAO NOS BICOS (RAMPA SPRAY)", "CICLO AM I001 E I014", "1,0 - 2,0 bar", 1),
    ("LAVAGEM ESTAGIO 4", "PRESSAO NOS BICOS (RAMPA DE AGITACAO)", "CICLO AM I001 E I014", "0,3 - 0,5 bar", 1),
    ("LAVAGEM ESTAGIO 7", "PRESSAO NOS BICOS (RAMPA SPRAY)", "CICLO AM I001 E I014", "1,0-2,0 bar", 1),
    ("LAVAGEM ESTAGIO 7", "pH", "", "5 a 7", 1),
    ("LAVAGEM ESTAGIO 7", "pH", "", "5 a 7", 2),
    ("LAVAGEM ESTAGIO 8", "PRESSAO NOS BICOS (RAMPA SPRAY)", "", "1,0-2,0 bar", 1),
    ("LAVAGEM ESTAGIO 8", "PRESSAO NOS BICOS (RAMPA DE AGITACAO)", "CICLO AM I001 E I014", "0,3-0,7 bar", 1),
    ("LAVAGEM ESTAGIO 8", "PH", "", "5,5 - 7", 1),
    ("LAVAGEM ESTAGIO 8", "PH", "", "5,5 - 7", 2),
    ("LAVAGEM ESTAGIO 10", "PRESSAO NOS BICOS (RAMPA SPRAY)", "CICLO AM I001 E I014", "1,0-2,0 bar", 1),
    ("LAVAGEM ESTAGIO 10", "PRESSAO NOS BICOS (RAMPA DE AGITACAO)", "CICLO AM I001 E I014", "0,3-0,7 bar", 1),
    ("LAVAGEM ESTAGIO 10", "CONDUTIVIDADE", "SGU JPM09", "< 80uS", 1),
    ("LAVAGEM ESTAGIO 10", "CONDUTIVIDADE", "SGU JPM09", "< 80uS", 2),
    ("FOSFATACAO", "PESO FOSFATICO (g/m2)", ".", "1,8 a 4 g/m2", 1),
]


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def _parse_number(token: str) -> float | None:
    text = (token or "").strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _extract_numbers(text: str) -> list[float]:
    numbers = re.findall(r"-?\d+(?:[\.,]\d+)?", text)
    result: list[float] = []
    for n in numbers:
        parsed = _parse_number(n)
        if parsed is not None:
            result.append(parsed)
    return result


def _validation_from_parameter(parametro: str) -> tuple[str, float | None, float | None]:
    text = (parametro or "").strip().lower()
    if not text:
        return ("nenhum", None, None)

    if text.startswith(">"):
        nums = _extract_numbers(text)
        return ("min", nums[0], None) if nums else ("texto", None, None)
    if text.startswith("<"):
        nums = _extract_numbers(text)
        return ("max", None, nums[0]) if nums else ("texto", None, None)

    if " a " in text or " - " in text or "-" in text:
        nums = _extract_numbers(text)
        if len(nums) >= 2:
            lo = min(nums[0], nums[1])
            hi = max(nums[0], nums[1])
            return ("range", lo, hi)

    return ("texto", None, None)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute("SET NAMES utf8mb4")

    if _has_column("operational_shifts", "operation_scope") is False:
        op.add_column(
            "operational_shifts",
            sa.Column("operation_scope", sa.String(length=40), nullable=False, server_default="ed"),
        )
        op.create_index(op.f("ix_operational_shifts_operation_scope"), "operational_shifts", ["operation_scope"], unique=False)
        op.execute("UPDATE operational_shifts SET operation_scope = 'ed' WHERE operation_scope IS NULL OR operation_scope = ''")

    with op.batch_alter_table("operational_shifts") as batch_op:
        try:
            batch_op.drop_constraint("uq_operational_shift_context", type_="unique")
        except Exception:
            pass
        try:
            batch_op.create_unique_constraint("uq_operational_shift_context", ["data_referencia", "turno", "operation_scope"])
        except Exception:
            pass

    items_table = sa.table(
        "operational_module_items",
        sa.column("id", sa.Integer()),
        sa.column("escopo", sa.String()),
        sa.column("modulo", sa.String()),
        sa.column("aba", sa.String()),
        sa.column("module_code", sa.String()),
        sa.column("setor_tipo", sa.String()),
        sa.column("operacao", sa.String()),
        sa.column("controle", sa.String()),
        sa.column("norma", sa.String()),
        sa.column("parametro", sa.String()),
        sa.column("parametro_exibicao", sa.String()),
        sa.column("tipo_validacao", sa.String()),
        sa.column("limite_minimo", sa.Numeric()),
        sa.column("limite_maximo", sa.Numeric()),
        sa.column("ordem", sa.Integer()),
        sa.column("obrigatorio", sa.Boolean()),
        sa.column("ativo", sa.Boolean()),
        sa.column("frequencia", sa.String()),
        sa.column("frequencia_tipo", sa.String()),
        sa.column("numero_coleta", sa.Integer()),
    )

    existing_rows = bind.execute(
        sa.text(
            """
            SELECT operacao, controle, parametro, COALESCE(numero_coleta, 0) AS numero_coleta
            FROM operational_module_items
            WHERE module_code = 'pt'
            """
        )
    ).mappings().all()
    existing_keys = {
        (
            str(row.get("operacao") or "").strip().lower(),
            str(row.get("controle") or "").strip().lower(),
            str(row.get("parametro") or "").strip().lower(),
            int(row.get("numero_coleta") or 0),
        )
        for row in existing_rows
    }

    dedup_source: dict[tuple[str, str, str, int], tuple[str, str, str, str, int]] = {}
    for row in PT_RAW_ROWS:
        operacao, controle, norma, parametro, numero_coleta = row
        key = (operacao.strip().lower(), controle.strip().lower(), parametro.strip().lower(), int(numero_coleta))
        dedup_source[key] = row

    payload: list[dict[str, object]] = []
    ordem = 1
    for row in dedup_source.values():
        operacao, controle, norma, parametro, numero_coleta = row
        key = (operacao.strip().lower(), controle.strip().lower(), parametro.strip().lower(), int(numero_coleta))
        if key in existing_keys:
            continue
        tipo_validacao, limite_minimo, limite_maximo = _validation_from_parameter(parametro)
        payload.append(
            {
                "escopo": "pt",
                "modulo": "pt",
                "aba": "PTED",
                "module_code": "pt",
                "setor_tipo": "PTED",
                "operacao": operacao,
                "controle": controle,
                "norma": norma or None,
                "parametro": parametro,
                "parametro_exibicao": parametro,
                "tipo_validacao": tipo_validacao,
                "limite_minimo": limite_minimo,
                "limite_maximo": limite_maximo,
                "ordem": ordem,
                "obrigatorio": True,
                "ativo": True,
                "frequencia": "DIARIO",
                "frequencia_tipo": "diario",
                "numero_coleta": int(numero_coleta),
            }
        )
        ordem += 1

    if payload:
        op.bulk_insert(items_table, payload)


def downgrade() -> None:
    op.execute("DELETE FROM operational_module_items WHERE module_code = 'pt'")

    with op.batch_alter_table("operational_shifts") as batch_op:
        try:
            batch_op.drop_constraint("uq_operational_shift_context", type_="unique")
        except Exception:
            pass
        try:
            batch_op.create_unique_constraint("uq_operational_shift_context", ["data_referencia", "turno"])
        except Exception:
            pass

    if _has_column("operational_shifts", "operation_scope"):
        try:
            op.drop_index(op.f("ix_operational_shifts_operation_scope"), table_name="operational_shifts")
        except Exception:
            pass
        op.drop_column("operational_shifts", "operation_scope")
