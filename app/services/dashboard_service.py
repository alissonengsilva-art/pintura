from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import case, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    OperationalModuleRecord,
    OperationalShift,
    Turno,
    SHIFT_STATUS_CONCLUIDO,
    SHIFT_STATUS_NAO_INICIADO,
)
from app.services.operational_module_service import (
    MISSING_SCHEMA_MESSAGE,
    MODULE_CONFIGS,
    MODULE_STATUS_CONCLUIDO,
    MODULE_STATUS_EM_ANDAMENTO,
    MODULE_STATUS_NAO_INICIADO,
    MODULE_STATUS_PARCIAL,
    STATUS_LABELS,
    SETOR_LABELS,
    build_history_row,
    build_sector_view,
    get_master_by_shift,
    get_module_config,
)
from app.services.shift_service import build_shift_detail, shift_schema_available


class DashboardValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DashboardFilters:
    data_referencia: date
    shift_id: int | None
    turno: str | None
    turno_options: list[Turno]


@dataclass(frozen=True)
class PendingFilters:
    data_referencia: date
    turno: str | None
    turno_options: list[Turno]


@dataclass(frozen=True)
class PendingSnapshot:
    filters: PendingFilters
    status_metrics: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    status_options: list[str]
    modulo_options: list[str]


@dataclass(frozen=True)
class DashboardSnapshot:
    filters: DashboardFilters
    has_global_alert: bool
    global_alert_message: str
    metrics: list[dict[str, Any]]
    module_cards: list[dict[str, Any]]
    shift_options: list[dict[str, Any]]
    selected_shift: dict[str, Any] | None
    empty_state_message: str | None


def _list_turno_options(session: Session) -> list[Turno]:
    return list(
        session.scalars(
            select(Turno)
            .where(Turno.ativo.is_(True))
            .order_by(case((Turno.codigo.in_(["1", "2", "3"]), 0), else_=1), Turno.codigo, Turno.nome)
        ).all()
    )


def parse_dashboard_filters(params: Any, session: Session) -> DashboardFilters:
    data_value = (params.get("data_referencia") or "").strip() if hasattr(params, "get") else ""
    if not data_value:
        target_date = date.today()
    else:
        try:
            target_date = date.fromisoformat(data_value)
        except ValueError as error:
            raise DashboardValidationError("Data inválida para o dashboard.") from error

    shift_id_value = (params.get("shift_id") or "").strip() if hasattr(params, "get") else ""
    shift_id: int | None = None
    if shift_id_value:
        try:
            shift_id = int(shift_id_value)
        except ValueError as error:
            raise DashboardValidationError("Turno selecionado inválido.") from error

    # Compatibilidade com links antigos por codigo de turno.
    turno_value = (params.get("turno") or "").strip() if hasattr(params, "get") else ""
    return DashboardFilters(
        data_referencia=target_date,
        shift_id=shift_id,
        turno=turno_value or None,
        turno_options=_list_turno_options(session),
    )


def parse_pending_filters(params: Any, session: Session) -> PendingFilters:
    data_value = (params.get("data_referencia") or "").strip() if hasattr(params, "get") else ""
    if not data_value:
        target_date = date.today()
    else:
        try:
            target_date = date.fromisoformat(data_value)
        except ValueError as error:
            raise DashboardValidationError("Data inválida para pendências.") from error
    turno = (params.get("turno") or "").strip() if hasattr(params, "get") else ""
    return PendingFilters(data_referencia=target_date, turno=turno or None, turno_options=_list_turno_options(session))


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y %H:%M")


def _turno_horario_label(turno: Turno | None) -> str | None:
    if turno is None:
        return None
    start = (
        getattr(turno, "hora_inicio", None)
        or getattr(turno, "horario_inicio", None)
        or getattr(turno, "inicio", None)
    )
    end = (
        getattr(turno, "hora_fim", None)
        or getattr(turno, "horario_fim", None)
        or getattr(turno, "fim", None)
    )
    if not start and not end:
        return None
    start_label = str(start) if start else "—"
    end_label = str(end) if end else "—"
    return f"{start_label} - {end_label}"


