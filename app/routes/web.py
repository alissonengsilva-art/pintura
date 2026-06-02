from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import (
    Modelo,
    OperationalModuleItem,
    SHIFT_STATUS_CONCLUIDO,
    SHIFT_STATUS_EM_ANDAMENTO,
    SHIFT_STATUS_NAO_INICIADO,
    SHIFT_STATUS_PARCIAL,
)
from app.services import item_frequency_runtime_service
from app.services.dashboard_service import (
    DashboardValidationError,
    build_dashboard_snapshot,
    build_pending_list_snapshot,
    parse_dashboard_filters,
    parse_pending_filters,
)
from app.services.navigation import layout_context
from app.services.operational_module_service import (
    MODULE_STATUS_CONCLUIDO,
    MODULE_STATUS_EM_ANDAMENTO,
    MODULE_STATUS_NAO_INICIADO,
    MODULE_STATUS_PARCIAL,
    MISSING_SCHEMA_MESSAGE,
    STATUS_LABELS,
    SETOR_LABELS,
    SETOR_SEQUENCE,
    build_context_from_source,
    build_sector_view,
    context_to_form_values,
    get_master_by_shift,
    list_masters_by_shift_module,
    get_module_config,
    operational_schema_available,
    resolve_context_defaults,
    save_sector,
)
from app.services.report_service import (
    ReportFilters,
    build_module_report_detail,
    build_reports_snapshot,
    build_shift_report_detail,
    build_shift_pdf_context,
    report_filter_options,
)
from app.services.shift_service import (
    ShiftValidationError,
    build_shift_detail,
    build_shifts_history,
    conclude_shift,
    create_shift,
    get_shift_by_id,
    list_shared_options as shift_list_options,
    shift_schema_available,
    update_shift_status,
)


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter()

PT_MODULE_CODES = ["pt", "pressao-filtros-pt"]
ED_MODULE_CODES = [
    "ed",
    "temperatura-forno-ed",
  
    "tensao-retificadores-ed",
    "poder-penetracao",
    "espessura-ed",
    "aspecto",
    "rugosidade",
]


def _module_codes_for_scope(operation_scope: str) -> list[str]:
    return PT_MODULE_CODES if operation_scope == "pt" else ED_MODULE_CODES


def _shift_execution_url(
    shift_id: int,
    module_code: str | None = None,
    setor: str | None = None,
    grupo_retificador: str | None = None,
    *,
    operation_scope: str = "ed",
) -> str:
    url = f"/turnos/{shift_id}"
    if operation_scope == "pt":
        url = f"/turnos-pt/{shift_id}"
    params: list[str] = []
    if module_code:
        params.append(f"modulo={module_code}")
    if grupo_retificador:
        params.append(f"grupo_retificador={grupo_retificador}")
    if setor:
        params.append(f"setor={setor}")
    if params:
        url += "?" + "&".join(params)
    return url


def _coerce_date(raw_value: str | None, fallback: date | None = None) -> date | None:
    if raw_value:
        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            pass
    if fallback is not None:
        return fallback
    return date.today()


def _parse_report_filters(request: Request) -> ReportFilters:
    data_inicio_raw = (request.query_params.get("data_inicio") or "").strip()
    data_fim_raw = (request.query_params.get("data_fim") or "").strip()
    modulo = (request.query_params.get("modulo") or "").strip() or None
    parametro = (request.query_params.get("parametro") or "").strip() or None
    setor = (request.query_params.get("setor") or "").strip() or None
    prioridade = (request.query_params.get("prioridade") or "").strip().lower() or None
    if prioridade not in {None, "baixo", "medio", "alto"}:
        prioridade = None
    agrupamento = (request.query_params.get("agrupamento") or "dia").strip().lower()
    if agrupamento not in {"dia", "modulo", "parametro"}:
        agrupamento = "dia"
    turno = (request.query_params.get("turno") or "").strip() or None
    responsavel = (request.query_params.get("responsavel") or "").strip() or None
    status = (request.query_params.get("status") or "").strip() or None
    return ReportFilters(
        data_inicio=_coerce_date(data_inicio_raw, None) if data_inicio_raw else None,
        data_fim=_coerce_date(data_fim_raw, None) if data_fim_raw else None,
        modulo=modulo,
        parametro=parametro,
        setor=setor,
        prioridade=prioridade,
        agrupamento=agrupamento,
        turno=turno,
        responsavel=responsavel,
        status=status,
    )


