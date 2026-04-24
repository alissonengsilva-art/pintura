from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import OperationalModuleItem


SECTOR_BOTH = "AMBOS"
FREQUENCY_DIARIO = "diario"
FREQUENCY_SEMANAL = "semanal"
FREQUENCY_MENSAL = "mensal"
FREQUENCY_SOB_DEMANDA = "sob_demanda"
FREQUENCY_TYPES = (
    FREQUENCY_DIARIO,
    FREQUENCY_SEMANAL,
    FREQUENCY_MENSAL,
    FREQUENCY_SOB_DEMANDA,
)
FREQUENCY_OPTIONS = [
    {"value": FREQUENCY_DIARIO, "label": "diario"},
    {"value": FREQUENCY_SEMANAL, "label": "semanal"},
    {"value": FREQUENCY_MENSAL, "label": "mensal"},
    {"value": FREQUENCY_SOB_DEMANDA, "label": "sob_demanda"},
]
WEEKDAY_OPTIONS = [
    {"value": 0, "label": "Segunda"},
    {"value": 1, "label": "Ter\u00e7a"},
    {"value": 2, "label": "Quarta"},
    {"value": 3, "label": "Quinta"},
    {"value": 4, "label": "Sexta"},
    {"value": 5, "label": "S\u00e1bado"},
    {"value": 6, "label": "Domingo"},
]
SETOR_LABELS = {
    "PTED": "PT/ED",
    "LABORATORIO": "Laborat\u00f3rio",
    SECTOR_BOTH: "Ambos",
}


def get_items_ordered(session: Session, module_code: str) -> list[OperationalModuleItem]:
    return list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )


def get_active_items(session: Session, module_code: str) -> list[OperationalModuleItem]:
    return list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .where(OperationalModuleItem.ativo.is_(True))
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )


def get_items_by_module(session: Session, module_code: str) -> list[OperationalModuleItem]:
    return get_active_items(session, module_code)


def get_items_by_module_and_setor(session: Session, module_code: str, setor: str) -> list[OperationalModuleItem]:
    return list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .where(OperationalModuleItem.ativo.is_(True))
            .where(or_(OperationalModuleItem.setor_tipo == setor, OperationalModuleItem.setor_tipo == SECTOR_BOTH))
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )


def get_item_map_by_legacy_ed_id(session: Session) -> dict[int, OperationalModuleItem]:
    items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "ed")
            .where(OperationalModuleItem.legacy_item_ed_id.is_not(None))
        ).all()
    )
    return {int(item.legacy_item_ed_id): item for item in items if item.legacy_item_ed_id is not None}


def list_frequency_modules() -> list[dict[str, str]]:
    from app.services.operational_module_service import MODULE_CONFIGS

    return [
        {"id": config.code, "code": config.code, "title": config.title}
        for config in MODULE_CONFIGS.values()
    ]


def get_itens_por_modulo(session: Session, modulo_id: str) -> list[dict[str, object | None]]:
    items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == modulo_id)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )
    grouped_items = _group_frequency_items(items)
    return [
        {
            "id": group[0].id,
            "nome": _item_display_name(group[0]),
            "responsavel": _item_sector_label(group[0]),
            "frequencia_tipo": group[0].frequencia_tipo or FREQUENCY_DIARIO,
            "dia_semana": _normalize_weekday(group[0].dia_semana),
            "dia_mes": group[0].dia_mes,
        }
        for group in grouped_items
    ]


def atualizar_frequencia_item(session: Session, item_id: int, payload: dict[str, object | None]) -> OperationalModuleItem:
    item = session.get(OperationalModuleItem, item_id)
    if item is None:
        raise ValueError("Item não encontrado.")

    frequencia_tipo = str(payload.get("frequencia_tipo") or "").strip().lower()
    if frequencia_tipo not in FREQUENCY_TYPES:
        raise ValueError("Frequência inválida.")

    dia_semana = _normalize_weekday(_normalize_nullable_int(payload.get("dia_semana")))
    dia_mes = _normalize_nullable_int(payload.get("dia_mes"))

    if frequencia_tipo == FREQUENCY_SEMANAL:
        if dia_semana is None or not 0 <= dia_semana <= 6:
            raise ValueError("Dia da semana inválido.")
        dia_mes = None
    elif frequencia_tipo == FREQUENCY_MENSAL:
        if dia_mes is None or not 1 <= dia_mes <= 31:
            raise ValueError("Dia do mês inválido.")
        dia_semana = None
    else:
        dia_semana = None
        dia_mes = None

    siblings = _find_frequency_siblings(session, item)
    updated_at = datetime.now(UTC).replace(tzinfo=None)
    for sibling in siblings:
        sibling.frequencia_tipo = frequencia_tipo
        sibling.dia_semana = dia_semana
        sibling.dia_mes = dia_mes
        sibling.updated_at = updated_at
    session.commit()
    session.refresh(item)
    return item


def _item_display_name(item: OperationalModuleItem) -> str:
    operacao = str(item.operacao or "").strip()
    controle = str(item.controle or "").strip()
    if operacao and operacao.lower() != controle.lower():
        return f"{operacao} · {controle}"
    return controle or f"Item {item.id}"


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


def _item_sector_label(item: OperationalModuleItem) -> str:
    if item.setor_tipo == SECTOR_BOTH:
        return "PT/ED e Laboratorio"
    return SETOR_LABELS.get(item.setor_tipo, item.setor_tipo or "-")


def _group_frequency_items(items: list[OperationalModuleItem]) -> list[list[OperationalModuleItem]]:
    grouped: dict[tuple[str, str, str, str], list[OperationalModuleItem]] = {}
    ordered_groups: list[list[OperationalModuleItem]] = []
    for item in items:
        key = _frequency_group_key(item)
        group = grouped.get(key)
        if group is None:
            group = []
            grouped[key] = group
            ordered_groups.append(group)
        group.append(item)
    return ordered_groups


def _find_frequency_siblings(session: Session, item: OperationalModuleItem) -> list[OperationalModuleItem]:
    items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == item.module_code)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )
    key = _frequency_group_key(item)
    siblings = [candidate for candidate in items if _frequency_group_key(candidate) == key]
    return siblings or [item]


def _frequency_group_key(item: OperationalModuleItem) -> tuple[str, str, str, str]:
    return (
        str(item.module_code or "").strip().lower(),
        str(item.setor_tipo or "").strip().upper(),
        str(item.operacao or "").strip().lower(),
        str(item.controle or "").strip().lower(),
    )
