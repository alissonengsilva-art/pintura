from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.central_tintas_service import (
    CentralTintasValidationError,
    build_relatorio_context,
    create_relatorio,
    get_relatorio,
    list_relatorios,
    save_relatorio,
    central_tintas_flow_schema_available,
)
from app.services.navigation import layout_context
from app.services.shift_service import list_shared_options as shift_list_options


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter()


@router.get("/central-tintas", name="central_tintas")
def central_tintas(request: Request, db: Session = Depends(get_db)):
    active_tab = request.query_params.get("tab")
    if active_tab not in {"andamento", "concluidos"}:
        active_tab = "andamento"

    relatorios = list_relatorios(db)
    options = shift_list_options(db)
    context = {
        "request": request,
        "page_title": "Central de Tintas",
        "page_description": "Entrada operacional da Central de Tintas com ciclos em andamento e concluidos.",
        "active_tab": active_tab,
        "relatorios_em_andamento": [row for row in relatorios if row["status"] != "concluido"],
        "relatorios_concluidos": [row for row in relatorios if row["status"] == "concluido"],
        "turnos": options.get("turnos", []),
        "responsaveis": options.get("responsaveis", []),
        "data_hoje": date.today().isoformat(),
        "error_message": request.query_params.get("error", ""),
        "form_data": {
            "data_referencia": request.query_params.get("data_referencia", ""),
            "turno": request.query_params.get("turno", ""),
            "responsavel": request.query_params.get("responsavel", ""),
        },
        "open_start_modal": request.query_params.get("modal") == "iniciar",
        "schema_error_message": (
            None
            if central_tintas_flow_schema_available(db)
            else "Estrutura do fluxo da Central de Tintas nao instalada. Execute as migrations."
        ),
        **layout_context(str(request.url.path), active_path="/central-tintas", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="central_tintas_index.html", context=context)


@router.post("/central-tintas/iniciar", name="central_tintas_iniciar")
async def central_tintas_iniciar(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    data_referencia = str(form.get("data_referencia") or "").strip()
    turno = str(form.get("turno") or "").strip()
    responsavel = str(form.get("responsavel") or "").strip()
    try:
        relatorio = create_relatorio(
            db,
            {
                "data_referencia": data_referencia,
                "turno": turno,
                "responsavel": responsavel,
            },
        )
    except CentralTintasValidationError as error:
        query = urlencode(
            {
                "modal": "iniciar",
                "error": str(error),
                "data_referencia": data_referencia,
                "turno": turno,
                "responsavel": responsavel,
            }
        )
        return RedirectResponse(url=f"/central-tintas?{query}", status_code=303)
    return RedirectResponse(url=f"/central-tintas/{relatorio.id}", status_code=303)


@router.get("/central-tintas/{relatorio_id}", name="central_tintas_execucao")
def central_tintas_execucao(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    relatorio = get_relatorio(db, relatorio_id)
    if relatorio is None:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    if relatorio.status == "concluido":
        return RedirectResponse(url=f"/central-tintas/{relatorio_id}/visualizar", status_code=303)
    context = {
        "request": request,
        "page_title": f"Central de Tintas {relatorio.data_controle.strftime('%d/%m/%Y')}",
        "page_description": "Execucao do checklist da Central de Tintas.",
        "relatorio": build_relatorio_context(db, relatorio),
        "schema_error_message": (
            None
            if central_tintas_flow_schema_available(db)
            else "Estrutura do fluxo da Central de Tintas nao instalada. Execute as migrations."
        ),
        "error_message": request.query_params.get("error", ""),
        **layout_context(str(request.url.path), active_path="/central-tintas", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="central_tintas_execution.html", context=context)


@router.post("/central-tintas/{relatorio_id}/salvar", name="central_tintas_salvar")
async def central_tintas_salvar(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    submit_action = str(form.get("submit_action") or "salvar").strip().lower()
    try:
        save_relatorio(db, relatorio_id, form, submit_action)
    except CentralTintasValidationError as error:
        return RedirectResponse(
            url=f"/central-tintas/{relatorio_id}?{urlencode({'error': str(error)})}",
            status_code=303,
        )
    return RedirectResponse(url=f"/central-tintas/{relatorio_id}", status_code=303)


@router.get("/central-tintas/{relatorio_id}/visualizar", name="central_tintas_visualizar")
def central_tintas_visualizar(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    relatorio = get_relatorio(db, relatorio_id)
    if relatorio is None:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    context = {
        "request": request,
        "page_title": f"Central de Tintas {relatorio.data_controle.strftime('%d/%m/%Y')}",
        "page_description": "Visualizacao somente leitura da Central de Tintas.",
        "relatorio": build_relatorio_context(db, relatorio),
        **layout_context(str(request.url.path), active_path="/central-tintas", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="central_tintas_view.html", context=context)
