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
    paired_details = list(zip(shifts, details))
    active_pair = next((pair for pair in paired_details if pair[1]["status_geral"] != "CONCLUIDO"), None)
    target_pair = active_pair or (paired_details[0] if paired_details else None)
    target_shift = target_pair[0] if target_pair else None
    target = target_pair[1] if target_pair else None
    if target is None:
        return _empty_module_card(code=code, title=title, list_url=list_url)

    base_status = STATUS_EM_ANDAMENTO if target["status_geral"] != "CONCLUIDO" else STATUS_CONCLUIDO
    desvios = sum(int(module.get("desvios", 0)) for module in target.get("modules", []))
    display_status = STATUS_PENDENTE if desvios > 0 else base_status
    has_active = base_status == STATUS_EM_ANDAMENTO
    primary_action_url = (
        f"/turnos-pt/{target['id']}" if operation_scope == "pt" else f"/turnos/{target['id']}"
    )
    if not has_active:
        primary_action_url = f"{primary_action_url}/visualizar"

    responsavel = target.get("responsavel_pted") or target.get("responsavel_lab") or "-"
    extra_meta = None
    if operation_scope == "ed" and target.get("responsavel_lab") and target.get("responsavel_lab") != responsavel:
        extra_meta = f"Laboratório: {target['responsavel_lab']}"

    return _finalize_module_card(
        code=code,
        title=title,
        list_url=list_url,
        base_status=base_status,
        display_status=display_status,
        filled_count=int(target.get("total_concluidos", 0)),
        total_count=int(target.get("total_exigiveis", 0)),
        progress_percent=int(target.get("progresso_percentual", 0)),
        responsavel=responsavel,
        turno=target.get("turno") or "-",
        updated_label=_format_datetime_label(getattr(target_shift, "updated_at", None)),
        desvios=desvios,
        primary_action_label="Abrir turno" if has_active else "Visualizar",
        primary_action_url=primary_action_url,
        start_url="/operacoes/iniciar",
        has_active=has_active,
        turnos_encontrados=len(details),
        message=None,
        responsavel_aux=extra_meta,
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
    paired_details = list(zip(turnos, details))
    active_pair = next((pair for pair in paired_details if pair[1]["status_geral"] != SIG_SHIFT_STATUS_CONCLUIDO), None)
    target_pair = active_pair or (paired_details[0] if paired_details else None)
    target_turno = target_pair[0] if target_pair else None
    target = target_pair[1] if target_pair else None
    if target is None:
        return _empty_module_card(code="sigilatura", title="Sigilatura", list_url=list_url)

    base_status = (
        STATUS_CONCLUIDO
        if target["status_geral"] == SIG_SHIFT_STATUS_CONCLUIDO
        else STATUS_EM_ANDAMENTO
        if target["status_geral"] in {SIG_SHIFT_STATUS_EM_ANDAMENTO, SIG_SHIFT_STATUS_PARCIAL}
        else STATUS_NAO_INICIADO
    )
    display_status = STATUS_PENDENTE if int(target.get("total_desvios", 0)) > 0 else base_status
    has_active = base_status == STATUS_EM_ANDAMENTO
    primary_action_url = f"/turnos-sigilatura/{target['id']}"
    if not has_active:
        primary_action_url = f"{primary_action_url}/visualizar"

    return _finalize_module_card(
        code="sigilatura",
        title="Sigilatura",
        list_url=list_url,
        base_status=base_status,
        display_status=display_status,
        filled_count=int(target.get("total_filled", 0)),
        total_count=int(target.get("total_items", 0)),
        progress_percent=int(target.get("progresso", 0)),
        responsavel=target.get("responsavel") or "-",
        turno=target.get("turno") or "-",
        updated_label=_format_datetime_label(getattr(target_turno, "updated_at", None)),
        desvios=int(target.get("total_desvios", 0)),
        primary_action_label="Abrir turno" if has_active else "Visualizar",
        primary_action_url=primary_action_url,
        start_url="/operacoes/iniciar",
        has_active=has_active,
        turnos_encontrados=len(details),
        message=None,
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
    active = next((relatorio for relatorio in relatorios if relatorio.status == active_status), None)
    target = active or (relatorios[0] if relatorios else None)
    if target is None:
        return _empty_module_card(code=code, title=title, list_url=list_url)

    context = context_builder(session, target)
    base_status = STATUS_CONCLUIDO if target.status == concluded_status else STATUS_EM_ANDAMENTO
    progress = context.get("summary", {})
    filled_count = int(progress.get("preenchidos", 0))
    total_count = int(progress.get("total", 0))
    display_status = base_status
    return _finalize_module_card(
        code=code,
        title=title,
        list_url=list_url,
        base_status=base_status,
        display_status=display_status,
        filled_count=filled_count,
        total_count=total_count,
        progress_percent=int(progress.get("percentual", 0)),
        responsavel=context.get("responsavel") or "-",
        turno=context.get("turno") or "-",
        updated_label=_format_datetime_label(getattr(target, "updated_at", None)),
        desvios=0,
        primary_action_label="Abrir turno" if base_status == STATUS_EM_ANDAMENTO else "Visualizar",
        primary_action_url=f"{list_url}/{target.id}" if base_status == STATUS_EM_ANDAMENTO else f"{list_url}/{target.id}/visualizar",
        start_url="/operacoes/iniciar",
        has_active=base_status == STATUS_EM_ANDAMENTO,
        turnos_encontrados=len(relatorios),
        message=None,
    )


def _finalize_module_card(
    *,
    code: str,
    title: str,
    list_url: str,
    base_status: str,
    display_status: str,
    filled_count: int,
    total_count: int,
    progress_percent: int,
    responsavel: str,
    turno: str,
    updated_label: str,
    desvios: int,
    primary_action_label: str,
    primary_action_url: str,
    start_url: str,
    has_active: bool,
    turnos_encontrados: int,
    message: str | None,
    responsavel_aux: str | None = None,
    can_start: bool | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "status": display_status,
        "base_status": base_status,
        "status_label": STATUS_LABELS[display_status],
        "tone": STATUS_TONES[display_status],
        "status_class": f"operacoes-status--{display_status.replace('_', '-')}",
        "progress_label": f"{filled_count}/{total_count}",
        "progress_percent": progress_percent,
        "filled_count": filled_count,
        "total_count": total_count,
        "responsavel": responsavel,
        "responsavel_aux": responsavel_aux,
        "turno": turno,
        "updated_label": updated_label,
        "desvios": desvios,
        "message": message,
        "turnos_label": f"{turnos_encontrados} turno{'s' if turnos_encontrados != 1 else ''} no dia" if turnos_encontrados else None,
        "primary_action_label": primary_action_label,
        "primary_action_url": primary_action_url,
        "secondary_action_label": "Ver histórico",
        "secondary_action_url": list_url,
        "start_url": start_url,
        "has_active": has_active,
        "can_start": base_status == STATUS_NAO_INICIADO if can_start is None else can_start,
    }


def _empty_module_card(*, code: str, title: str, list_url: str, message: str | None = None) -> dict[str, Any]:
    resolved_message = message or "Nenhum turno iniciado para esta data."
    return _finalize_module_card(
        code=code,
        title=title,
        list_url=list_url,
        base_status=STATUS_NAO_INICIADO,
        display_status=STATUS_NAO_INICIADO,
        filled_count=0,
        total_count=0,
        progress_percent=0,
        responsavel="-",
        turno="-",
        updated_label="-",
        desvios=0,
        primary_action_label="Iniciar turno",
        primary_action_url="#",
        start_url="/operacoes/iniciar",
        has_active=False,
        turnos_encontrados=0,
        message=resolved_message,
        can_start="não configurada" not in resolved_message.lower() and "nao configurada" not in resolved_message.lower(),
    )


def _format_datetime_label(value) -> str:
    if value is None:
        return "-"
    return value.strftime("%d/%m/%Y %H:%M")
