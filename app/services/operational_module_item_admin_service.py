from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OperationalModuleItem
from app.services import operational_module_item_service
from app.services.operational_module_service import MODULE_CONFIGS


SECTOR_OPTIONS = [
    {"value": "PTED", "label": "PT/ED"},
    {"value": "LABORATORIO", "label": "Laboratório"},
    {"value": "AMBOS", "label": "PT/ED e Laboratório"},
]


@dataclass(frozen=True)
class ModuleAdminContext:
    module_code: str
    module_title: str
    rows: list[dict[str, object | None]]


def list_modules() -> list[dict[str, str]]:
    return operational_module_item_service.list_frequency_modules()


def build_module_context(session: Session, module_code: str) -> ModuleAdminContext:
    if module_code not in MODULE_CONFIGS:
        raise ValueError("Modulo invalido.")

    items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )
    groups = _group_items(items)
    rows = [_serialize_group(group) for group in groups]
    return ModuleAdminContext(
        module_code=module_code,
        module_title=MODULE_CONFIGS[module_code].title,
        rows=rows,
    )


def save_module_batch(session: Session, module_code: str, payload: dict[str, object]) -> dict[str, int]:
    if module_code not in MODULE_CONFIGS:
        raise ValueError("Modulo invalido.")

    existing_items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )
    grouped_items = _group_items(existing_items)
    groups_by_representative_id = {group[0].id: group for group in grouped_items if group}

    deleted_count = 0
    deleted_ids = {_normalize_nullable_int(value) for value in (payload.get("delete_ids") or [])}
    for item_id in deleted_ids:
        if item_id is None:
            continue
        group = groups_by_representative_id.get(item_id)
        if not group:
            continue
        for item in group:
            session.delete(item)
            deleted_count += 1

    updated_count = 0
    created_count = 0
    for raw_row in payload.get("rows") or []:
        if not isinstance(raw_row, dict):
            continue
        row_id = _normalize_nullable_int(raw_row.get("id"))
        group = groups_by_representative_id.get(row_id) if row_id is not None else None
        normalized = _normalize_row_payload(module_code, raw_row, existing_item=group[0] if group else None)
        if group:
            for item in group:
                _apply_row_payload(item, normalized)
                updated_count += 1
            continue

        item = OperationalModuleItem(**normalized)
        session.add(item)
        created_count += 1

    session.commit()
    return {
        "updated_count": updated_count,
        "created_count": created_count,
        "deleted_count": deleted_count,
    }


def delete_item_group(session: Session, item_id: int) -> bool:
    item = session.get(OperationalModuleItem, item_id)
    if item is None:
        return False

    items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == item.module_code)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )
    target_key = _group_key(item)
    deleted = False
    for candidate in items:
        if _group_key(candidate) == target_key:
            session.delete(candidate)
            deleted = True
    if deleted:
        session.commit()
    return deleted


def _serialize_group(group: list[OperationalModuleItem]) -> dict[str, object | None]:
    item = group[0]
    return {
        "id": item.id,
        "controle": item.controle,
        "operacao": item.operacao,
        "setor_tipo": item.setor_tipo,
        "setor_label": operational_module_item_service.SETOR_LABELS.get(item.setor_tipo, item.setor_tipo),
        "frequencia_tipo": item.frequencia_tipo or operational_module_item_service.FREQUENCY_DIARIO,
        "dia_semana": _normalize_weekday(item.dia_semana),
        "dia_mes": item.dia_mes,
        "ordem": item.ordem,
        "ativo": bool(item.ativo),
    }


def _group_items(items: list[OperationalModuleItem]) -> list[list[OperationalModuleItem]]:
    grouped: dict[tuple[str, str, str, str], list[OperationalModuleItem]] = {}
    ordered_groups: list[list[OperationalModuleItem]] = []
    for item in items:
        key = _group_key(item)
        group = grouped.get(key)
        if group is None:
            group = []
            grouped[key] = group
            ordered_groups.append(group)
        group.append(item)
    return ordered_groups


def _group_key(item: OperationalModuleItem) -> tuple[str, str, str, str]:
    return (
        str(item.module_code or "").strip().lower(),
        str(item.setor_tipo or "").strip().upper(),
        str(item.operacao or "").strip().lower(),
        str(item.controle or "").strip().lower(),
    )


def _normalize_row_payload(
    module_code: str,
    payload: dict[str, object],
    *,
    existing_item: OperationalModuleItem | None = None,
) -> dict[str, object | None]:
    controle = str(payload.get("controle") or "").strip()
    if not controle:
        raise ValueError("Informe o nome do item.")

    setor_tipo = str(payload.get("setor_tipo") or "").strip().upper()
    if setor_tipo not in {option["value"] for option in SECTOR_OPTIONS}:
        raise ValueError("Setor invalido.")

    frequencia_tipo = str(payload.get("frequencia_tipo") or "").strip().lower()
    if frequencia_tipo not in operational_module_item_service.FREQUENCY_TYPES:
        raise ValueError("Frequencia invalida.")

    dia_semana = _normalize_weekday(_normalize_nullable_int(payload.get("dia_semana")))
    dia_mes = _normalize_nullable_int(payload.get("dia_mes"))
    if existing_item is not None:
        if dia_semana is None:
            dia_semana = _normalize_weekday(existing_item.dia_semana)
        if dia_mes is None:
            dia_mes = existing_item.dia_mes

    if frequencia_tipo == operational_module_item_service.FREQUENCY_SEMANAL:
        if dia_semana is None and existing_item is not None:
            # Legacy records may have weekly frequency without weekday configured.
            # Default to Monday so batch updates do not fail unexpectedly.
            dia_semana = 0
        if dia_semana is None or not 0 <= dia_semana <= 6:
            raise ValueError("Dia da semana invalido.")
        dia_mes = None
    elif frequencia_tipo == operational_module_item_service.FREQUENCY_MENSAL:
        if dia_mes is None or not 1 <= dia_mes <= 31:
            raise ValueError("Dia do mes invalido.")
        dia_semana = None
    else:
        dia_semana = None
        dia_mes = None

    return {
        "module_code": module_code,
        "controle": controle,
        "operacao": str(payload.get("operacao") or "").strip() or None,
        "setor_tipo": setor_tipo,
        "frequencia_tipo": frequencia_tipo,
        "dia_semana": dia_semana,
        "dia_mes": dia_mes,
        "ordem": _normalize_nullable_int(payload.get("ordem")) or 0,
        "ativo": _normalize_bool(payload.get("ativo")),
        "obrigatorio": True,
    }


def _apply_row_payload(item: OperationalModuleItem, payload: dict[str, object | None]) -> None:
    item.controle = str(payload["controle"])
    item.operacao = payload["operacao"]
    item.setor_tipo = str(payload["setor_tipo"])
    item.frequencia_tipo = str(payload["frequencia_tipo"])
    item.dia_semana = payload["dia_semana"]
    item.dia_mes = payload["dia_mes"]
    item.ordem = int(payload["ordem"] or 0)
    item.ativo = bool(payload["ativo"])
    item.obrigatorio = True


def _normalize_nullable_int(value: object | None) -> int | None:
    if value in (None, ""):
        return None
    return int(str(value))


def _normalize_weekday(value: int | None) -> int | None:
    if value is None:
        return None
    # Backward-compatibility: treat legacy Sunday=7 as Sunday=6.
    if value == 7:
        return 6
    return value


def _normalize_bool(value: object | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "on", "yes"}
