from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import (
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
    build_general_history,
    build_sector_view,
    context_to_form_values,
    get_master_by_shift,
    get_module_config,
    list_all_modules,
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


def _shift_execution_url(shift_id: int, module_code: str | None = None, setor: str | None = None) -> str:
    url = f"/turnos/{shift_id}"
    params: list[str] = []
    if module_code:
        params.append(f"modulo={module_code}")
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
    turno = (request.query_params.get("turno") or "").strip() or None
    modulo = (request.query_params.get("modulo") or "").strip() or None
    setor = (request.query_params.get("setor") or "").strip() or None
    responsavel = (request.query_params.get("responsavel") or "").strip() or None
    status = (request.query_params.get("status") or "").strip() or None
    visao = (request.query_params.get("visao") or "modulos").strip().lower()
    if visao not in {"modulos", "turnos"}:
        visao = "modulos"
    return ReportFilters(
        data_inicio=_coerce_date(data_inicio_raw, None) if data_inicio_raw else None,
        data_fim=_coerce_date(data_fim_raw, None) if data_fim_raw else None,
        turno=turno,
        modulo=modulo,
        setor=setor,
        responsavel=responsavel,
        status=status,
        visao=visao,
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
) -> dict:
    config = get_module_config(module_code)
    master = get_master_by_shift(db, shift.id, config.code)
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
        "execution_save_base_url": f"/turnos/{shift.id}/modulos/{config.code}/setores",
        "turnos_url": "/turno-atual",
        "inherited_context": inherited_context,
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
    status_code: int = 200,
):
    shift = get_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")

    shift_detail = build_shift_detail(db, shift)
    active_module_code = _resolve_active_module(shift_detail, module_code)
    module_state = _build_module_execution_state(
        db,
        shift,
        shift_detail,
        active_module_code,
        source,
        error_message=error_message,
        active_sector=active_sector,
    )

    context = {
        "request": request,
        "page_title": f"Execução do Turno {shift_detail['data_label']}",
        "page_description": "Execução principal do turno com os oito módulos do mesmo turno mestre.",
        "shift": shift_detail,
        "active_module_code": active_module_code,
        "module_state": module_state,
        "setor_sequence": module_state["module_config"].sector_sequence,
        "setor_labels": SETOR_LABELS,
        "schema_error_message": None if operational_schema_available(db) and shift_schema_available(db) else MISSING_SCHEMA_MESSAGE,
        **layout_context(str(request.url.path), active_path="/turno-atual", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="turnos_execution.html", context=context, status_code=status_code)


def _render_turnos_index(
    request: Request,
    db: Session,
    *,
    error_message: str | None = None,
    form_data: dict | None = None,
    open_start_modal: bool = False,
):
    options = shift_list_options(db)
    active_tab = request.query_params.get("tab")
    if active_tab not in {"andamento", "concluidos"}:
        active_tab = "andamento"

    shifts = build_shifts_history(db, limit=100) if shift_schema_available(db) else []
    shifts_em_andamento = [shift for shift in shifts if shift["status_geral"] != SHIFT_STATUS_CONCLUIDO]
    shifts_concluidos = [shift for shift in shifts if shift["status_geral"] == SHIFT_STATUS_CONCLUIDO]

    context = {
        "request": request,
        "page_title": "Turnos",
        "page_description": "Entrada operacional principal para iniciar e acompanhar turnos.",
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
        **layout_context(str(request.url.path), active_path="/turno-atual", scope_source=request.query_params),
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
        "page_description": "Visao consolidada do modelo operacional.",
        "filters": snapshot.filters,
        "has_global_alert": snapshot.has_global_alert,
        "global_alert_message": snapshot.global_alert_message,
        "metrics": snapshot.metrics,
        "module_cards": snapshot.module_cards,
        "occurrences": snapshot.occurrences,
        "pending_summary": snapshot.pending_summary,
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
    return _render_turnos_index(request, db)


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
        )
        return RedirectResponse(url=_shift_execution_url(shift.id), status_code=303)
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
        )


@router.get("/turnos/{shift_id}", name="turno_execucao")
def turno_execucao(
    shift_id: int,
    request: Request,
    modulo: str | None = None,
    setor: str | None = None,
    db: Session = Depends(get_db),
):
    return _render_shift_execution(request, db, shift_id, modulo, active_sector=setor)


