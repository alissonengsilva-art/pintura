from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CABINE_PINTURA_STATUS_CONCLUIDO,
    CABINE_PINTURA_STATUS_EM_ANDAMENTO,
    CENTRAL_TINTAS_STATUS_CONCLUIDO,
    CENTRAL_TINTAS_STATUS_EM_ANDAMENTO,
    CabinePinturaRelatorio,
    CentralTintasRelatorio,
    OperationalShift,
    SIG_SHIFT_STATUS_CONCLUIDO,
    SIG_SHIFT_STATUS_EM_ANDAMENTO,
    SIG_SHIFT_STATUS_PARCIAL,
    SigilaturaTurno,
)
from app.services.cabine_pintura_service import (
    build_relatorio_context as build_cabine_relatorio_context,
    cabine_pintura_flow_schema_available,
)
from app.services.central_tintas_service import (
    build_relatorio_context as build_central_relatorio_context,
    central_tintas_flow_schema_available,
)
from app.services.shift_service import build_shift_detail, shift_schema_available
from app.services.sigilatura_service import build_turno_detail, sigilatura_schema_available


PT_MODULE_CODES = ["pt", "pressao-filtros-pt"]
ED_MODULE_CODES = [
    "ed",
    "temperatura-forno-ed",
    "pressao-filtros-ed",
    "tensao-retificadores-ed",
    "poder-penetracao",
    "espessura-ed",
    "aspecto",
    "rugosidade",
]

STANDARD_SHIFT_CODES = ("1", "2", "3")
STANDARD_SHIFT_LABELS = {
    "1": "1º Turno",
    "2": "2º Turno",
    "3": "3º Turno",
}

STATUS_NAO_INICIADO = "nao_iniciado"
STATUS_EM_ANDAMENTO = "em_andamento"
STATUS_CONCLUIDO = "concluido"
STATUS_PENDENTE = "pendente"

STATUS_LABELS = {
    STATUS_NAO_INICIADO: "Não iniciado",
    STATUS_EM_ANDAMENTO: "Em andamento",
    STATUS_CONCLUIDO: "Concluído",
    STATUS_PENDENTE: "Com pendências",
}

STATUS_TONES = {
    STATUS_NAO_INICIADO: "neutral",
    STATUS_EM_ANDAMENTO: "warning",
    STATUS_CONCLUIDO: "success",
    STATUS_PENDENTE: "alert",
}


def build_operacoes_context(session: Session, data_referencia: date) -> dict[str, Any]:
    modules = [
        _build_shift_module_card(
            session,
            data_referencia,
            title="PT",
            code="pt",
            list_url="/turnos-pt",
            operation_scope="pt",
            module_codes=PT_MODULE_CODES,
        ),
        _build_shift_module_card(
            session,
            data_referencia,
            title="ED",
            code="ed",
            list_url="/turnos-ed",
            operation_scope="ed",
            module_codes=ED_MODULE_CODES,
        ),
        _build_sigilatura_module_card(session, data_referencia),
        _build_central_tintas_module_card(session, data_referencia),
        _build_cabine_pintura_module_card(session, data_referencia),
    ]

    total_modulos = len(modules)
    concluidos = sum(1 for module in modules if module["base_status"] == STATUS_CONCLUIDO)
    em_andamento = sum(1 for module in modules if module["base_status"] == STATUS_EM_ANDAMENTO)
    nao_iniciados = sum(1 for module in modules if module["base_status"] == STATUS_NAO_INICIADO)
    pendencias = sum(1 for module in modules if int(module.get("desvios") or 0) > 0)
    iniciados = concluidos + em_andamento
    percentual = int(round((iniciados / total_modulos) * 100)) if total_modulos else 0

    return {
        "data_referencia": data_referencia,
        "data_label": data_referencia.strftime("%d/%m/%Y"),
        "summary": {
            "total_modulos": total_modulos,
            "concluidos": concluidos,
            "em_andamento": em_andamento,
            "nao_iniciados": nao_iniciados,
            "pendencias": pendencias,
            "iniciados": iniciados,
            "percentual": percentual,
            "progress_label": f"{iniciados}/{total_modulos} módulos iniciados",
        },
        "modules": modules,
    }