def _resolve_active_module(shift_detail: dict, requested_module: str | None) -> str:
    modules = shift_detail.get("modules", [])
    available_codes = [module["code"] for module in modules]
    if requested_module in available_codes:
        return str(requested_module)
    for module in modules:
        if module["status_geral"] != MODULE_STATUS_CONCLUIDO:
            return module["code"]
    return available_codes[0] if available_codes else "ed"


def _build_module_execution_state(
    db: Session,
    shift,
    shift_detail: dict,
    module_code: str,
    source=None,
    *,
    error_message: str | None = None,
    active_sector: str | None = None,
    operation_scope: str = "ed",
) -> dict:
    def _rehydrate_rows_from_source(setor_views: list[dict], payload) -> None:
        if payload is None or not hasattr(payload, "get"):
            return
        for setor_view in setor_views:
            setor_tipo = str(setor_view.get("setor_tipo") or "")
            if not setor_tipo:
                continue
            observacoes_setor = payload.get(f"observacoes_setor_{setor_tipo}")
            if observacoes_setor is not None:
                setor_view["observacoes_setor"] = str(observacoes_setor)
            for row in setor_view.get("rows", []):
                reference = str(row.get("reference") or "")
                if not reference:
                    continue
                value_key = f"value_{setor_tipo}_{reference}"
                obs_key = f"obs_{setor_tipo}_{reference}"
                if payload.get(value_key) is not None:
                    row["value"] = str(payload.get(value_key) or "")
                if payload.get(obs_key) is not None:
                    row["row_observation"] = str(payload.get(obs_key) or "")
                # Preserve custom input columns (ex: aspecto e observacao por linha).
                for field_key in list(row.keys()):
                    if field_key in {"reference", "order", "status_label", "flag", "item_id"}:
                        continue
                    custom_key = f"{field_key}_{setor_tipo}_{reference}"
                    if payload.get(custom_key) is not None:
                        row[field_key] = str(payload.get(custom_key) or "")

    config = get_module_config(module_code)
    selected_group = None
    if source is not None and hasattr(source, "get"):
        selected_group = str(source.get("grupo_retificador") or "").strip().lower() or None
    master = get_master_by_shift(db, shift.id, config.code)
    group_summaries: list[dict] = []
    if config.code == "tensao-retificadores-ed":
        masters = list_masters_by_shift_module(db, shift.id, config.code)
        group_map = {str((item.context_data or {}).get("grupo_retificador") or "").strip().lower(): item for item in masters}
        ordered_groups = [
            ("grupo_1", "Grupo 1"),
            ("grupo_2", "Grupo 2"),
            ("grupo_3", "Grupo 3"),
        ]
        if selected_group in group_map:
            master = group_map[selected_group]
        elif selected_group:
            master = None
        for group_code, group_label in ordered_groups:
            group_master = group_map.get(group_code)
            group_models = list(
                db.scalars(
                    select(Modelo)
                    .where(Modelo.ativo.is_(True))
                    .where(Modelo.grupo_retificador == group_code)
                    .order_by(Modelo.nome, Modelo.codigo)
                ).all()
            )
            group_models_label = ", ".join(
                f"{str(model.nome or '').strip()}{f' ({str(model.codigo or '').strip()})' if str(model.codigo or '').strip() else ''}"
                for model in group_models
            ) or "Sem modelos"
            has_flag = False
            status = MODULE_STATUS_NAO_INICIADO
            if group_master is not None:
                status = group_master.status_geral
                for sector in group_master.setores:
                    if int((sector.metricas or {}).get("flag_count", 0)) > 0:
                        has_flag = True
                if status == MODULE_STATUS_CONCLUIDO and has_flag:
                    status = MODULE_STATUS_PARCIAL
            group_summaries.append(
                {
                    "code": group_code,
                    "label": group_label,
                    "status": status,
                    "status_label": STATUS_LABELS.get(status, "Não iniciado"),
                    "has_flag": has_flag,
                    "models_label": group_models_label,
                }
            )
    context_options: dict = {}

    if master:
        parsed_context = build_context_from_source(config, master.context_data)
        context_options = resolve_context_defaults(config, db, master.context_data)[1]
        context_locked = True
    else:
        base_source = {"data_referencia": shift.data_referencia.isoformat()}
        if shift.turno and config.supports_turno:
            base_source["turno"] = shift.turno

        merged_source = dict(base_source)
        if source is not None and hasattr(source, "get"):
            for field in config.context_fields:
                value = source.get(field.name)
                if value not in (None, ""):
                    merged_source[field.name] = value

        defaults, context_options = resolve_context_defaults(config, db, merged_source)
        for key, value in base_source.items():
            defaults[key] = value
        parsed_context = build_context_from_source(config, defaults)
        context_locked = False

    setor_views = [build_sector_view(db, config, parsed_context, master, setor) for setor in config.sector_sequence]
    if source is not None and error_message:
        _rehydrate_rows_from_source(setor_views, source)
    module_summary = next((module for module in shift_detail["modules"] if module["code"] == config.code), None)

    inherited_context = {
        "data": shift.data_referencia.strftime("%d/%m/%Y"),
        "turno": shift.turno,
        "responsavel_pted": shift.responsavel_pted,
        "responsavel_lab": shift.responsavel_lab,
    }
    parsed_context["shift_id"] = shift.id

    extra_context_fields = [
        field
        for field in config.context_fields
        if field.name != "data_referencia" and not (field.name == "turno" and shift.turno and config.supports_turno)
    ]
    if config.code == "ed":
        extra_context_fields = [field for field in extra_context_fields if field.name != "tipo_dia"]
    if config.code == "tensao-retificadores-ed":
        extra_context_fields = [field for field in extra_context_fields if field.name != "grupo_retificador"]

    status_geral_label = module_summary["status_badge_tone"] if module_summary else (master.status_geral if master else MODULE_STATUS_NAO_INICIADO)
    status_geral_texto = module_summary["status_geral_label"] if module_summary else (STATUS_LABELS[master.status_geral] if master else STATUS_LABELS[MODULE_STATUS_NAO_INICIADO])

    return {
        "module_config": config,
        "module_summary": module_summary,
        "master": master,
        "context_values": context_to_form_values(config, parsed_context),
        "context_fields": config.context_fields,
        "context_options": context_options,
        "extra_context_fields": extra_context_fields,
        "context_locked": context_locked,
        "setor_views": setor_views,
        "status_geral_label": status_geral_label,
        "status_geral_texto": status_geral_texto,
        "error_message": error_message,
        "active_sector": active_sector if active_sector in config.sector_sequence else config.sector_sequence[0],
        "execution_url": _shift_execution_url(shift.id, config.code),
        "execution_save_base_url": (
            f"/turnos-pt/{shift.id}/modulos/{config.code}/setores"
            if operation_scope == "pt"
            else f"/turnos/{shift.id}/modulos/{config.code}/setores"
        ),
        "turnos_url": "/turnos-pt" if operation_scope == "pt" else "/turno-atual",
        "inherited_context": inherited_context,
        "retificador_groups": group_summaries,
        "active_retificador_group": str(parsed_context.get("grupo_retificador") or ""),
        "retificador_models": [
            {
                "id": int(getattr(model, "id", 0)),
                "nome": str(getattr(model, "nome", "") or ""),
                "codigo": str(getattr(model, "codigo", "") or ""),
            }
            for model in context_options.get("modelos", [])
        ] if config.code == "tensao-retificadores-ed" else [],
    }


