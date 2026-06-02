from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import OperationalModuleItem
from app.services import module_parameter_validation
from app.services import operational_module_item_service
from app.services import sigilatura_service


SECTOR_OPTIONS = [
    {"value": "PTED", "label": "PT/ED"},
    {"value": "LABORATORIO", "label": "Laboratório"},
    {"value": "AMBOS", "label": "PT/ED e Laboratório"},
]

VALIDATION_TYPE_OPTIONS = [
    {"value": module_parameter_validation.VALIDATION_RANGE, "label": "range"},
    {"value": module_parameter_validation.VALIDATION_MIN, "label": "min"},
    {"value": module_parameter_validation.VALIDATION_MAX, "label": "max"},
    {"value": module_parameter_validation.VALIDATION_TEXT, "label": "texto"},
    {"value": "referencia", "label": "referência"},
    {"value": module_parameter_validation.VALIDATION_BOOLEAN, "label": "booleano"},
    {"value": module_parameter_validation.VALIDATION_SETPOINT_MARGIN, "label": "Setpoint + margem %"},
    {"value": module_parameter_validation.VALIDATION_NONE, "label": "nenhum"},
]


@dataclass(frozen=True)
class ModuleAdminContext:
    module_code: str
    module_title: str
    rows: list[dict[str, object | None]]


def list_modules() -> list[dict[str, str]]:
    return operational_module_item_service.list_frequency_modules()


def build_module_context(session: Session, module_code: str) -> ModuleAdminContext:
    module_catalog = {item["code"]: item["title"] for item in operational_module_item_service.list_frequency_modules()}
    if module_code not in module_catalog:
        raise ValueError("Modulo invalido.")

    _ensure_sigilatura_module_seed(session, module_code)

    items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .order_by(
                case(
                    (OperationalModuleItem.setor_tipo == "PTED", 0),
                    (OperationalModuleItem.setor_tipo == "LABORATORIO", 1),
                    (OperationalModuleItem.setor_tipo == "AMBOS", 2),
                    else_=3,
                ),
                OperationalModuleItem.ordem,
                OperationalModuleItem.id,
            )
        ).all()
    )
    groups = _group_items(items)
    rows = [_serialize_group(group) for group in groups]
    return ModuleAdminContext(
        module_code=module_code,
        module_title=module_catalog[module_code],
        rows=rows,
    )


def _ensure_sigilatura_module_seed(session: Session, module_code: str) -> None:
    if module_code not in {"sigilatura", "espessura-pvc", "temperatura-forno-sigilatura", "escorrimento"}:
        return
    has_any = session.scalars(
        select(OperationalModuleItem.id)
        .where(OperationalModuleItem.module_code == module_code)
        .limit(1)
    ).first()
    if has_any is not None:
        return

    updates: list[dict[str, str]] = []
    if module_code == "sigilatura":
        source_rows = sigilatura_service._sigilatura_base_items("1", None)
        for row in source_rows:
            updates.append(
                {
                    "operacao": str(row.get("operacao") or "").strip(),
                    "controle": str(row.get("controle") or "").strip(),
                    "parametro": str(row.get("parametro") or "").strip(),
                }
            )
    elif module_code == "espessura-pvc":
        source_rows = sigilatura_service._espessura_base_items("1", None)
        for row in source_rows:
            updates.append(
                {
                    "operacao": str(row.get("modelo") or "").strip() or "226",
                    "controle": str(row.get("ponto") or "").strip(),
                    "parametro": str(row.get("valor_referencia") or "").strip(),
                }
            )
    elif module_code == "temperatura-forno-sigilatura":
        source_rows = sigilatura_service._temperatura_base_items(None)
        for row in source_rows:
            updates.append(
                {
                    "operacao": "FORNO",
                    "controle": str(row.get("zona") or "").strip(),
                    "parametro": str(row.get("referencia") or "").strip(),
                }
            )
    else:
        source_rows = sigilatura_service._escorrimento_base_items(None, None)
        for row in source_rows:
            updates.append(
                {
                    "operacao": "ESCORRIMENTO",
                    "controle": str(row.get("item") or "").strip(),
                    "parametro": "",
                }
            )

    dedup: dict[tuple[str, str], dict[str, str]] = {}
    for row in updates:
        operacao = str(row.get("operacao") or "").strip()
        controle = str(row.get("controle") or "").strip()
        if not operacao or not controle:
            continue
        dedup[(operacao.lower(), controle.lower())] = row

    if dedup:
        sigilatura_service.save_admin_parameter_overrides(session, module_code, list(dedup.values()))