def _build_shift_module_card(
    session: Session,
    data_referencia: date,
    *,
    title: str,
    code: str,
    list_url: str,
    operation_scope: str,
    module_codes: list[str],
) -> dict[str, Any]:
    if not shift_schema_available(session):
        return _empty_module_card(code=code, title=title, list_url=list_url, message="Estrutura não configurada.")

    statement = (
        select(OperationalShift)
        .options(joinedload(OperationalShift.modulos))
        .where(OperationalShift.data_referencia == data_referencia)
        .where(OperationalShift.operation_scope == operation_scope)
        .order_by(OperationalShift.updated_at.desc(), OperationalShift.turno.desc(), OperationalShift.id.desc())
    )
    shifts = list(session.scalars(statement).unique().all())
    details = [build_shift_detail(session, shift, module_codes=module_codes) for shift in shifts]

    turno_map: dict[str, dict[str, Any]] = {}
    for shift, detail in zip(shifts, details):
        turno_code = _normalize_turno_code(getattr(shift, "turno", None) or detail.get("turno"))
        if turno_code not in STANDARD_SHIFT_CODES or turno_code in turno_map:
            continue
        status = STATUS_CONCLUIDO if detail.get("status_geral") == "CONCLUIDO" else STATUS_EM_ANDAMENTO
        responsavel = detail.get("responsavel_pted") or detail.get("responsavel_lab") or "-"
        turno_map[turno_code] = {
            "turno_code": turno_code,
            "status": status,
            "filled_count": int(detail.get("total_concluidos", 0)),
            "total_count": int(detail.get("total_exigiveis", 0)),
            "desvios": sum(int(module.get("desvios", 0)) for module in detail.get("modules", [])),
            "updated_at": getattr(shift, "updated_at", None),
            "responsavel": responsavel,
            "action_label": "Abrir" if status == STATUS_EM_ANDAMENTO else "Visualizar",
            "action_url": (
                f"/turnos-pt/{detail['id']}" if operation_scope == "pt" else f"/turnos/{detail['id']}"
            ),
            "action_kind": "link",
            "action_style": "primary" if status == STATUS_EM_ANDAMENTO else "secondary",
        }
        if status == STATUS_CONCLUIDO:
            turno_map[turno_code]["action_url"] = f"{turno_map[turno_code]['action_url']}/visualizar"

    return _build_module_card_from_turnos(
        code=code,
        title=title,
        list_url=list_url,
        turno_map=turno_map,
        can_start=True,
    )


def _build_sigilatura_module_card(session: Session, data_referencia: date) -> dict[str, Any]:
    list_url = "/turnos-sigilatura"
    if not sigilatura_schema_available(session):
        return _empty_module_card(code="sigilatura", title="Sigilatura", list_url=list_url, message="Estrutura não configurada.")

    statement = (
        select(SigilaturaTurno)
        .options(joinedload(SigilaturaTurno.modulos))
        .where(SigilaturaTurno.data_referencia == data_referencia)
        .order_by(SigilaturaTurno.updated_at.desc(), SigilaturaTurno.turno.desc(), SigilaturaTurno.id.desc())
    )
    turnos = list(session.scalars(statement).unique().all())
    details = [build_turno_detail(session, turno) for turno in turnos]

    turno_map: dict[str, dict[str, Any]] = {}
    for turno, detail in zip(turnos, details):
        turno_code = _normalize_turno_code(getattr(turno, "turno", None) or detail.get("turno"))
        if turno_code not in STANDARD_SHIFT_CODES or turno_code in turno_map:
            continue

        raw_status = detail.get("status_geral")
        status = STATUS_CONCLUIDO if raw_status == SIG_SHIFT_STATUS_CONCLUIDO else STATUS_EM_ANDAMENTO
        turno_map[turno_code] = {
            "turno_code": turno_code,
            "status": status,
            "filled_count": int(detail.get("total_filled", 0)),
            "total_count": int(detail.get("total_items", 0)),
            "desvios": int(detail.get("total_desvios", 0)),
            "updated_at": getattr(turno, "updated_at", None),
            "responsavel": detail.get("responsavel") or "-",
            "action_label": "Abrir" if raw_status in {SIG_SHIFT_STATUS_EM_ANDAMENTO, SIG_SHIFT_STATUS_PARCIAL} else "Visualizar",
            "action_url": (
                f"/turnos-sigilatura/{detail['id']}"
                if raw_status in {SIG_SHIFT_STATUS_EM_ANDAMENTO, SIG_SHIFT_STATUS_PARCIAL}
                else f"/turnos-sigilatura/{detail['id']}/visualizar"
            ),
            "action_kind": "link",
            "action_style": "primary" if raw_status in {SIG_SHIFT_STATUS_EM_ANDAMENTO, SIG_SHIFT_STATUS_PARCIAL} else "secondary",
        }

    return _build_module_card_from_turnos(
        code="sigilatura",
        title="Sigilatura",
        list_url=list_url,
        turno_map=turno_map,
        can_start=True,
    )