def _render_shift_execution(
    request: Request,
    db: Session,
    shift_id: int,
    module_code: str | None,
    *,
    source=None,
    error_message: str | None = None,
    active_sector: str | None = None,
    readonly_mode: bool = False,
    status_code: int = 200,
    operation_scope: str = "ed",
    module_codes: list[str] | None = None,
):
    shift = get_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")

    shift_detail = build_shift_detail(db, shift, module_codes=module_codes)
    active_module_code = _resolve_active_module(shift_detail, module_code)
    module_state = _build_module_execution_state(
        db,
        shift,
        shift_detail,
        active_module_code,
        source,
        error_message=error_message,
        active_sector=active_sector,
        operation_scope=operation_scope,
    )

    context = {
        "request": request,
        "page_title": f"{'Relatório final do Turno' if readonly_mode else 'Execução do Turno'} {shift_detail['data_label']}",
        "page_description": "Visualização somente leitura do turno concluído." if readonly_mode else "Execução principal do turno com os oito módulos do mesmo turno mestre.",
        "shift": shift_detail,
        "active_module_code": active_module_code,
        "module_state": module_state,
        "readonly_mode": readonly_mode,
        "setor_sequence": module_state["module_config"].sector_sequence,
        "setor_labels": SETOR_LABELS,
        "schema_error_message": None if operational_schema_available(db) and shift_schema_available(db) else MISSING_SCHEMA_MESSAGE,
        **layout_context(
            str(request.url.path),
            active_path="/turnos-pt" if operation_scope == "pt" else "/turno-atual",
            scope_source=request.query_params,
        ),
    }
    return templates.TemplateResponse(request=request, name="turnos_execution.html", context=context, status_code=status_code)


