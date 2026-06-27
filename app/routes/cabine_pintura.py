from __future__ import annotations

import logging
from datetime import date
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.user import User
from app.services.auth_service import require_admin
from app.services.cabine_pintura_service import (
    CabinePinturaValidationError,
    build_relatorio_context,
    cabine_pintura_flow_schema_available,
    create_relatorio,
    delete_relatorio,
    get_relatorio,
    list_relatorios,
    save_relatorio,
)
from app.services.navigation import layout_context
from app.services.shift_service import list_shared_options as shift_list_options


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_redirect_url(raw_value: str | None, default_path: str) -> str:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return default_path
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return default_path
    path = parsed.path or default_path
    if not path.startswith("/"):
        return default_path
    return f"{path}?{parsed.query}" if parsed.query else path


@router.get("/cabine-pintura", name="cabine_pintura")
def cabine_pintura(request: Request, db: Session = Depends(get_db)):
    active_tab = request.query_params.get("tab")
    if active_tab not in {"andamento", "concluidos"}:
        active_tab = "andamento"

    relatorios = list_relatorios(db)
    options = shift_list_options(db)
    context = {
        "request": request,
        "page_title": "Cabine de Pintura",
        "page_description": "Entrada operacional da Cabine de Pintura com ciclos em andamento e concluidos.",
        "active_tab": active_tab,
        "relatorios_em_andamento": [row for row in relatorios if row["status"] != "concluido"],
        "relatorios_concluidos": [row for row in relatorios if row["status"] == "concluido"],
        "turnos": options.get("turnos", []),
        "responsaveis": options.get("responsaveis", []),
        "data_hoje": date.today().isoformat(),
        "error_message": request.query_params.get("error", ""),
        "success_message": request.query_params.get("success", ""),
        "form_data": {
            "data_referencia": request.query_params.get("data_referencia", ""),
            "turno": request.query_params.get("turno", ""),
            "responsavel": request.query_params.get("responsavel", ""),
        },
        "open_start_modal": request.query_params.get("modal") == "iniciar",
        "schema_error_message": (
            None
            if cabine_pintura_flow_schema_available(db)
            else "Estrutura do fluxo da Cabine de Pintura nao instalada. Execute as migrations."
        ),
        **layout_context(str(request.url.path), active_path="/cabine-pintura", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="cabine_pintura_index.html", context=context)


@router.post("/cabine-pintura/iniciar", name="cabine_pintura_iniciar")
async def cabine_pintura_iniciar(request: Request, db: Session = Depends(get_db)):
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
    except CabinePinturaValidationError as error:
        query = urlencode(
            {
                "modal": "iniciar",
                "error": str(error),
                "data_referencia": data_referencia,
                "turno": turno,
                "responsavel": responsavel,
            }
        )
        return RedirectResponse(url=f"/cabine-pintura?{query}", status_code=303)
    return RedirectResponse(url=f"/cabine-pintura/{relatorio.id}", status_code=303)


@router.get("/cabine-pintura/{relatorio_id}", name="cabine_pintura_execucao")
def cabine_pintura_execucao(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    relatorio = get_relatorio(db, relatorio_id)
    if relatorio is None:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    if relatorio.status == "concluido":
        return RedirectResponse(url=f"/cabine-pintura/{relatorio_id}/visualizar", status_code=303)
    context = {
        "request": request,
        "page_title": f"Cabine de Pintura {relatorio.data_controle.strftime('%d/%m/%Y')}",
        "page_description": "Execucao do checklist da Cabine de Pintura.",
        "relatorio": build_relatorio_context(db, relatorio),
        "schema_error_message": (
            None
            if cabine_pintura_flow_schema_available(db)
            else "Estrutura do fluxo da Cabine de Pintura nao instalada. Execute as migrations."
        ),
        "error_message": request.query_params.get("error", ""),
        **layout_context(str(request.url.path), active_path="/cabine-pintura", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="cabine_pintura_execution.html", context=context)


@router.post("/cabine-pintura/{relatorio_id}/salvar", name="cabine_pintura_salvar")
async def cabine_pintura_salvar(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    submit_action = str(form.get("submit_action") or "salvar").strip().lower()
    try:
        save_relatorio(db, relatorio_id, form, submit_action)
    except CabinePinturaValidationError as error:
        return RedirectResponse(
            url=f"/cabine-pintura/{relatorio_id}?{urlencode({'error': str(error)})}",
            status_code=303,
        )
    return RedirectResponse(url=f"/cabine-pintura/{relatorio_id}", status_code=303)


@router.get("/cabine-pintura/{relatorio_id}/visualizar", name="cabine_pintura_visualizar")
def cabine_pintura_visualizar(relatorio_id: int, request: Request, db: Session = Depends(get_db)):
    relatorio = get_relatorio(db, relatorio_id)
    if relatorio is None:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")
    context = {
        "request": request,
        "page_title": f"Cabine de Pintura {relatorio.data_controle.strftime('%d/%m/%Y')}",
        "page_description": "Visualizacao somente leitura da Cabine de Pintura.",
        "relatorio": build_relatorio_context(db, relatorio),
        **layout_context(str(request.url.path), active_path="/cabine-pintura", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="cabine_pintura_view.html", context=context)


@router.post("/cabine-pintura/{relatorio_id}/excluir", name="cabine_pintura_excluir")
def cabine_pintura_excluir(
    relatorio_id: int,
    redirect_to: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    relatorio = get_relatorio(db, relatorio_id)
    if relatorio is None:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")

    target_url = _safe_redirect_url(redirect_to, "/cabine-pintura")
    try:
        delete_relatorio(db, relatorio)
        logger.info("Turno excluido: id=%s modulo=%s usuario=%s", relatorio_id, "Cabine de Pintura", current_user.username)
        separator = "&" if "?" in target_url else "?"
        return RedirectResponse(
            url=f"{target_url}{separator}{urlencode({'success': 'Turno excluido com sucesso.'})}",
            status_code=303,
        )
    except CabinePinturaValidationError as error:
        separator = "&" if "?" in target_url else "?"
        return RedirectResponse(
            url=f"{target_url}{separator}{urlencode({'error': str(error)})}",
            status_code=303,
        )
    except Exception:
        logger.exception("Falha ao excluir turno: id=%s modulo=%s usuario=%s", relatorio_id, "Cabine de Pintura", current_user.username)
        separator = "&" if "?" in target_url else "?"
        return RedirectResponse(
            url=(
                f"{target_url}{separator}"
                f"{urlencode({'error': 'Nao foi possivel excluir o turno. Tente novamente ou verifique se existem dados vinculados.'})}"
            ),
            status_code=303,
        )