def _build_central_tintas_module_card(session: Session, data_referencia: date) -> dict[str, Any]:
    return _build_relatorio_module_card(
        session,
        data_referencia,
        model=CentralTintasRelatorio,
        title="Central de Tintas",
        code="central-tintas",
        list_url="/central-tintas",
        schema_available=central_tintas_flow_schema_available(session),
        context_builder=build_central_relatorio_context,
        concluded_status=CENTRAL_TINTAS_STATUS_CONCLUIDO,
        active_status=CENTRAL_TINTAS_STATUS_EM_ANDAMENTO,
    )


def _build_cabine_pintura_module_card(session: Session, data_referencia: date) -> dict[str, Any]:
    return _build_relatorio_module_card(
        session,
        data_referencia,
        model=CabinePinturaRelatorio,
        title="Cabine de Pintura",
        code="cabine-pintura",
        list_url="/cabine-pintura",
        schema_available=cabine_pintura_flow_schema_available(session),
        context_builder=build_cabine_relatorio_context,
        concluded_status=CABINE_PINTURA_STATUS_CONCLUIDO,
        active_status=CABINE_PINTURA_STATUS_EM_ANDAMENTO,
    )


def _build_relatorio_module_card(
    session: Session,
    data_referencia: date,
    *,
    model,
    title: str,
    code: str,
    list_url: str,
    schema_available: bool,
    context_builder,
    concluded_status: str,
    active_status: str,
) -> dict[str, Any]:
    if not schema_available:
        return _empty_module_card(code=code, title=title, list_url=list_url, message="Estrutura não configurada.")

    statement = (
        select(model)
        .options(joinedload(model.itens))
        .where(model.data_controle == data_referencia)
        .order_by(model.updated_at.desc(), model.turno.desc(), model.id.desc())
    )
    relatorios = list(session.scalars(statement).unique().all())

    turno_map: dict[str, dict[str, Any]] = {}
    for relatorio in relatorios:
        turno_code = _normalize_turno_code(getattr(relatorio, "turno", None))
        if turno_code not in STANDARD_SHIFT_CODES or turno_code in turno_map:
            continue

        context = context_builder(session, relatorio)
        progress = context.get("summary", {})
        is_active = relatorio.status == active_status
        turno_map[turno_code] = {
            "turno_code": turno_code,
            "status": STATUS_EM_ANDAMENTO if is_active else STATUS_CONCLUIDO,
            "filled_count": int(progress.get("preenchidos", 0)),
            "total_count": int(progress.get("total", 0)),
            "desvios": int(progress.get("desvios", 0) or 0),
            "updated_at": getattr(relatorio, "updated_at", None),
            "responsavel": context.get("responsavel") or "-",
            "action_label": "Abrir" if is_active else "Visualizar",
            "action_url": f"{list_url}/{relatorio.id}" if is_active else f"{list_url}/{relatorio.id}/visualizar",
            "action_kind": "link",
            "action_style": "primary" if is_active else "secondary",
        }
        if relatorio.status not in {active_status, concluded_status}:
            turno_map[turno_code]["status"] = STATUS_EM_ANDAMENTO
            turno_map[turno_code]["action_label"] = "Abrir"
            turno_map[turno_code]["action_url"] = f"{list_url}/{relatorio.id}"
            turno_map[turno_code]["action_style"] = "primary"

    return _build_module_card_from_turnos(
        code=code,
        title=title,
        list_url=list_url,
        turno_map=turno_map,
        can_start=True,
    )