def _render_turnos_index(
    request: Request,
    db: Session,
    *,
    error_message: str | None = None,
    form_data: dict | None = None,
    open_start_modal: bool = False,
    operation_scope: str = "ed",
    module_codes: list[str] | None = None,
):
    options = shift_list_options(db)
    active_tab = request.query_params.get("tab")
    if active_tab not in {"andamento", "concluidos"}:
        active_tab = "andamento"

    shifts = (
        build_shifts_history(
            db,
            limit=100,
            operation_scope=operation_scope,
            module_codes=module_codes,
        )
        if shift_schema_available(db)
        else []
    )
    shifts_em_andamento = [shift for shift in shifts if shift["status_geral"] != SHIFT_STATUS_CONCLUIDO]
    shifts_concluidos = [shift for shift in shifts if shift["status_geral"] == SHIFT_STATUS_CONCLUIDO]

    context = {
        "request": request,
        "page_title": "Turnos",
        "page_description": "Entrada operacional principal para iniciar e acompanhar turnos.",
        "operation_scope": operation_scope,
        "is_pt_operation": operation_scope == "pt",
        "active_tab": active_tab,
        "shifts_em_andamento": shifts_em_andamento,
        "shifts_concluidos": shifts_concluidos,
        "turnos": options.get("turnos", []),
        "responsaveis": options.get("responsaveis", []),
        "data_hoje": date.today().isoformat(),
        "error_message": error_message,
        "form_data": form_data or {},
        "open_start_modal": open_start_modal or request.query_params.get("modal") == "iniciar",
        "schema_error_message": None if shift_schema_available(db) else MISSING_SCHEMA_MESSAGE,
        **layout_context(
            str(request.url.path),
            active_path="/turnos-pt" if operation_scope == "pt" else "/turno-atual",
            scope_source=request.query_params,
        ),
    }
    return templates.TemplateResponse(request=request, name="turnos_index.html", context=context)


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/dashboard", name="dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    error_message = None
    try:
        filters = parse_dashboard_filters(request.query_params, db)
    except DashboardValidationError as error:
        error_message = str(error)
        filters = parse_dashboard_filters({}, db)
    snapshot = build_dashboard_snapshot(db, filters)
    context = {
        "request": request,
        "page_title": "Dashboard Operacional",
        "page_description": "Acompanhamento operacional por data e turno.",
        "filters": snapshot.filters,
        "has_global_alert": snapshot.has_global_alert,
        "global_alert_message": snapshot.global_alert_message,
        "metrics": snapshot.metrics,
        "module_cards": snapshot.module_cards,
        "shift_options": snapshot.shift_options,
        "selected_shift": snapshot.selected_shift,
        "empty_state_message": snapshot.empty_state_message,
        "error_message": error_message,
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)


@router.get("/pendencias", name="pendencias")
def pendencias(request: Request, db: Session = Depends(get_db)):
    error_message = None
    try:
        filters = parse_pending_filters(request.query_params, db)
    except DashboardValidationError as error:
        error_message = str(error)
        filters = parse_pending_filters({}, db)
    snapshot = build_pending_list_snapshot(db, filters)
    context = {
        "request": request,
        "page_title": "Pendencias",
        "page_description": "Pendencias operacionais do turno mestre.",
        "filters": snapshot.filters,
        "status_metrics": snapshot.status_metrics,
        "rows": snapshot.rows,
        "error_message": error_message,
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="pendencias.html", context=context)