@router.post("/turnos/{shift_id}/concluir", name="turno_concluir")
def turno_concluir(
    shift_id: int,
    db: Session = Depends(get_db),
):
    shift = get_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno nao encontrado")

    conclude_shift(db, shift)
    return RedirectResponse(url="/turno-atual?tab=concluidos", status_code=303)


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
        return RedirectResponse(url=_shift_execution_url(shift_id, config.code, setor_tipo), status_code=303)
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
        )


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
        filters = ReportFilters(data_inicio=today, data_fim=today, visao="modulos")
        validation_error = None
        snapshot = build_reports_snapshot(db, filters)
    else:
        filters = _parse_report_filters(request)
        if not filters.data_inicio or not filters.data_fim:
            validation_error = "Informe data inicial e data final para consultar relatorios."
            snapshot = {"rows": [], "metrics": []}
        else:
            validation_error = None
            snapshot = build_reports_snapshot(db, filters)
    options = report_filter_options(db)
    query = {
        key: value
        for key, value in {
            "data_inicio": request.query_params.get("data_inicio", ""),
            "data_fim": request.query_params.get("data_fim", ""),
            "turno": filters.turno or "",
            "modulo": filters.modulo or "",
            "setor": filters.setor or "",
            "responsavel": filters.responsavel or "",
            "status": filters.status or "",
            "visao": filters.visao,
        }.items()
        if value
    }
    pdf_export_url = "/relatorios/pdf"
    if query:
        pdf_export_url += "?" + urlencode(query)

    context = {
        "request": request,
        "page_title": "Relatorios",
        "page_description": "Consulta consolidada por turno, modulo, setor e responsavel.",
        "validation_error": validation_error,
        "filters": filters,
        "rows": snapshot["rows"],
        "metrics": snapshot["metrics"],
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
    pdf_url = f"/{detail['module_config'].slug}/registros/{record_id}/relatorio"
    if setor:
        pdf_url += f"?setor={setor}"
    context = {
        "request": request,
        "page_title": detail["module_config"].report_title,
        "page_description": "Consulta detalhada do modulo.",
        "pdf_url": pdf_url,
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


@router.get("/historico-geral", name="historico_geral")
def historico_geral(request: Request, db: Session = Depends(get_db)):
    data_inicio_str = request.query_params.get("data_inicio")
    data_fim_str = request.query_params.get("data_fim")
    turno = request.query_params.get("turno") or None
    status = request.query_params.get("status") or None
    modulo = request.query_params.get("modulo") or None

    data_inicio = _coerce_date(data_inicio_str, None) if data_inicio_str else None
    data_fim = _coerce_date(data_fim_str, None) if data_fim_str else None

    if shift_schema_available(db):
        shifts = build_shifts_history(
            db,
            data_inicio=data_inicio,
            data_fim=data_fim,
            turno=turno,
            status=status,
        )
        use_shift_history = True
    else:
        shifts = build_general_history(
            db,
            data_inicio=data_inicio,
            data_fim=data_fim,
            turno=turno,
            module_code=modulo,
            status=status,
        )
        use_shift_history = False

    options = shift_list_options(db)
    context = {
        "request": request,
        "page_title": "Historico Geral",
        "page_description": "Consulta consolidada de turnos e modulos.",
        "shifts": shifts,
        "turnos": options.get("turnos", []),
        "modulos": list_all_modules(),
        "selected_data_inicio": data_inicio_str or "",
        "selected_data_fim": data_fim_str or "",
        "selected_turno": turno,
        "selected_status": status,
        "selected_modulo": modulo,
        "use_shift_history": use_shift_history,
        "status_options": [
            {"value": SHIFT_STATUS_NAO_INICIADO, "label": "Nao iniciado"},
            {"value": SHIFT_STATUS_EM_ANDAMENTO, "label": "Em andamento"},
            {"value": SHIFT_STATUS_PARCIAL, "label": "Parcial"},
            {"value": SHIFT_STATUS_CONCLUIDO, "label": "Concluido"},
        ],
        "MODULE_STATUS_NAO_INICIADO": MODULE_STATUS_NAO_INICIADO,
        "MODULE_STATUS_EM_ANDAMENTO": MODULE_STATUS_EM_ANDAMENTO,
        "MODULE_STATUS_PARCIAL": MODULE_STATUS_PARCIAL,
        "MODULE_STATUS_CONCLUIDO": MODULE_STATUS_CONCLUIDO,
        "SHIFT_STATUS_NAO_INICIADO": SHIFT_STATUS_NAO_INICIADO,
        "SHIFT_STATUS_EM_ANDAMENTO": SHIFT_STATUS_EM_ANDAMENTO,
        "SHIFT_STATUS_PARCIAL": SHIFT_STATUS_PARCIAL,
        "SHIFT_STATUS_CONCLUIDO": SHIFT_STATUS_CONCLUIDO,
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="historico_geral.html", context=context)
