from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    OVERRIDE_STATUS_APPLICABLE,
    OVERRIDE_STATUS_AUTOMATIC,
    OVERRIDE_STATUS_DISPENSED,
    OVERRIDE_STATUS_NOT_APPLICABLE,
    OperationalItemApplicabilityOverride,
)


FREQUENCY_DIARIO = "diario"
FREQUENCY_SEMANAL = "semanal"
FREQUENCY_MENSAL = "mensal"
FREQUENCY_SOB_DEMANDA = "sob_demanda"
OVERRIDE_STATUS_OPTIONS = (
    OVERRIDE_STATUS_AUTOMATIC,
    OVERRIDE_STATUS_APPLICABLE,
    OVERRIDE_STATUS_NOT_APPLICABLE,
    OVERRIDE_STATUS_DISPENSED,
)


def normalize_frequency_type(item: Any) -> str:
    frequencia_tipo = str(getattr(item, "frequencia_tipo", "") or "").strip().lower()
    if frequencia_tipo in {FREQUENCY_DIARIO, FREQUENCY_SEMANAL, FREQUENCY_MENSAL, FREQUENCY_SOB_DEMANDA}:
        return frequencia_tipo

    legacy = str(getattr(item, "frequencia", "") or "").strip().upper()
    if legacy == "SEMANAL":
        return FREQUENCY_SEMANAL
    if legacy == "MENSAL":
        return FREQUENCY_MENSAL
    if legacy in {"SOB_DEMANDA", "SOB DEMANDA"}:
        return FREQUENCY_SOB_DEMANDA
    return FREQUENCY_DIARIO


def is_item_applicable_on_date(item: Any, reference_date: date) -> bool:
    frequency_type = normalize_frequency_type(item)
    if frequency_type == FREQUENCY_DIARIO:
        return True
    if frequency_type == FREQUENCY_SEMANAL:
        stored_day = getattr(item, "dia_semana", None)
        if stored_day == 7:
            stored_day = 6
        return stored_day == reference_date.weekday()
    if frequency_type == FREQUENCY_MENSAL:
        return getattr(item, "dia_mes", None) == reference_date.day
    if frequency_type == FREQUENCY_SOB_DEMANDA:
        return False
    return True


def get_applicability_label(item: Any, reference_date: date) -> str:
    frequency_type = normalize_frequency_type(item)
    if frequency_type == FREQUENCY_SOB_DEMANDA:
        return "Sob demanda"
    if is_item_applicable_on_date(item, reference_date):
        return "Aplicável hoje"
    return "Não aplicável hoje"


def get_applicable_items(items: list[Any], reference_date: date) -> list[Any]:
    return [item for item in items if is_item_applicable_on_date(item, reference_date)]


def get_row_applicability(item: Any, reference_date: date) -> dict[str, Any]:
    return resolve_item_applicability(item, reference_date)