@router.get("/turno-atual", name="turno_atual")
def turno_atual(request: Request, db: Session = Depends(get_db)):
    return _render_turnos_index(request, db, operation_scope="ed", module_codes=ED_MODULE_CODES)


@router.get("/turno-atual/iniciar", name="turno_iniciar")
def turno_iniciar_form():
    return RedirectResponse(url="/turno-atual?modal=iniciar", status_code=302)


@router.post("/turno-atual/iniciar", name="turno_iniciar_post")
def turno_iniciar_post(
    request: Request,
    db: Session = Depends(get_db),
    data_referencia: str = Form(...),
    turno: str = Form(None),
    responsavel_pted: str = Form(None),
    responsavel_lab: str = Form(None),
    observacoes: str = Form(None),
):
    data_ref = _coerce_date(data_referencia)
    turno_value = turno.strip() if turno else None
    try:
        shift = create_shift(
            session=db,
            data_referencia=data_ref,
            turno=turno_value,
            responsavel_pted=responsavel_pted.strip() if responsavel_pted else None,
            responsavel_lab=responsavel_lab.strip() if responsavel_lab else None,
            observacoes=observacoes.strip() if observacoes else None,
            operation_scope="ed",
        )
        return RedirectResponse(url=_shift_execution_url(shift.id, operation_scope="ed"), status_code=303)
    except ShiftValidationError as error:
        return _render_turnos_index(
            request,
            db,
            error_message=str(error),
            form_data={
                "data_referencia": data_referencia,
                "turno": turno,
                "responsavel_pted": responsavel_pted,
                "responsavel_lab": responsavel_lab,
                "observacoes": observacoes,
            },
            open_start_modal=True,
            operation_scope="ed",
        )


@router.get("/turnos-pt", name="turnos_pt")
def turnos_pt(request: Request, db: Session = Depends(get_db)):
    return _render_turnos_index(request, db, operation_scope="pt", module_codes=PT_MODULE_CODES)


@router.get("/turnos-pt/iniciar", name="turno_pt_iniciar")
def turno_pt_iniciar_form():
    return RedirectResponse(url="/turnos-pt?modal=iniciar", status_code=302)


@router.post("/turnos-pt/iniciar", name="turno_pt_iniciar_post")
def turno_pt_iniciar_post(
    request: Request,
    db: Session = Depends(get_db),
    data_referencia: str = Form(...),
    turno: str = Form(None),
    responsavel_pted: str = Form(None),
):
    data_ref = _coerce_date(data_referencia)
    turno_value = turno.strip() if turno else None
    try:
        shift = create_shift(
            session=db,
            data_referencia=data_ref,
            turno=turno_value,
            responsavel_pted=responsavel_pted.strip() if responsavel_pted else None,
            responsavel_lab=None,
            observacoes=None,
            operation_scope="pt",
            module_codes=["pt", "pressao-filtros-pt"],
        )
        return RedirectResponse(url=_shift_execution_url(shift.id, operation_scope="pt"), status_code=303)
    except ShiftValidationError as error:
        return _render_turnos_index(
            request,
            db,
            error_message=str(error),
            form_data={
                "data_referencia": data_referencia,
                "turno": turno,
                "responsavel_pted": responsavel_pted,
            },
            open_start_modal=True,
            operation_scope="pt",
            module_codes=PT_MODULE_CODES,
        )


