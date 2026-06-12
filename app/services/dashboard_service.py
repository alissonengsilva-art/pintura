from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import case, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    OperationalModuleItem,
    OperationalModuleRecord,
    OperationalShift,
    SIG_MODULE_CODES,
    SHIFT_STATUS_CONCLUIDO,
    SHIFT_STATUS_NAO_INICIADO,
    SigilaturaModulo,
    SigilaturaTurno,
    Turno,
)
from app.services.operational_module_service import (
    MISSING_SCHEMA_MESSAGE,
    MODULE_CONFIGS,
    MODULE_STATUS_CONCLUIDO,
    MODULE_STATUS_EM_ANDAMENTO,
    MODULE_STATUS_NAO_INICIADO,
    MODULE_STATUS_PARCIAL,
    PRIORIDADE_LABELS,
    STATUS_LABELS,
    SETOR_LABELS,
    build_history_row,
    build_sector_view,
    get_master_by_shift,
    get_module_config,
)
from app.services.shift_service import build_shift_detail, shift_schema_available
from app.services.sigilatura_service import (
    _load_module_rows as load_sigilatura_module_rows,
    build_turno_detail,
    sigilatura_schema_available,
)


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
    dashboard_day: dict[str, Any] | None
    has_global_alert: bool
    global_alert_message: str
    metrics: list[dict[str, Any]]
    chart_parametros: list[dict[str, Any]]
    chart_prioridades: list[dict[str, Any]]
    module_cards: list[dict[str, Any]]
    shift_options: list[dict[str, Any]]
    selected_shift: dict[str, Any] | None
    empty_state_message: str | None


MACRO_MODULE_ORDER = ("PT", "ED", "SIGILATURA")
MACRO_MODULE_CODES = {
    "PT": {"pt", "pressao-filtros-pt"},
    "ED": {
        "ed",
        "temperatura-forno-ed",
        "pressao-filtros-ed",
        "tensao-retificadores-ed",
        "poder-penetracao",
        "espessura-ed",
        "aspecto",
        "rugosidade",
    },
    "SIGILATURA": set(SIG_MODULE_CODES),
}
PRIORITY_ORDER = ("baixo", "medio", "alto")
CHART_COLORS = {
    "realizado": "#2f9e44",
    "nao_realizado": "#d64545",
    "baixo": "#f3c64b",
    "medio": "#f28c28",
    "alto": "#d64545",
}


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


def _format_date_label(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _turno_horario_label(turno: Turno | None) -> str | None:
    if turno is None:
        return None
    start = getattr(turno, "hora_inicio", None) or getattr(turno, "horario_inicio", None) or getattr(turno, "inicio", None)
    end = getattr(turno, "hora_fim", None) or getattr(turno, "horario_fim", None) or getattr(turno, "fim", None)
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


def _macro_module_for_code(module_code: str) -> str:
    for macro, codes in MACRO_MODULE_CODES.items():
        if module_code in codes:
            return macro
    return "ED"


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
    if master is not None and master.context_data:
        context.update(master.context_data)
    context["data_referencia"] = shift.data_referencia
    context["shift_id"] = shift.id
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
            valor = row.get("value") or row.get("anomalia") or row.get("quantidade") or ""
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
                    "prioridade": str(row.get("prioridade") or "medio"),
                    "is_applicable": bool(row.get("is_applicable", True)),
                }
            )
    return rows


def _load_item_priority_map(session: Session) -> dict[int, str]:
    priority_map: dict[int, str] = {}
    for item in session.scalars(select(OperationalModuleItem)).all():
        prioridade = str(item.prioridade or "").strip().lower()
        if prioridade not in PRIORIDADE_LABELS:
            prioridade = "medio"
        priority_map[item.id] = prioridade
    return priority_map


def _sigilatura_row_value(row: dict[str, Any]) -> str:
    return str(
        row.get("valor")
        or row.get("descricao")
        or row.get("valor_medido")
        or row.get("resultados_obtidos")
        or ""
    ).strip()


