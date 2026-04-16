from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.navigation import layout_context
from app.services.operational_module_service import (
    MISSING_SCHEMA_MESSAGE,
    STATUS_LABELS,
    SETOR_LABELS,
    SETOR_SEQUENCE,
    build_context_from_source,
    build_detail_context,
    build_history_rows,
    build_sector_view,
    context_to_form_values,
    get_master,
    get_master_by_context,
    get_module_config,
    operational_schema_available,
    resolve_context_defaults,
    save_sector,
)


templates = Jinja2Templates(directory=str(settings.templates_dir))


def build_module_router(module_key: str) -> APIRouter:
    config = get_module_config(module_key)
    router = APIRouter(prefix=f"/{config.slug}", tags=[config.slug])

    def _base_context(request: Request, db: Session, **extra) -> dict:
        return {
            "request": request,
            "module_config": config,
            "page_title": config.title,
            "page_description": config.description,
            "setor_sequence": SETOR_SEQUENCE,
            "setor_labels": SETOR_LABELS,
            **layout_context(str(request.url.path), active_path=f"/{config.slug}", scope_source=request.query_params),
            **extra,
        }

    @router.get("")
    def module_home(request: Request, db: Session = Depends(get_db)):
        context_values, options = resolve_context_defaults(config, db, request.query_params)
        parsed_context = build_context_from_source(config, context_values)
        master = get_master_by_context(db, config, parsed_context)
        setor_views = [build_sector_view(db, config, parsed_context, master, setor) for setor in SETOR_SEQUENCE]
        schema_ready = operational_schema_available(db)
        return templates.TemplateResponse(
            request=request,
            name="modules/index.html",
            context=_base_context(
                request,
                db,
                context_values=context_to_form_values(config, parsed_context),
                context_fields=config.context_fields,
                context_options=options,
                setor_views=setor_views,
                status_geral_label=master.status_geral if master else "NAO_INICIADO",
                status_geral_texto=STATUS_LABELS[master.status_geral] if master else STATUS_LABELS["NAO_INICIADO"],
                master=master,
                error_message=None if schema_ready else MISSING_SCHEMA_MESSAGE,
            ),
        )

    @router.post("/setores/{setor_tipo}/salvar")
    async def module_save_sector(setor_tipo: str, request: Request, db: Session = Depends(get_db)):
        if setor_tipo not in SETOR_SEQUENCE:
            raise HTTPException(status_code=404, detail="Setor inválido")
        form = await request.form()
        error_message = None
        try:
            parsed_context = build_context_from_source(config, form)
            action = "concluir" if (form.get("submit_action") or "").strip().lower() == "concluir" else "salvar"
            master = save_sector(db, config, parsed_context, setor_tipo, form, action)
        except ValueError as error:
            try:
                parsed_context = build_context_from_source(config, dict(form))
            except ValueError:
                parsed_context = build_context_from_source(config, resolve_context_defaults(config, db, form)[0])
            master = get_master_by_context(db, config, parsed_context)
            error_message = str(error)
        options = resolve_context_defaults(config, db, form)[1]
        setor_views = [build_sector_view(db, config, parsed_context, master, setor) for setor in SETOR_SEQUENCE]
        return templates.TemplateResponse(
            request=request,
            name="modules/index.html",
            context=_base_context(
                request,
                db,
                context_values=context_to_form_values(config, parsed_context),
                context_fields=config.context_fields,
                context_options=options,
                setor_views=setor_views,
                status_geral_label=master.status_geral if master else "NAO_INICIADO",
                status_geral_texto=STATUS_LABELS[master.status_geral] if master else STATUS_LABELS["NAO_INICIADO"],
                master=master,
                error_message=error_message,
            ),
            status_code=400 if error_message else 200,
        )

    @router.get("/historico")
    def module_history(request: Request, db: Session = Depends(get_db)):
        rows = build_history_rows(db, config)
        return templates.TemplateResponse(
            request=request,
            name="modules/history.html",
            context=_base_context(
                request,
                db,
                page_title=config.history_title,
                history_rows=rows,
                error_message=None if operational_schema_available(db) else MISSING_SCHEMA_MESSAGE,
            ),
        )

    @router.get("/registros/{record_id}")
    def module_detail(record_id: int, request: Request, db: Session = Depends(get_db)):
        master = get_master(db, record_id)
        if master is None or master.module_code != config.code:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        detail = build_detail_context(db, config, master)
        return templates.TemplateResponse(
            request=request,
            name="modules/detail.html",
            context=_base_context(request, db, **detail),
        )

    @router.get("/registros/{record_id}/relatorio")
    def module_report(record_id: int, request: Request, setor: str | None = None, db: Session = Depends(get_db)):
        master = get_master(db, record_id)
        if master is None or master.module_code != config.code:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        detail = build_detail_context(db, config, master, report_setor=setor)
        return templates.TemplateResponse(
            request=request,
            name="modules/report.html",
            context=_base_context(request, db, page_title=config.report_title, report_setor=setor, **detail),
        )

    @router.get("/legado/{legacy_id}")
    def module_legacy_detail(legacy_id: int, request: Request, db: Session = Depends(get_db)):
        lancamento = config.legacy_detail_loader(db, legacy_id)
        if lancamento is None:
            raise HTTPException(status_code=404, detail="Registro legado não encontrado")
        return templates.TemplateResponse(
            request=request,
            name="modules/legacy_detail.html",
            context=_base_context(request, db, legacy=lancamento),
        )

    return router