def resolve_item_applicability(
    item: Any,
    reference_date: date,
    override_status: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    frequency_type = normalize_frequency_type(item)
    normalized_override = str(override_status or OVERRIDE_STATUS_AUTOMATIC).strip().lower() or OVERRIDE_STATUS_AUTOMATIC
    if normalized_override not in OVERRIDE_STATUS_OPTIONS:
        normalized_override = OVERRIDE_STATUS_AUTOMATIC

    if normalized_override == OVERRIDE_STATUS_APPLICABLE:
        return {
            "frequency_type": frequency_type,
            "is_applicable": True,
            "applicability_state": OVERRIDE_STATUS_APPLICABLE,
            "applicability_label": "Aplicável neste turno",
            "applicability_source": "override",
            "override_status": OVERRIDE_STATUS_APPLICABLE,
            "override_reason": reason,
            "resolved_status": OVERRIDE_STATUS_APPLICABLE,
            "affects_progress": True,
        }
    if normalized_override == OVERRIDE_STATUS_NOT_APPLICABLE:
        return {
            "frequency_type": frequency_type,
            "is_applicable": False,
            "applicability_state": OVERRIDE_STATUS_NOT_APPLICABLE,
            "applicability_label": "Não aplicável neste turno",
            "applicability_source": "override",
            "override_status": OVERRIDE_STATUS_NOT_APPLICABLE,
            "override_reason": reason,
            "resolved_status": OVERRIDE_STATUS_NOT_APPLICABLE,
            "affects_progress": False,
        }
    if normalized_override == OVERRIDE_STATUS_DISPENSED:
        return {
            "frequency_type": frequency_type,
            "is_applicable": False,
            "applicability_state": OVERRIDE_STATUS_DISPENSED,
            "applicability_label": "Dispensado no turno",
            "applicability_source": "override",
            "override_status": OVERRIDE_STATUS_DISPENSED,
            "override_reason": reason,
            "resolved_status": OVERRIDE_STATUS_DISPENSED,
            "affects_progress": False,
        }

    automatic_applicable = is_item_applicable_on_date(item, reference_date)
    automatic_label = get_applicability_label(item, reference_date)
    resolved_status = OVERRIDE_STATUS_AUTOMATIC if automatic_applicable else "sob_demanda" if frequency_type == FREQUENCY_SOB_DEMANDA else "not_applicable"
    return {
        "frequency_type": frequency_type,
        "is_applicable": automatic_applicable,
        "applicability_state": "applicable" if automatic_applicable else "on_demand" if frequency_type == FREQUENCY_SOB_DEMANDA else "not_applicable",
        "applicability_label": automatic_label,
        "applicability_source": "automatic",
        "override_status": OVERRIDE_STATUS_AUTOMATIC,
        "override_reason": reason,
        "resolved_status": resolved_status,
        "affects_progress": automatic_applicable,
    }


def calculate_row_progress(rows: list[dict[str, Any]]) -> dict[str, Any]:
    applicable_rows = [row for row in rows if row.get("is_applicable", True)]
    applicable_total = len(applicable_rows)
    preenchidos = sum(1 for row in applicable_rows if str(row.get("value") or "").strip())
    flags = sum(1 for row in applicable_rows if row.get("flag"))
    not_applicable_count = sum(1 for row in rows if row.get("applicability_state") == "not_applicable")
    on_demand_count = sum(1 for row in rows if row.get("applicability_state") == "on_demand")
    return {
        "total": applicable_total,
        "preenchidos": preenchidos,
        "flag_count": flags,
        "percentual": int(round((preenchidos / applicable_total) * 100)) if applicable_total else 100,
        "has_applicable_items": applicable_total > 0,
        "not_applicable_count": not_applicable_count,
        "on_demand_count": on_demand_count,
        "total_rows": len(rows),
        "status_text": None if applicable_total else "Sem itens aplicáveis hoje",
    }


def get_override_map(session: Session, shift_id: int | None) -> dict[int, OperationalItemApplicabilityOverride]:
    if not shift_id:
        return {}
    overrides = list(
        session.scalars(
            select(OperationalItemApplicabilityOverride).where(OperationalItemApplicabilityOverride.shift_id == shift_id)
        ).all()
    )
    return {override.operational_module_item_id: override for override in overrides}


def save_item_applicability_override(
    session: Session,
    shift_id: int,
    item_id: int,
    override_status: str,
    reason: str | None = None,
) -> OperationalItemApplicabilityOverride | None:
    normalized = str(override_status or OVERRIDE_STATUS_AUTOMATIC).strip().lower()
    if normalized not in OVERRIDE_STATUS_OPTIONS:
        raise ValueError("Override inválido.")

    existing = session.scalars(
        select(OperationalItemApplicabilityOverride)
        .where(OperationalItemApplicabilityOverride.shift_id == shift_id)
        .where(OperationalItemApplicabilityOverride.operational_module_item_id == item_id)
    ).first()

    if normalized == OVERRIDE_STATUS_AUTOMATIC:
        if existing is not None:
            session.delete(existing)
            session.commit()
        return None

    if existing is None:
        existing = OperationalItemApplicabilityOverride(
            shift_id=shift_id,
            operational_module_item_id=item_id,
            override_status=normalized,
            reason=reason,
        )
        session.add(existing)
    else:
        existing.override_status = normalized
        existing.reason = reason
    session.commit()
    session.refresh(existing)
    return existing