def _sigilatura_rows_for_module(
    session: Session,
    turno_obj: SigilaturaTurno,
    module_code: str,
    item_priority_map: dict[int, str],
) -> list[dict[str, Any]]:
    rows = []
    for row in load_sigilatura_module_rows(session, turno_obj, module_code):
        item_id = row.get("item_id") or row.get("operational_module_item_id")
        prioridade = item_priority_map.get(int(item_id)) if item_id not in (None, "") else "medio"
        rows.append(
            {
                **row,
                "prioridade": prioridade if prioridade in PRIORIDADE_LABELS else "medio",
                "is_applicable": True,
            }
        )
    return rows


def _aggregate_priority_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {priority: 0 for priority in PRIORITY_ORDER}
    for row in rows:
        if not row.get("is_applicable", True):
            continue
        prioridade = str(row.get("prioridade") or "medio").strip().lower()
        if prioridade not in counts:
            prioridade = "medio"
        counts[prioridade] += 1
    return counts


def _build_chart_segments(segment_specs: list[tuple[str, str, int]], total: int) -> list[dict[str, Any]]:
    safe_total = total if total > 0 else 1
    segments = []
    for key, label, value in segment_specs:
        percent = (value / safe_total) * 100 if total > 0 else 0
        percent_int = int(round(percent))
        segments.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "percent": round(percent, 2),
                "percent_label": f"{percent_int}%",
                "color": CHART_COLORS[key],
                "show_value": value > 0 and percent >= 12,
            }
        )
    segments.sort(key=lambda segment: (-float(segment["percent"]), segment["label"]))
    return segments


def _build_chart_row(label: str, total: int, segment_specs: list[tuple[str, str, int]]) -> dict[str, Any]:
    return {"label": label, "total": total, "segments": _build_chart_segments(segment_specs, total)}


def _empty_chart_row(label: str, segment_keys: list[tuple[str, str]]) -> dict[str, Any]:
    return _build_chart_row(label, 0, [(key, title, 0) for key, title in segment_keys])