@router.get("/turnos/{shift_id}", name="turno_execucao")
def turno_execucao(
    shift_id: int,
    request: Request,
    modulo: str | None = None,
    grupo_retificador: str | None = None,
    setor: str | None = None,
    db: Session = Depends(get_db),
):
    shift = get_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")
    route_scope = "pt" if request.url.path.startswith("/turnos-pt") else "ed"
    shift_scope = getattr(shift, "operation_scope", "ed")
    if route_scope != shift_scope:
        target_base = "/turnos-pt" if shift_scope == "pt" else "/turnos"
        query_parts: list[str] = []
        if modulo:
            query_parts.append(f"modulo={modulo}")
        if grupo_retificador:
            query_parts.append(f"grupo_retificador={grupo_retificador}")
        if setor:
            query_parts.append(f"setor={setor}")
        query = f"?{'&'.join(query_parts)}" if query_parts else ""
        return RedirectResponse(url=f"{target_base}/{shift_id}{query}", status_code=303)
    if shift.status_geral == SHIFT_STATUS_CONCLUIDO:
        operation_scope = route_scope
        query_parts: list[str] = []
        if modulo:
            query_parts.append(f"modulo={modulo}")
        if setor:
            query_parts.append(f"setor={setor}")
        query = f"?{'&'.join(query_parts)}" if query_parts else ""
        base = "/turnos-pt" if operation_scope == "pt" else "/turnos"
        return RedirectResponse(url=f"{base}/{shift_id}/visualizar{query}", status_code=303)
    operation_scope = route_scope
    module_codes = _module_codes_for_scope(operation_scope)
    return _render_shift_execution(
        request,
        db,
        shift_id,
        modulo,
        source=request.query_params,
        active_sector=setor,
        operation_scope=operation_scope,
        module_codes=module_codes,
    )


@router.get("/turnos/{shift_id}/visualizar", name="turno_visualizacao")
def turno_visualizacao(shift_id: int, request: Request, db: Session = Depends(get_db)):
    shift = get_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")
    modulo = request.query_params.get("modulo")
    grupo_retificador = request.query_params.get("grupo_retificador")
    setor = request.query_params.get("setor")
    operation_scope = "pt" if request.url.path.startswith("/turnos-pt") else "ed"
    module_codes = _module_codes_for_scope(operation_scope)
    return _render_shift_execution(
        request,
        db,
        shift_id,
        modulo,
        source={"grupo_retificador": grupo_retificador} if grupo_retificador else request.query_params,
        active_sector=setor,
        readonly_mode=True,
        operation_scope=operation_scope,
        module_codes=module_codes,
    )