def _build_module_card_from_turnos(
    *,
    code: str,
    title: str,
    list_url: str,
    turno_map: dict[str, dict[str, Any]],
    can_start: bool,
    message: str | None = None,
) -> dict[str, Any]:
    shift_rows = [_build_shift_row(code, title, turno_code, turno_map.get(turno_code), can_start=can_start) for turno_code in STANDARD_SHIFT_CODES]

    existing_rows = [row for row in shift_rows if row["status"] != STATUS_NAO_INICIADO]
    total_desvios = sum(int(row.get("desvios", 0)) for row in existing_rows)
    filled_count = sum(int(row.get("filled_count", 0)) for row in existing_rows)
    total_count = sum(int(row.get("total_count", 0)) for row in existing_rows)
    started_count = len(existing_rows)
    all_concluded = bool(shift_rows) and all(row["status"] == STATUS_CONCLUIDO for row in shift_rows)
    any_active = any(row["status"] == STATUS_EM_ANDAMENTO for row in shift_rows)
    all_not_started = all(row["status"] == STATUS_NAO_INICIADO for row in shift_rows)
    base_status = (
        STATUS_CONCLUIDO
        if all_concluded
        else STATUS_NAO_INICIADO
        if all_not_started
        else STATUS_EM_ANDAMENTO
    )
    display_status = _resolve_display_status(
        base_status=base_status,
        total_desvios=total_desvios,
        any_active=any_active,
        all_not_started=all_not_started,
    )
    latest_update = max((row["updated_at"] for row in existing_rows if row.get("updated_at") is not None), default=None)

    return {
        "code": code,
        "title": title,
        "status": display_status,
        "base_status": base_status,
        "status_label": STATUS_LABELS[display_status],
        "tone": STATUS_TONES[display_status],
        "status_class": f"operacoes-status--{display_status.replace('_', '-')}",
        "progress_label": f"{filled_count}/{total_count}" if total_count else "0/0",
        "progress_percent": int(round((filled_count / total_count) * 100)) if total_count else 0,
        "filled_count": filled_count,
        "total_count": total_count,
        "responsavel": existing_rows[0]["responsavel"] if existing_rows else "-",
        "turno": existing_rows[0]["turno_label"] if existing_rows else "-",
        "updated_label": _format_datetime_label(latest_update),
        "updated_time_label": _format_time_label(latest_update),
        "desvios": total_desvios,
        "message": message,
        "turnos_label": f"{started_count}/3 turnos iniciados" if started_count else "Sem turno no dia",
        "shift_rows": shift_rows,
        "footer_items_label": f"{total_count} itens",
        "footer_pendencias_label": f"{total_desvios} pendência{'s' if total_desvios != 1 else ''}",
        "footer_updated_label": f"Atualizado { _format_time_label(latest_update) }" if latest_update else "Sem atualização",
        "secondary_action_label": "Ver histórico",
        "secondary_action_url": list_url,
        "can_start": can_start,
    }


def _build_shift_row(
    module_code: str,
    module_title: str,
    turno_code: str,
    turno_data: dict[str, Any] | None,
    *,
    can_start: bool,
) -> dict[str, Any]:
    if turno_data is None:
        return {
            "turno_code": turno_code,
            "turno_label": STANDARD_SHIFT_LABELS[turno_code],
            "status": STATUS_NAO_INICIADO,
            "status_label": STATUS_LABELS[STATUS_NAO_INICIADO],
            "tone": STATUS_TONES[STATUS_NAO_INICIADO],
            "status_class": f"operacoes-status--{STATUS_NAO_INICIADO.replace('_', '-')}",
            "filled_count": 0,
            "total_count": 0,
            "desvios": 0,
            "updated_at": None,
            "responsavel": "-",
            "action_label": "Iniciar" if can_start else "Indisponível",
            "action_url": "#",
            "action_kind": "start" if can_start else "disabled",
            "action_style": "ghost",
            "module_code": module_code,
            "module_title": module_title,
        }

    row = dict(turno_data)
    row["turno_label"] = STANDARD_SHIFT_LABELS[turno_code]
    row["status_label"] = STATUS_LABELS[row["status"]]
    row["tone"] = STATUS_TONES[row["status"]]
    row["status_class"] = f"operacoes-status--{row['status'].replace('_', '-')}"
    row["module_code"] = module_code
    row["module_title"] = module_title
    return row


def _resolve_display_status(
    *,
    base_status: str,
    total_desvios: int,
    any_active: bool,
    all_not_started: bool,
) -> str:
    if any_active:
        return STATUS_EM_ANDAMENTO
    if total_desvios > 0:
        return STATUS_PENDENTE
    if all_not_started:
        return STATUS_NAO_INICIADO
    return base_status


def _empty_module_card(*, code: str, title: str, list_url: str, message: str | None = None) -> dict[str, Any]:
    return _build_module_card_from_turnos(
        code=code,
        title=title,
        list_url=list_url,
        turno_map={},
        can_start=not _is_unavailable_message(message),
        message=message,
    )


def _is_unavailable_message(message: str | None) -> bool:
    lowered = str(message or "").strip().lower()
    return "não configurada" in lowered or "nao configurada" in lowered


def _normalize_turno_code(value: Any) -> str:
    return str(value or "").strip()


def _format_datetime_label(value) -> str:
    if value is None:
        return "-"
    return value.strftime("%d/%m/%Y %H:%M")


def _format_time_label(value) -> str:
    if value is None:
        return "-"
    return value.strftime("%H:%M")