def build_dashboard_snapshot(session: Session, filters: DashboardFilters) -> DashboardSnapshot:
    shift_schema_ok = shift_schema_available(session)
    sig_schema_ok = sigilatura_schema_available(session)
    if not shift_schema_ok and not sig_schema_ok:
        return DashboardSnapshot(
            filters=filters,
            dashboard_day=None,
            has_global_alert=False,
            global_alert_message=MISSING_SCHEMA_MESSAGE,
            metrics=[],
            chart_parametros=[],
            chart_prioridades=[],
            module_cards=[],
            shift_options=[],
            selected_shift=None,
            empty_state_message=MISSING_SCHEMA_MESSAGE,
        )

    item_priority_map = _load_item_priority_map(session)
    module_aggregates: dict[str, dict[str, Any]] = {}
    macro_param_totals = {macro: {"filled": 0, "total": 0} for macro in MACRO_MODULE_ORDER}
    macro_priority_totals = {macro: {priority: 0 for priority in PRIORITY_ORDER} for macro in MACRO_MODULE_ORDER}
    shift_options: list[dict[str, Any]] = []

    operational_shifts: list[OperationalShift] = []
    if shift_schema_ok:
        operational_shifts = list(
            session.scalars(
                select(OperationalShift)
                .options(joinedload(OperationalShift.modulos))
                .where(OperationalShift.data_referencia == filters.data_referencia)
                .order_by(OperationalShift.operation_scope.asc(), OperationalShift.turno.asc(), OperationalShift.created_at.asc())
            ).unique().all()
        )

    sigilatura_shifts: list[SigilaturaTurno] = []
    if sig_schema_ok:
        sigilatura_shifts = list(
            session.scalars(
                select(SigilaturaTurno)
                .options(joinedload(SigilaturaTurno.modulos).joinedload(SigilaturaModulo.respostas))
                .where(SigilaturaTurno.data_referencia == filters.data_referencia)
                .order_by(SigilaturaTurno.turno.asc(), SigilaturaTurno.created_at.asc())
            ).unique().all()
        )

    if filters.shift_id:
        known_ids = {shift.id for shift in operational_shifts} | {shift.id for shift in sigilatura_shifts}
        if filters.shift_id not in known_ids:
            raise DashboardValidationError("O turno selecionado não foi encontrado para a data informada.")

    turno_map = {str(turno.codigo or ""): turno for turno in filters.turno_options}

    for shift in operational_shifts:
        shift_detail = build_shift_detail(session, shift)
        turno_ref = turno_map.get(str(shift.turno or ""))
        turno_nome = turno_ref.nome if turno_ref else (f"Turno {shift.turno}" if shift.turno else "Sem turno")
        turno_horario = _turno_horario_label(turno_ref)
        status_label, status_tone = _shift_status_view(shift_detail["status_geral"])
        shift_options.append(
            {
                "id": shift.id,
                "turno_nome": turno_nome,
                "turno_horario": turno_horario,
                "status_label": status_label,
                "status_tone": status_tone,
                "modules_progress_label": f"{shift_detail['concluidos']}/{shift_detail['total_modules']} módulos",
            }
        )

        records_map = {record.module_code: record for record in shift.modulos}
        for module in shift_detail["modules"]:
            module_code = str(module["code"])
            module_total = int(module["pted_progress"]["total"]) + int(module["lab_progress"]["total"])
            module_preenchidos = int(module["pted_progress"]["preenchidos"]) + int(module["lab_progress"]["preenchidos"])
            module_desvios = int(module["desvios"])
            module_rows = _build_module_items_summary(
                session,
                shift,
                module_code,
                shift_detail.get("responsavel_pted"),
                shift_detail.get("responsavel_lab"),
            )
            module_record = records_map.get(module_code)
            aggregate = module_aggregates.setdefault(
                module_code,
                {
                    "code": module_code,
                    "title": module["title"],
                    "slug": module["slug"],
                    "filled_items": 0,
                    "total_items": 0,
                    "desvios": 0,
                    "last_updated_at": None,
                    "responsavel_pted": set(),
                    "responsavel_lab": set(),
                    "items": [],
                    "execution_url": f"/turnos/{shift.id}?modulo={module_code}",
                    "history_url": f"/{module['slug']}/historico?data_referencia={filters.data_referencia.isoformat()}",
                },
            )
            aggregate["filled_items"] += module_preenchidos
            aggregate["total_items"] += module_total
            aggregate["desvios"] += module_desvios
            if module_record and (aggregate["last_updated_at"] is None or (module_record.updated_at and module_record.updated_at > aggregate["last_updated_at"])):
                aggregate["last_updated_at"] = module_record.updated_at
            if shift_detail.get("responsavel_pted"):
                aggregate["responsavel_pted"].add(shift_detail["responsavel_pted"])
            if shift_detail.get("responsavel_lab"):
                aggregate["responsavel_lab"].add(shift_detail["responsavel_lab"])
            for row in module_rows:
                aggregate["items"].append(
                    {
                        **row,
                        "setor": f"{turno_nome} · {row['setor']}",
                    }
                )

            macro = _macro_module_for_code(module_code)
            macro_param_totals[macro]["filled"] += module_preenchidos
            macro_param_totals[macro]["total"] += module_total
            priority_counts = _aggregate_priority_counts(module_rows)
            for priority, count in priority_counts.items():
                macro_priority_totals[macro][priority] += count

    for turno_obj in sigilatura_shifts:
        detail = build_turno_detail(session, turno_obj)
        turno_nome = f"Turno {turno_obj.turno}"
        shift_options.append(
            {
                "id": turno_obj.id,
                "turno_nome": f"{turno_nome} · Sigilatura",
                "turno_horario": None,
                "status_label": detail["status_geral_label"],
                "status_tone": "success" if detail["status_geral"] == SHIFT_STATUS_CONCLUIDO else "warning",
                "modules_progress_label": f"{detail['concluidos']}/{detail['total_modules']} módulos",
            }
        )

        for module in detail["modules"]:
            module_code = str(module["code"])
            module_total = int(module["total"])
            module_preenchidos = int(module["preenchidos"])
            module_desvios = int(module["desvios"])
            module_rows = _sigilatura_rows_for_module(session, turno_obj, module_code, item_priority_map)
            module_record = next((record for record in turno_obj.modulos if record.module_code == module_code), None)
            aggregate = module_aggregates.setdefault(
                module_code,
                {
                    "code": module_code,
                    "title": module["title"],
                    "slug": module_code,
                    "filled_items": 0,
                    "total_items": 0,
                    "desvios": 0,
                    "last_updated_at": None,
                    "responsavel_pted": set(),
                    "responsavel_lab": set(),
                    "items": [],
                    "execution_url": f"/turnos-sigilatura/{turno_obj.id}?modulo={module_code}",
                    "history_url": "/turnos-sigilatura",
                },
            )
            aggregate["filled_items"] += module_preenchidos
            aggregate["total_items"] += module_total
            aggregate["desvios"] += module_desvios
            if module_record and (aggregate["last_updated_at"] is None or (module_record.updated_at and module_record.updated_at > aggregate["last_updated_at"])):
                aggregate["last_updated_at"] = module_record.updated_at
            if detail.get("responsavel"):
                aggregate["responsavel_pted"].add(detail["responsavel"])
                aggregate["responsavel_lab"].add(detail["responsavel"])
            for row in module_rows:
                item_nome = row.get("controle") or row.get("ponto") or row.get("zona") or row.get("item") or "Item"
                observacao = row.get("observacao") or row.get("observacoes") or row.get("norma") or "—"
                aggregate["items"].append(
                    {
                        "setor": turno_nome,
                        "item_nome": str(item_nome),
                        "status_item": str(row.get("status") or "Não avaliado"),
                        "valor": _sigilatura_row_value(row) or "—",
                        "observacao": str(observacao),
                        "responsavel": str(detail.get("responsavel") or "—"),
                        "desvio": row.get("desvio") == "SIM",
                    }
                )

            macro = _macro_module_for_code(module_code)
            macro_param_totals[macro]["filled"] += module_preenchidos
            macro_param_totals[macro]["total"] += module_total
            priority_counts = _aggregate_priority_counts(module_rows)
            for priority, count in priority_counts.items():
                macro_priority_totals[macro][priority] += count

    total_turnos = len(operational_shifts) + len(sigilatura_shifts)
    if total_turnos == 0:
        return DashboardSnapshot(
            filters=filters,
            dashboard_day={
                "date_label": _format_date_label(filters.data_referencia),
                "shift_count": 0,
                "turnos_count": 0,
                "filled_items": 0,
                "total_items": 0,
                "percentual": 0,
                "total_desvios": 0,
                "progress_label": "0/0",
                "modulos_concluidos": 0,
                "modulos_em_andamento": 0,
            },
            has_global_alert=False,
            global_alert_message="Nenhum turno encontrado para a data selecionada.",
            metrics=[],
            chart_parametros=[
                _empty_chart_row(macro, [("realizado", "Realizado/Iniciado"), ("nao_realizado", "Não realizado/Não iniciado")])
                for macro in MACRO_MODULE_ORDER
            ],
            chart_prioridades=[
                _empty_chart_row(macro, [("baixo", "Baixo"), ("medio", "Médio"), ("alto", "Alto")])
                for macro in MACRO_MODULE_ORDER
            ],
            module_cards=[],
            shift_options=[],
            selected_shift=None,
            empty_state_message="Nenhum turno encontrado para a data selecionada. Escolha outra data para visualizar o dashboard do dia.",
        )

    module_cards: list[dict[str, Any]] = []
    total_items = 0
    total_preenchidos = 0
    total_desvios = 0
    modulos_concluidos = 0
    modulos_andamento = 0
    modulos_nao_iniciados = 0

    for aggregate in sorted(module_aggregates.values(), key=lambda item: item["title"].lower()):
        module_total = int(aggregate["total_items"])
        module_preenchidos = int(aggregate["filled_items"])
        module_desvios = int(aggregate["desvios"])
        total_items += module_total
        total_preenchidos += module_preenchidos
        total_desvios += module_desvios

        if module_total > 0 and module_preenchidos >= module_total:
            module_status = MODULE_STATUS_CONCLUIDO
            modulos_concluidos += 1
        elif module_preenchidos > 0:
            module_status = MODULE_STATUS_EM_ANDAMENTO
            modulos_andamento += 1
        else:
            module_status = MODULE_STATUS_NAO_INICIADO
            modulos_nao_iniciados += 1

        status_label, status_tone = _module_status_view(module_status, module_desvios > 0)
        module_percentual = int(round((module_preenchidos / module_total) * 100)) if module_total > 0 else 0
        responsavel_pted = ", ".join(sorted(aggregate["responsavel_pted"])) or "—"
        responsavel_lab = ", ".join(sorted(aggregate["responsavel_lab"])) or "—"
        last_updated = _format_datetime(aggregate["last_updated_at"])
        module_cards.append(
            {
                "code": aggregate["code"],
                "title": aggregate["title"],
                "status_label": status_label,
                "status_tone": status_tone,
                "responsavel_pted": responsavel_pted,
                "responsavel_lab": responsavel_lab,
                "desvios": module_desvios,
                "progress_percent": module_percentual,
                "filled_items": module_preenchidos,
                "total_items": module_total,
                "progress_label": f"{module_preenchidos}/{module_total} itens preenchidos",
                "percent_label": f"{module_percentual}%",
                "last_updated": last_updated,
                "execution_url": aggregate["execution_url"],
                "history_url": aggregate["history_url"],
                "modal": {
                    "nome_modulo": aggregate["title"],
                    "data": _format_date_label(filters.data_referencia),
                    "turno": f"{total_turnos} turnos no dia",
                    "turno_horario": "",
                    "status": status_label,
                    "responsavel_pted": responsavel_pted,
                    "responsavel_lab": responsavel_lab,
                    "progress_percent": module_percentual,
                    "progress_label": f"{module_preenchidos}/{module_total}",
                    "desvios": module_desvios,
                    "last_updated": last_updated,
                    "items": [item for item in aggregate["items"] if item.get("desvio")],
                    "execution_url": aggregate["execution_url"],
                    "history_url": aggregate["history_url"],
                },
            }
        )

    percentual_geral = int(round((total_preenchidos / total_items) * 100)) if total_items > 0 else 0
    metrics = [
        {"label": "Turnos no dia", "value": total_turnos, "tone": "neutral"},
        {"label": "Módulos concluídos", "value": modulos_concluidos, "tone": "success"},
        {"label": "Módulos em andamento", "value": modulos_andamento, "tone": "warning"},
        {"label": "Desvios no dia", "value": total_desvios, "tone": "alert" if total_desvios > 0 else "neutral"},
    ]

    chart_parametros = [
        _build_chart_row(
            macro,
            int(macro_param_totals[macro]["total"]),
            [
                ("realizado", "Realizado/Iniciado", int(macro_param_totals[macro]["filled"])),
                (
                    "nao_realizado",
                    "Não realizado/Não iniciado",
                    max(int(macro_param_totals[macro]["total"]) - int(macro_param_totals[macro]["filled"]), 0),
                ),
            ],
        )
        for macro in MACRO_MODULE_ORDER
    ]
    chart_prioridades = [
        _build_chart_row(
            macro,
            sum(int(macro_priority_totals[macro][priority]) for priority in PRIORITY_ORDER),
            [(priority, PRIORIDADE_LABELS[priority], int(macro_priority_totals[macro][priority])) for priority in PRIORITY_ORDER],
        )
        for macro in MACRO_MODULE_ORDER
    ]

    return DashboardSnapshot(
        filters=filters,
        dashboard_day={
            "date_label": _format_date_label(filters.data_referencia),
            "shift_count": total_turnos,
            "turnos_count": total_turnos,
            "filled_items": total_preenchidos,
            "total_items": total_items,
            "percentual": percentual_geral,
            "total_desvios": total_desvios,
            "progress_label": f"{total_preenchidos}/{total_items}",
            "modulos_concluidos": modulos_concluidos,
            "modulos_em_andamento": modulos_andamento,
        },
        has_global_alert=total_desvios > 0,
        global_alert_message=(
            "Atenção: existem desvios operacionais no dia."
            if total_desvios > 0
            else "Dia sem desvios ativos no momento."
        ),
        metrics=metrics,
        chart_parametros=chart_parametros,
        chart_prioridades=chart_prioridades,
        module_cards=module_cards,
        shift_options=shift_options,
        selected_shift=None,
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
