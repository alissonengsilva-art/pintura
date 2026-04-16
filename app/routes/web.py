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
from app.services.navigation import layout_context


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter()


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
        "page_description": "Visão consolidada do novo modelo setorial PTED/Laboratório.",
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
        "page_title": "Pendências",
        "page_description": "Pendências operacionais do novo modelo consolidado.",
        "filters": snapshot.filters,
        "status_metrics": snapshot.status_metrics,
        "rows": snapshot.rows,
        "error_message": error_message,
        **layout_context(str(request.url.path), scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="pendencias.html", context=context)

