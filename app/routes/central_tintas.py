from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import CENTRAL_TINTAS_STATUS_CONCLUIDO, CENTRAL_TINTAS_STATUS_EM_ANDAMENTO
from app.services.navigation import layout_context
from app.services.shift_service import list_shared_options as shift_list_options
from app.services.central_tintas_service import (
    CentralTintasValidationError,
    build_relatorio_detail,
    central_tintas_schema_available,
    create_relatorio,
    get_relatorio_by_id,
    list_relatorios_history,
    list_turno_options,
    save_relatorio,
)


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter()


def _coerce_date(raw_value: str | None, fallback: date | None = None) -> date | None:
    if raw_value:
        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            pass
    return fallback if fallback is not None else date.today()


def _render_index(
    request: Request,
    db: Session,
    *,
    error_message: str | None = None,
    form_data: dict | None = None,
    open_start_modal: bool = False,
):
    active_tab = request.query_params.get("tab")
    if active_tab not in {"andamento", "concluidos"}:
        active_tab = "andamento"

    relatorios = list_relatorios_history(db, limit=100) if central_tintas_schema_available(db) else []
    relatorios_em_andamento = [item for item in relatorios if item["status"] != CENTRAL_TINTAS_STATUS_CONCLUIDO]
    relatorios_concluidos = [item for item in relatorios if item["status"] == CENTRAL_TINTAS_STATUS_CONCLUIDO]

    context = {
        "request": request,
        "page_title": "Central de Tintas",
        "page_description": "Entrada principal para iniciar e acompanhar os relatorios da Central de Tintas.",
        "active_tab": active_tab,
        "relatorios_em_andamento": relatorios_em_andamento,
        "relatorios_concluidos": relatorios_concluidos,
        "turnos": list_turno_options(db),
        "responsaveis": shift_list_options(db).get("responsaveis", []),
        "data_hoje": date.today().isoformat(),
        "error_message": error_message,
        "form_data": form_data or {},
        "open_start_modal": open_start_modal or request.query_params.get("modal") == "iniciar",
        "schema_error_message": None if central_tintas_schema_available(db) else "Estrutura da Central de Tintas nao instalada. Execute as migrations.",
        **layout_context(str(request.url.path), active_path="/central-tintas", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="central_tintas_index.html", context=context)


def _render_execution(
    request: Request,
    db: Session,
    relatorio_id: int,
    *,
    error_message: str | None = None,
    status_code: int = 200,
):
    relatorio_obj = get_relatorio_by_id(db, relatorio_id)
    if not relatorio_obj:
        raise HTTPException(status_code=404, detail="Relatorio da central de tintas nao encontrado")
    relatorio = build_relatorio_detail(db, relatorio_obj)

    if relatorio_obj.status == CENTRAL_TINTAS_STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/central-tintas/registros/{relatorio_id}/visualizar", status_code=303)

    context = {
        "request": request,
        "page_title": f"Central de Tintas {relatorio['data_label']}",
        "page_description": "Checklist principal da Central de Tintas.",
        "relatorio": relatorio,
        "error_message": error_message,
        "schema_error_message": None if central_tintas_schema_available(db) else "Estrutura da Central de Tintas nao instalada.",
        **layout_context(str(request.url.path), active_path="/central-tintas", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="central_tintas_execution.html", context=context, status_code=status_code)


def _render_visualizacao(request: Request, db: Session, relatorio_id: int):
    relatorio_obj = get_relatorio_by_id(db, relatorio_id)
    if not relatorio_obj:
        raise HTTPException(status_code=404, detail="Relatorio da central de tintas nao encontrado")
    relatorio = build_relatorio_detail(db, relatorio_obj)

    context = {
        "request": request,
        "page_title": f"Visualizacao Central de Tintas {relatorio['data_label']}",
        "page_description": "Relatorio final da Central de Tintas.",
        "relatorio": relatorio,
        "schema_error_message": None if central_tintas_schema_available(db) else "Estrutura da Central de Tintas nao instalada.",
        **layout_context(str(request.url.path), active_path="/central-tintas", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="central_tintas_view.html", context=context)


@router.get("/central-tintas", name="central_tintas")
def central_tintas(request: Request, db: Session = Depends(get_db)):
    return _render_index(request, db)


@router.get("/central-tintas/iniciar", name="central_tintas_iniciar_form")
def central_tintas_iniciar_form():
    return RedirectResponse(url="/central-tintas?modal=iniciar", status_code=302)


@router.post("/central-tintas/iniciar", name="central_tintas_iniciar_post")
def central_tintas_iniciar_post(
    request: Request,
    db: Session = Depends(get_db),
    data_controle: str = Form(...),
    turno: str = Form(...),
    responsavel: str = Form(None),
):
    data_ref = _coerce_date(data_controle)
    try:
        relatorio = create_relatorio(db, data_ref, str(turno).strip(), (responsavel or "").strip())
        return RedirectResponse(url=f"/central-tintas/registros/{relatorio.id}", status_code=303)
    except CentralTintasValidationError as error:
        return _render_index(
            request,
            db,
            error_message=str(error),
            form_data={"data_controle": data_controle, "turno": turno, "responsavel": responsavel},
            open_start_modal=True,
        )


@router.get("/central-tintas/{relatorio_id}", name="central_tintas_execucao_legacy")
def central_tintas_execucao_legacy(relatorio_id: int):
    return RedirectResponse(url=f"/central-tintas/registros/{relatorio_id}", status_code=302)


@router.get("/central-tintas/registros/{relatorio_id}", name="central_tintas_execucao")
def central_tintas_execucao(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    return _render_execution(request, db, relatorio_id)


@router.get("/central-tintas/registros/{relatorio_id}/visualizar", name="central_tintas_visualizar")
def central_tintas_visualizar(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    return _render_visualizacao(request, db, relatorio_id)


@router.post("/central-tintas/{relatorio_id}/salvar", name="central_tintas_salvar")
async def central_tintas_salvar(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    relatorio_obj = get_relatorio_by_id(db, relatorio_id)
    if not relatorio_obj:
        raise HTTPException(status_code=404, detail="Relatorio da central de tintas nao encontrado")
    if relatorio_obj.status == CENTRAL_TINTAS_STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/central-tintas/registros/{relatorio_id}/visualizar", status_code=303)

    form = await request.form()
    submit_action = "concluir" if (form.get("submit_action") or "").strip().lower() == "concluir" else "salvar"
    try:
        save_relatorio(db, relatorio_obj, dict(form), action=submit_action)
        if submit_action == "concluir":
            return RedirectResponse(url=f"/central-tintas/registros/{relatorio_id}/visualizar", status_code=303)
        return RedirectResponse(url=f"/central-tintas/registros/{relatorio_id}", status_code=303)
    except CentralTintasValidationError as error:
        return _render_execution(request, db, relatorio_id, error_message=str(error), status_code=400)


@router.post("/central-tintas/{relatorio_id}/concluir", name="central_tintas_concluir")
def central_tintas_concluir(relatorio_id: int, db: Session = Depends(get_db)):
    relatorio_obj = get_relatorio_by_id(db, relatorio_id)
    if not relatorio_obj:
        raise HTTPException(status_code=404, detail="Relatorio da central de tintas nao encontrado")
    if relatorio_obj.status == CENTRAL_TINTAS_STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/central-tintas/registros/{relatorio_id}/visualizar", status_code=303)
    try:
        save_relatorio(db, relatorio_obj, {}, action="concluir")
    except CentralTintasValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return RedirectResponse(url="/central-tintas?tab=concluidos", status_code=303)