def save_module_batch(session: Session, module_code: str, payload: dict[str, object]) -> dict[str, int]:
    available_codes = {item["code"] for item in operational_module_item_service.list_frequency_modules()}
    if module_code not in available_codes:
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
    limite_minimo = _normalize_nullable_float(item.limite_minimo)
    limite_maximo = _normalize_nullable_float(item.limite_maximo)
    if limite_minimo is None:
        limite_minimo = _normalize_nullable_float(item.valor_min)
    if limite_maximo is None:
        limite_maximo = _normalize_nullable_float(item.valor_max)
    return {
        "id": item.id,
        "escopo": item.escopo or "",
        "modulo": item.modulo or item.module_code,
        "aba": item.aba or "",
        "controle": item.controle,
        "operacao": item.operacao,
        "setor_tipo": item.setor_tipo,
        "setor_label": operational_module_item_service.SETOR_LABELS.get(item.setor_tipo, item.setor_tipo),
        "frequencia_tipo": item.frequencia_tipo or operational_module_item_service.FREQUENCY_DIARIO,
        "prioridade": _normalize_priority(item.prioridade),
        "dia_semana": _normalize_weekday(item.dia_semana),
        "dia_mes": item.dia_mes,
        "ordem": item.ordem,
        "ativo": bool(item.ativo),
        "tipo_validacao": module_parameter_validation.normalize_validation_type(item.tipo_validacao),
        "limite_minimo": limite_minimo,
        "limite_maximo": limite_maximo,
        "unidade": item.unidade or "",
        "parametro_exibicao": item.parametro_exibicao or item.referencia_visual or item.parametro or "",
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
    prioridade = _normalize_priority(payload.get("prioridade"))

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

    parametro_exibicao_payload = payload.get("parametro_exibicao")
    if parametro_exibicao_payload is None and existing_item is not None:
        parametro_exibicao = existing_item.parametro_exibicao
        parametro_raw = existing_item.parametro
    else:
        parametro_exibicao = str(parametro_exibicao_payload or "").strip() or None
        parametro_raw = parametro_exibicao

    limite_minimo = _normalize_nullable_float(payload.get("limite_minimo"))
    limite_maximo = _normalize_nullable_float(payload.get("limite_maximo"))

    return {
        "escopo": str(payload.get("escopo") or (existing_item.escopo if existing_item else "") or _scope_for_module(module_code)).strip() or _scope_for_module(module_code),
        "modulo": str(payload.get("modulo") or (existing_item.modulo if existing_item else "") or module_code).strip() or module_code,
        "aba": str(payload.get("aba") or (existing_item.aba if existing_item else "") or _aba_from_setor(setor_tipo)).strip() or _aba_from_setor(setor_tipo),
        "module_code": module_code,
        "controle": controle,
        "operacao": str(payload.get("operacao") or "").strip() or None,
        "setor_tipo": setor_tipo,
        "frequencia_tipo": frequencia_tipo,
        "prioridade": prioridade,
        "dia_semana": dia_semana,
        "dia_mes": dia_mes,
        "ordem": _normalize_nullable_int(payload.get("ordem")) or 0,
        "ativo": _normalize_bool(payload.get("ativo")),
        "obrigatorio": True,
        "tipo_validacao": _normalize_validation_type(payload.get("tipo_validacao")),
        "limite_minimo": limite_minimo,
        "limite_maximo": limite_maximo,
        "valor_min": limite_minimo,
        "valor_max": limite_maximo,
        "unidade": str(payload.get("unidade") or "").strip() or None,
        "parametro_exibicao": parametro_exibicao,
        "referencia_visual": parametro_exibicao,
        "parametro": parametro_raw,
    }


def _apply_row_payload(item: OperationalModuleItem, payload: dict[str, object | None]) -> None:
    item.controle = str(payload["controle"])
    item.escopo = payload["escopo"]
    item.modulo = payload["modulo"]
    item.aba = payload["aba"]
    item.operacao = payload["operacao"]
    item.setor_tipo = str(payload["setor_tipo"])
    item.frequencia_tipo = str(payload["frequencia_tipo"])
    item.prioridade = _normalize_priority(payload.get("prioridade"))
    item.dia_semana = payload["dia_semana"]
    item.dia_mes = payload["dia_mes"]
    item.ordem = int(payload["ordem"] or 0)
    item.ativo = bool(payload["ativo"])
    item.obrigatorio = True
    item.tipo_validacao = str(payload["tipo_validacao"] or module_parameter_validation.VALIDATION_NONE)
    item.limite_minimo = payload["limite_minimo"]
    item.limite_maximo = payload["limite_maximo"]
    item.valor_min = payload["valor_min"]
    item.valor_max = payload["valor_max"]
    item.unidade = payload["unidade"]
    item.parametro_exibicao = payload["parametro_exibicao"]
    item.referencia_visual = payload["referencia_visual"]
    item.parametro = payload["parametro"]


def _scope_for_module(module_code: str) -> str:
    normalized = str(module_code or "").strip().lower()
    if normalized in {"sigilatura", "espessura-pvc", "temperatura-forno-sigilatura", "escorrimento"}:
        return "sigilatura"
    if normalized == "central-tintas":
        return "central_tintas"
    return "ed"


def _aba_from_setor(setor_tipo: str) -> str:
    raw = str(setor_tipo or "").strip().upper()
    if raw == "PTED":
        return "PTED"
    if raw == "LABORATORIO":
        return "Laboratorio"
    if raw == "AMBOS":
        return "Ambos"
    return raw


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


def _normalize_nullable_float(value: object | None) -> float | None:
    if value in (None, ""):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")
    return float(raw)


def _normalize_validation_type(value: object | None) -> str:
    normalized = module_parameter_validation.normalize_validation_type(str(value or ""))
    if normalized not in module_parameter_validation.VALIDATION_TYPES:
        raise ValueError("Tipo de validação inválido.")
    return normalized


def _normalize_priority(value: object | None) -> str:
    normalized = str(value or '').strip().lower()
    if normalized not in operational_module_item_service.PRIORITY_TYPES:
        return operational_module_item_service.PRIORITY_MEDIO
    return normalized

