from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


VALIDATION_RANGE = "range"
VALIDATION_MIN = "min"
VALIDATION_MAX = "max"
VALIDATION_TEXT = "texto"
VALIDATION_BOOLEAN = "booleano"
VALIDATION_NONE = "nenhum"

VALIDATION_TYPES = {
    VALIDATION_RANGE,
    VALIDATION_MIN,
    VALIDATION_MAX,
    VALIDATION_TEXT,
    VALIDATION_BOOLEAN,
    VALIDATION_NONE,
}

STATUS_NAO_AVALIADO = "NAO_AVALIADO"
STATUS_DENTRO = "DENTRO_DO_ESPERADO"
STATUS_FORA = "FORA_DO_ESPERADO"

STATUS_LABELS = {
    STATUS_NAO_AVALIADO: "Não avaliado",
    STATUS_DENTRO: "Dentro do esperado",
    STATUS_FORA: "Fora do esperado",
}

_NUMBER_PATTERN = re.compile(r"-?\d+(?:[\.,]\d+)?")


@dataclass(frozen=True)
class ValidationResult:
    status: str
    label: str
    fora_padrao: bool | None
    value_number: float | None


def normalize_validation_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "referencia":
        return VALIDATION_TEXT
    if normalized in VALIDATION_TYPES:
        return normalized
    return VALIDATION_NONE


def display_parameter(item: Any) -> str:
    validation_type = normalize_validation_type(getattr(item, "tipo_validacao", None))
    unidade = str(getattr(item, "unidade", "") or "").strip()
    min_value = _to_float(getattr(item, "limite_minimo", None))
    max_value = _to_float(getattr(item, "limite_maximo", None))

    if validation_type == VALIDATION_RANGE and (min_value is not None or max_value is not None):
        min_text = _format_number(min_value) if min_value is not None else "—"
        max_text = _format_number(max_value) if max_value is not None else "—"
        return f"{min_text} - {max_text}{(' ' + unidade) if unidade else ''}".strip()
    if validation_type == VALIDATION_MIN and min_value is not None:
        return f"> {_format_number(min_value)}{(' ' + unidade) if unidade else ''}".strip()
    if validation_type == VALIDATION_MAX and max_value is not None:
        return f"< {_format_number(max_value)}{(' ' + unidade) if unidade else ''}".strip()

    parametro_exibicao = str(getattr(item, "parametro_exibicao", "") or "").strip()
    if parametro_exibicao:
        return parametro_exibicao
    parametro = str(getattr(item, "parametro", "") or "").strip()
    return parametro or "-"


def parse_numeric_value(raw_value: str | None) -> float | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    return _to_float(match.group(0))


def evaluate(
    raw_value: str | None,
    *,
    tipo_validacao: str | None,
    limite_minimo: Any = None,
    limite_maximo: Any = None,
) -> ValidationResult:
    validation_type = normalize_validation_type(tipo_validacao)
    value_number = parse_numeric_value(raw_value)

    if raw_value is None or not str(raw_value).strip():
        return ValidationResult(STATUS_NAO_AVALIADO, STATUS_LABELS[STATUS_NAO_AVALIADO], None, None)

    if validation_type in {VALIDATION_NONE, VALIDATION_TEXT, VALIDATION_BOOLEAN}:
        return ValidationResult(STATUS_DENTRO, STATUS_LABELS[STATUS_DENTRO], False, value_number)

    if value_number is None:
        return ValidationResult(STATUS_NAO_AVALIADO, STATUS_LABELS[STATUS_NAO_AVALIADO], None, None)

    min_value = _to_float(limite_minimo)
    max_value = _to_float(limite_maximo)

    is_within = True
    if validation_type == VALIDATION_RANGE:
        if min_value is not None and value_number < min_value:
            is_within = False
        if max_value is not None and value_number > max_value:
            is_within = False
    elif validation_type == VALIDATION_MIN:
        if min_value is None:
            return ValidationResult(STATUS_NAO_AVALIADO, STATUS_LABELS[STATUS_NAO_AVALIADO], None, value_number)
        is_within = value_number >= min_value
    elif validation_type == VALIDATION_MAX:
        if max_value is None:
            return ValidationResult(STATUS_NAO_AVALIADO, STATUS_LABELS[STATUS_NAO_AVALIADO], None, value_number)
        is_within = value_number <= max_value

    if is_within:
        return ValidationResult(STATUS_DENTRO, STATUS_LABELS[STATUS_DENTRO], False, value_number)
    return ValidationResult(STATUS_FORA, STATUS_LABELS[STATUS_FORA], True, value_number)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        raw = str(value).strip()
        if not raw:
            return None
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", ".")
        return float(Decimal(raw))
    except (InvalidOperation, ValueError):
        return None


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
