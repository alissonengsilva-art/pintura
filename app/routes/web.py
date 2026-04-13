from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.dashboard_service import (
    DashboardValidationError,
    build_dashboard_snapshot,
    parse_dashboard_filters,
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
        "page_title": "Dashboard Operacional do Dia",
        "page_description": "Visão consolidada de ED e Pressão dos Filtros ED para decisão rápida por data e turno.",
        "filters": snapshot.filters,
        "has_global_alert": snapshot.has_global_alert,
        "global_alert_message": snapshot.global_alert_message,
        "alert_summaries": snapshot.alert_summaries,
        "metrics": snapshot.metrics,
        "module_cards": snapshot.module_cards,
        "pending_rows": snapshot.pending_rows,
        "occurrences": snapshot.occurrences,
        "error_message": error_message,
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)


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
