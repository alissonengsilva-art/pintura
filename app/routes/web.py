from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.dashboard_service import (
    DashboardValidationError,
    build_dashboard_snapshot,
    build_pending_list_snapshot,
    parse_dashboard_filters,
    parse_pending_filters,
)
from app.services.navigation import SECTIONS, layout_context


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter()

SECTION_MAP = {section["slug"]: section for section in SECTIONS}


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
        "page_title": "Dashboard Operacional",
        "page_description": "Visão consolidada por período, turno e módulos do processo.",
        "filters": snapshot.filters,
        "has_global_alert": snapshot.has_global_alert,
        "global_alert_message": snapshot.global_alert_message,
        "alert_summaries": snapshot.alert_summaries,
        "metrics": snapshot.metrics,
        "pending_summary": snapshot.pending_summary,
        "module_cards": snapshot.module_cards,
        "pending_rows": snapshot.pending_rows,
        "occurrences": snapshot.occurrences,
        "error_message": error_message,
        **layout_context(str(request.url.path)),
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
        "page_title": "Pendências",
        "page_description": "Gestão de pendências operacionais por período, responsável, turno e módulo.",
        "filters": snapshot.filters,
        "status_metrics": snapshot.status_metrics,
        "rows": snapshot.rows,
        "status_options": snapshot.status_options,
        "modulo_options": snapshot.modulo_options,
        "error_message": error_message,
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="pendencias.html", context=context)


@router.get("/{section_slug}", name="section_page")
def section_page(section_slug: str, request: Request):
    section = SECTION_MAP.get(section_slug)
    if section is None:
        return RedirectResponse(url="/dashboard", status_code=302)
    context = {
        "page_title": section["title"],
        "page_description": section["description"],
        "section": section,
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="section_placeholder.html", context=context)