@router.post("/turnos/{shift_id}/concluir", name="turno_concluir")
def turno_concluir(
    shift_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    shift = get_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")

    try:
        operation_scope = "pt" if request.url.path.startswith("/turnos-pt") else "ed"
        required_modules = PT_MODULE_CODES if operation_scope == "pt" else ["ed"]
        conclude_shift(db, shift, required_module_codes=required_modules)
        return RedirectResponse(url="/turnos-pt?tab=concluidos" if operation_scope == "pt" else "/turno-atual?tab=concluidos", status_code=303)
    except ShiftValidationError as error:
        modulo = request.query_params.get("modulo")
        setor = request.query_params.get("setor")
        operation_scope = "pt" if request.url.path.startswith("/turnos-pt") else "ed"
        module_codes = _module_codes_for_scope(operation_scope)
        return _render_shift_execution(
            request,
            db,
            shift_id,
            modulo,
            active_sector=setor,
            error_message=str(error),
            status_code=400,
            operation_scope=operation_scope,
            module_codes=module_codes,
        )


@router.get("/turnos-pt/{shift_id}", name="turno_pt_execucao")
def turno_pt_execucao(
    shift_id: int,
    request: Request,
    modulo: str | None = None,
    grupo_retificador: str | None = None,
    setor: str | None = None,
    db: Session = Depends(get_db),
):
    return turno_execucao(
        shift_id=shift_id,
        request=request,
        modulo=modulo,
        grupo_retificador=grupo_retificador,
        setor=setor,
        db=db,
    )


@router.get("/turnos-pt/{shift_id}/visualizar", name="turno_pt_visualizacao")
def turno_pt_visualizacao(shift_id: int, request: Request, db: Session = Depends(get_db)):
    return turno_visualizacao(shift_id, request, db)


@router.post("/turnos-pt/{shift_id}/concluir", name="turno_pt_concluir")
def turno_pt_concluir(shift_id: int, request: Request, db: Session = Depends(get_db)):
    return turno_concluir(shift_id, request, db)


@router.post("/turnos/{shift_id}/modulos/{module_code}/setores/{setor_tipo}/salvar", name="turno_modulo_salvar_setor")
async def turno_modulo_salvar_setor(
    shift_id: int,
    module_code: str,
    setor_tipo: str,
    request: Request,
    db: Session = Depends(get_db),
):
    config = get_module_config(module_code)
    if setor_tipo not in config.sector_sequence:
        raise HTTPException(status_code=404, detail="Setor invalido")

    shift = get_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")

    form = await request.form()
    form_data = dict(form)
    form_data["data_referencia"] = shift.data_referencia.isoformat()
    if shift.turno and config.supports_turno:
        form_data["turno"] = shift.turno

    action = "concluir" if (form.get("submit_action") or "").strip().lower() == "concluir" else "salvar"

    try:
        parsed_context = build_context_from_source(config, form_data)
        save_sector(db, config, parsed_context, setor_tipo, form, action, shift_id=shift_id)
        update_shift_status(db, shift)
        operation_scope = getattr(shift, "operation_scope", "ed")
        return RedirectResponse(
            url=_shift_execution_url(
                shift_id,
                config.code,
                setor_tipo,
                grupo_retificador=str(parsed_context.get("grupo_retificador") or "") if config.code == "tensao-retificadores-ed" else None,
                operation_scope=operation_scope,
            ),
            status_code=303,
        )
    except ValueError as error:
        return _render_shift_execution(
            request,
            db,
            shift_id,
            config.code,
            source=form_data,
            error_message=str(error),
            active_sector=setor_tipo,
            status_code=400,
            operation_scope=getattr(shift, "operation_scope", "ed"),
            module_codes=_module_codes_for_scope(getattr(shift, "operation_scope", "ed")),
        )


@router.post("/turnos-pt/{shift_id}/modulos/{module_code}/setores/{setor_tipo}/salvar", name="turno_pt_modulo_salvar_setor")
async def turno_pt_modulo_salvar_setor(
    shift_id: int,
    module_code: str,
    setor_tipo: str,
    request: Request,
    db: Session = Depends(get_db),
):
    return await turno_modulo_salvar_setor(shift_id, module_code, setor_tipo, request, db)


@router.post("/turnos/execution/{shift_id}/items/{item_id}/applicability", name="turno_item_applicability_override")
async def turno_item_applicability_override(
    shift_id: int,
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    shift = get_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")
    if shift.status_geral == SHIFT_STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/turnos/{shift_id}/visualizar?modulo={config.code}&setor={setor_tipo}", status_code=303)

    item = db.get(OperationalModuleItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item nao encontrado")

    payload = await request.json()
    override_status = str(payload.get("override_status") or "").strip().lower() or item_frequency_runtime_service.OVERRIDE_STATUS_AUTOMATIC
    reason = str(payload.get("reason") or "").strip() or None

    try:
        item_frequency_runtime_service.save_item_applicability_override(db, shift_id, item_id, override_status, reason)
    except ValueError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)

    resolved = item_frequency_runtime_service.resolve_item_applicability(
        item,
        shift.data_referencia,
        override_status,
        reason,
    )
    shift_detail = build_shift_detail(db, shift)
    module_summary = next((module for module in shift_detail["modules"] if module["code"] == item.module_code), None)

    return JSONResponse(
        {
            "success": True,
            "resolved_label": resolved["applicability_label"],
            "resolved_source": resolved["applicability_source"],
            "resolved_status": resolved["resolved_status"],
            "affects_progress": resolved["affects_progress"],
            "module_progress": module_summary,
        }
    )


@router.post("/turno-atual/{shift_id}/modulo/{module_code}/previsao", name="turno_modulo_previsao")
def turno_modulo_previsao(shift_id: int, module_code: str):
    return RedirectResponse(url=_shift_execution_url(shift_id, module_code), status_code=303)


@router.get("/turno-atual/{shift_id}/modulos/{module_code}", name="turno_modulo_executar")
def turno_modulo_executar(shift_id: int, module_code: str):
    return RedirectResponse(url=_shift_execution_url(shift_id, module_code), status_code=302)


@router.post("/turno-atual/{shift_id}/modulos/{module_code}/iniciar", name="turno_modulo_iniciar")
def turno_modulo_iniciar(shift_id: int, module_code: str):
    return RedirectResponse(url=_shift_execution_url(shift_id, module_code), status_code=303)


@router.get("/relatorios", name="relatorios")
def relatorios(request: Request, db: Session = Depends(get_db)):
    has_query = bool(request.query_params)
    if not has_query:
        today = date.today()
        filters = ReportFilters(data_inicio=today, data_fim=today, agrupamento="dia")
        validation_error = None
        snapshot = build_reports_snapshot(db, filters)
    else:
        filters = _parse_report_filters(request)
        if not filters.data_inicio or not filters.data_fim:
            validation_error = "Informe data inicial e data final para consultar relatorios."
            snapshot = {
                "rows": [],
                "metrics": [],
                "grouped": [],
                "desvios": [],
                "grouped_modulo": [],
                "percentual_desvio": 0.0,
            }
        else:
            validation_error = None
            snapshot = build_reports_snapshot(db, filters)
    options = report_filter_options(db)
    query = {
        key: value
        for key, value in {
            "data_inicio": request.query_params.get("data_inicio", ""),
            "data_fim": request.query_params.get("data_fim", ""),
            "modulo": filters.modulo or "",
            "parametro": filters.parametro or "",
            "setor": filters.setor or "",
            "prioridade": filters.prioridade or "",
            "agrupamento": filters.agrupamento,
            "turno": filters.turno or "",
            "responsavel": filters.responsavel or "",
            "status": filters.status or "",
        }.items()
        if value
    }
    pdf_export_url = "/relatorios/pdf"
    if query:
        pdf_export_url += "?" + urlencode(query)

    context = {
        "request": request,
        "page_title": "Relatorios",
        "page_description": "Análise técnica das medições operacionais dos controles.",
        "validation_error": validation_error,
        "filters": filters,
        "rows": snapshot["rows"],
        "metrics": snapshot["metrics"],
        "grouped": snapshot["grouped"],
        "percentual_desvio": snapshot["percentual_desvio"],
        "pdf_export_url": pdf_export_url,
        **options,
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="reports.html", context=context)


@router.get("/relatorios/pdf", name="relatorios_pdf")
def relatorios_pdf(request: Request, db: Session = Depends(get_db)):
    filters = _parse_report_filters(request)
    if not filters.data_inicio or not filters.data_fim:
        raise HTTPException(status_code=400, detail="Data inicial e data final sao obrigatorias.")
    snapshot = build_reports_snapshot(db, filters)
    context = {
        "request": request,
        "page_title": "Relatorios",
        "page_description": "Exportacao de relatorios",
        "filters": filters,
        "rows": snapshot["rows"],
        "metrics": snapshot["metrics"],
        "grouped": snapshot["grouped"],
        "grouped_modulo": snapshot["grouped_modulo"],
        "desvios": snapshot["desvios"],
        "percentual_desvio": snapshot["percentual_desvio"],
        "print_mode": True,
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="reports_pdf.html", context=context)


@router.get("/relatorios/visualizar/turnos/{shift_id}", name="relatorio_turno_detalhe")
def relatorio_turno_detalhe(shift_id: int, request: Request, db: Session = Depends(get_db)):
    detail = build_shift_report_detail(db, shift_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")
    context = {
        "request": request,
        "page_title": f"Relatorio do Turno {detail['data_label']}",
        "page_description": "Consulta detalhada do turno.",
        "shift": detail,
        "pdf_url": f"/relatorios/turnos/{shift_id}/pdf",
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="report_detail_shift.html", context=context)


@router.get("/relatorios/visualizar/modulos/{module_code}/{record_id}", name="relatorio_modulo_detalhe")
def relatorio_modulo_detalhe(module_code: str, record_id: int, request: Request, db: Session = Depends(get_db)):
    setor = request.query_params.get("setor") or None
    detail = build_module_report_detail(db, module_code, record_id, setor=setor)
    if detail is None:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    context = {
        "request": request,
        "page_title": detail["module_config"].report_title,
        "page_description": "Consulta detalhada do modulo.",
        "pdf_url": None,
        **detail,
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="report_detail_module.html", context=context)


@router.get("/relatorios/turnos/{shift_id}/pdf", name="relatorio_turno_pdf")
def relatorio_turno_pdf(shift_id: int, request: Request, db: Session = Depends(get_db)):
    detail = build_shift_pdf_context(db, shift_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")
    context = {
        "request": request,
        "page_title": f"Relatorio do Turno {detail['data_label']}",
        "page_description": "Relatorio completo do turno.",
        "shift": detail,
        "print_mode": True,
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="reports_shift_pdf.html", context=context)