def _shift_status_view(status: str) -> tuple[str, str]:
    if status == SHIFT_STATUS_CONCLUIDO:
        return ("Concluído", "success")
    if status == SHIFT_STATUS_NAO_INICIADO:
        return ("Não iniciado", "neutral")
    return ("Em andamento", "warning")


def _module_status_view(status: str, has_alert: bool) -> tuple[str, str]:
    if status == MODULE_STATUS_CONCLUIDO:
        label = "Concluído"
        tone = "success"
    elif status == MODULE_STATUS_NAO_INICIADO:
        label = "Não iniciado"
        tone = "neutral"
    else:
        label = "Em andamento"
        tone = "warning"
    if has_alert:
        tone = "alert"
    return (label, tone)


def _build_shift_options(
    session: Session,
    filters: DashboardFilters,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    turno_map = {str(turno.codigo or ""): turno for turno in filters.turno_options}
    shift_rows = list(
        session.scalars(
            select(OperationalShift)
            .options(joinedload(OperationalShift.modulos))
            .where(OperationalShift.data_referencia == filters.data_referencia)
            .order_by(OperationalShift.turno.asc(), OperationalShift.created_at.asc())
        ).unique().all()
    )

    options: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    for shift in shift_rows:
        detail = build_shift_detail(session, shift)
        if not detail:
            continue
        turno_key = str(shift.turno or "")
        turno_ref = turno_map.get(turno_key)
        turno_nome = turno_ref.nome if turno_ref else (shift.turno or "Sem turno")
        turno_horario = _turno_horario_label(turno_ref)
        status_label, status_tone = _shift_status_view(detail["status_geral"])
        option = {
            "id": shift.id,
            "turno_codigo": shift.turno or "",
            "turno_nome": turno_nome,
            "turno_horario": turno_horario,
            "status_label": status_label,
            "status_tone": status_tone,
            "modulos_concluidos": detail["concluidos"],
            "modulos_total": detail["total_modules"],
            "modules_progress_label": f"{detail['concluidos']}/{detail['total_modules']} módulos",
            "detail": detail,
            "entity": shift,
        }
        options.append(option)

        if filters.shift_id and shift.id == filters.shift_id:
            selected = option

    if selected is None and filters.turno:
        selected = next((item for item in options if item["turno_codigo"] == filters.turno), None)

    return options, selected


def _build_module_items_summary(
    session: Session,
    shift: OperationalShift,
    module_code: str,
    responsavel_pted: str | None,
    responsavel_lab: str | None,
) -> list[dict[str, Any]]:
    config = get_module_config(module_code)
    master = get_master_by_shift(session, shift.id, module_code)
    context: dict[str, Any] = {"data_referencia": shift.data_referencia, "shift_id": shift.id}
    if shift.turno:
        context["turno"] = shift.turno

    rows: list[dict[str, Any]] = []
    for setor_tipo in config.sector_sequence:
        setor_view = build_sector_view(session, config, context, master, setor_tipo)
        fallback_responsavel = responsavel_pted if setor_tipo == "PTED" else responsavel_lab
        responsavel = setor_view["responsavel_nome"] or fallback_responsavel or "—"
        for row in setor_view["rows"]:
            item_nome = (
                row.get("descricao")
                or row.get("label")
                or row.get("operacao")
                or row.get("cis")
                or str(row.get("reference") or "Item")
            )
            valor = (
                row.get("value")
                or row.get("anomalia")
                or row.get("quantidade")
                or ""
            )
            observacao = row.get("row_observation") or row.get("item_observation") or ""
            status_label = row.get("status_label") or ("Agendado" if not row.get("is_applicable", True) else "Pendente")
            rows.append(
                {
                    "setor": SETOR_LABELS.get(setor_tipo, setor_tipo),
                    "item_nome": str(item_nome),
                    "status_item": str(status_label),
                    "valor": str(valor or "—"),
                    "observacao": str(observacao or "—"),
                    "responsavel": str(responsavel),
                    "desvio": bool(row.get("flag")),
                }
            )
    return rows


def build_dashboard_snapshot(session: Session, filters: DashboardFilters) -> DashboardSnapshot:
    if not shift_schema_available(session):
        return DashboardSnapshot(
            filters=filters,
            has_global_alert=False,
            global_alert_message=MISSING_SCHEMA_MESSAGE,
            metrics=[],
            module_cards=[],
            shift_options=[],
            selected_shift=None,
            empty_state_message=MISSING_SCHEMA_MESSAGE,
        )

    shift_options, selected_option = _build_shift_options(session, filters)
    if filters.shift_id and selected_option is None:
        raise DashboardValidationError("O turno selecionado não foi encontrado para a data informada.")

    if selected_option is None:
        message = "Selecione uma data e um turno para visualizar os controles."
        if not shift_options:
            message = "Nenhum turno encontrado para a data selecionada. Escolha outra data."
        return DashboardSnapshot(
            filters=filters,
            has_global_alert=False,
            global_alert_message="",
            metrics=[],
            module_cards=[],
            shift_options=[
                {
                    "id": item["id"],
                    "turno_nome": item["turno_nome"],
                    "turno_horario": item["turno_horario"],
                    "status_label": item["status_label"],
                    "status_tone": item["status_tone"],
                    "modules_progress_label": item["modules_progress_label"],
                }
                for item in shift_options
            ],
            selected_shift=None,
            empty_state_message=message,
        )

    shift = selected_option["entity"]
    shift_detail = selected_option["detail"]
    turno_horario = selected_option["turno_horario"]

    total_items = 0
    total_preenchidos = 0
    total_desvios = 0
    modulos_concluidos = 0
    modulos_andamento = 0
    modulos_nao_iniciados = 0
    module_cards: list[dict[str, Any]] = []

    records_map = {record.module_code: record for record in shift.modulos}
    for module in shift_detail["modules"]:
        module_total = int(module["pted_progress"]["total"]) + int(module["lab_progress"]["total"])
        module_preenchidos = int(module["pted_progress"]["preenchidos"]) + int(module["lab_progress"]["preenchidos"])
        module_percentual = int(round((module_preenchidos / module_total) * 100)) if module_total > 0 else 100
        module_desvios = int(module["desvios"])
        status_label, status_tone = _module_status_view(module["status_geral"], module_desvios > 0)

        if module["status_geral"] == MODULE_STATUS_CONCLUIDO:
            modulos_concluidos += 1
        elif module["status_geral"] in {MODULE_STATUS_EM_ANDAMENTO, MODULE_STATUS_PARCIAL}:
            modulos_andamento += 1
        else:
            modulos_nao_iniciados += 1

        total_items += module_total
        total_preenchidos += module_preenchidos
        total_desvios += module_desvios

        module_record = records_map.get(module["code"])
        last_updated = _format_datetime(module_record.updated_at if module_record else None)
        action_label = "Iniciar" if module["status_geral"] == MODULE_STATUS_NAO_INICIADO else "Continuar"
        execution_url = f"/turnos/{shift.id}?modulo={module['code']}"
        history_url = f"/{module['slug']}/historico"
        detail_rows = _build_module_items_summary(
            session,
            shift,
            module["code"],
            shift_detail.get("responsavel_pted"),
            shift_detail.get("responsavel_lab"),
        )
        module_cards.append(
            {
                "code": module["code"],
                "title": module["title"],
                "status_label": status_label,
                "status_tone": status_tone,
                "responsavel_pted": shift_detail.get("responsavel_pted") or "—",
                "responsavel_lab": shift_detail.get("responsavel_lab") or "—",
                "desvios": module_desvios,
                "progress_percent": module_percentual,
                "filled_items": module_preenchidos,
                "total_items": module_total,
                "progress_label": f"{module_preenchidos}/{module_total} itens preenchidos",
                "percent_label": f"{module_percentual}%",
                "last_updated": last_updated,
                "action_label": action_label,
                "execution_url": execution_url,
                "history_url": history_url,
                "detail_rows": detail_rows,
                "modal": {
                    "nome_modulo": module["title"],
                    "data": shift_detail["data_label"],
                    "turno": selected_option["turno_nome"],
                    "turno_horario": turno_horario,
                    "status": status_label,
                    "responsavel_pted": shift_detail.get("responsavel_pted") or "—",
                    "responsavel_lab": shift_detail.get("responsavel_lab") or "—",
                    "progress_percent": module_percentual,
                    "progress_label": f"{module_preenchidos}/{module_total}",
                    "desvios": module_desvios,
                    "last_updated": last_updated,
                    "items": detail_rows,
                    "execution_url": execution_url,
                    "history_url": history_url,
                },
            }
        )

    percentual_geral = int(round((total_preenchidos / total_items) * 100)) if total_items > 0 else 100
    shift_status_label, shift_status_tone = _shift_status_view(shift_detail["status_geral"])

    metrics = [
        {"label": "Módulos concluídos", "value": modulos_concluidos, "tone": "success"},
        {"label": "Módulos em andamento", "value": modulos_andamento, "tone": "warning"},
        {"label": "Módulos não iniciados", "value": modulos_nao_iniciados, "tone": "neutral"},
        {"label": "Desvios no turno", "value": total_desvios, "tone": "alert" if total_desvios > 0 else "neutral"},
    ]

    selected_shift = {
        "id": shift.id,
        "data_label": shift_detail["data_label"],
        "turno_nome": selected_option["turno_nome"],
        "turno_horario": turno_horario,
        "status_label": shift_status_label,
        "status_tone": shift_status_tone,
        "filled_items": total_preenchidos,
        "total_items": total_items,
        "percentual": percentual_geral,
        "progress_label": f"{total_preenchidos}/{total_items}",
        "modules_progress_label": f"{modulos_concluidos}/{shift_detail['total_modules']} módulos",
        "total_desvios": total_desvios,
    }

    return DashboardSnapshot(
        filters=filters,
        has_global_alert=total_desvios > 0,
        global_alert_message=(
            "Atenção: existem desvios operacionais neste turno."
            if total_desvios > 0
            else "Turno sem desvios ativos no momento."
        ),
        metrics=metrics,
        module_cards=module_cards,
        shift_options=[
            {
                "id": item["id"],
                "turno_nome": item["turno_nome"],
                "turno_horario": item["turno_horario"],
                "status_label": item["status_label"],
                "status_tone": item["status_tone"],
                "modules_progress_label": item["modules_progress_label"],
            }
            for item in shift_options
        ],
        selected_shift=selected_shift,
        empty_state_message=None,
    )


def build_pending_list_snapshot(session: Session, filters: PendingFilters) -> PendingSnapshot:
    rows = []
    for config in MODULE_CONFIGS.values():
        statement = (
            select(OperationalModuleRecord)
            .options(joinedload(OperationalModuleRecord.setores))
            .where(OperationalModuleRecord.module_code == config.code)
            .where(OperationalModuleRecord.data_referencia == filters.data_referencia)
            .order_by(OperationalModuleRecord.updated_at.desc())
        )
        if filters.turno and config.supports_turno:
            statement = statement.where(OperationalModuleRecord.turno == filters.turno)
        for record in session.scalars(statement).unique().all():
            row = build_history_row(config, record)
            if row["status_geral_label"] == STATUS_LABELS["CONCLUIDO"]:
                continue
            rows.append(
                {
                    "modulo": config.title,
                    "contexto": row["context_label"],
                    "status": row["status_geral_label"],
                    "pted": row["status_pted_label"],
                    "laboratorio": row["status_lab_label"],
                    "desvios": row["desvios"],
                    "detail_url": row["detail_url"],
                }
            )
    return PendingSnapshot(
        filters=filters,
        status_metrics=[
            {"label": "Pendências", "value": len(rows), "tone": "warning"},
            {"label": "Com desvio", "value": sum(1 for row in rows if row["desvios"] > 0), "tone": "warning"},
        ],
        rows=rows,
        status_options=[STATUS_LABELS["NAO_INICIADO"], STATUS_LABELS["EM_ANDAMENTO"], STATUS_LABELS["PARCIAL"]],
        modulo_options=[config.title for config in MODULE_CONFIGS.values()],
    )
