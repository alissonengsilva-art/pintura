from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.navigation import layout_context
from app.services.shift_service import list_shared_options as shift_list_options
from app.services.sigilatura_service import (
    MODULE_META,
    SigilaturaValidationError,
    add_escorrimento_image,
    build_module_editor_state,
    build_turno_detail,
    conclude_turno,
    create_turno,
    get_turno_by_id,
    list_turno_options,
    list_turnos_history,
    remove_escorrimento_image,
    save_module,
    sigilatura_schema_available,
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


def _shift_exec_url(shift_id: int, module_code: str | None = None) -> str:
    if not module_code:
        return f"/turnos-sigilatura/{shift_id}"
    return f"/turnos-sigilatura/{shift_id}?modulo={module_code}"


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

    shifts = list_turnos_history(db, limit=100) if sigilatura_schema_available(db) else []
    shifts_em_andamento = [shift for shift in shifts if shift["status_geral"] != "CONCLUIDO"]
    shifts_concluidos = [shift for shift in shifts if shift["status_geral"] == "CONCLUIDO"]

    context = {
        "request": request,
        "page_title": "Turnos Sigilatura",
        "page_description": "Entrada principal para iniciar e acompanhar os controles de Sigilatura em andamento ou concluÃ­dos.",
        "active_tab": active_tab,
        "shifts_em_andamento": shifts_em_andamento,
        "shifts_concluidos": shifts_concluidos,
        "turnos": list_turno_options(db),
        "responsaveis": shift_list_options(db).get("responsaveis", []),
        "data_hoje": date.today().isoformat(),
        "error_message": error_message,
        "form_data": form_data or {},
        "open_start_modal": open_start_modal or request.query_params.get("modal") == "iniciar",
        "schema_error_message": None if sigilatura_schema_available(db) else "Estrutura de Sigilatura nÃ£o instalada. Execute as migrations.",
        **layout_context(str(request.url.path), active_path="/turnos-sigilatura", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="turnos_sigilatura_index.html", context=context)


def _render_execution(
    request: Request,
    db: Session,
    shift_id: int,
    module_code: str | None,
    *,
    error_message: str | None = None,
    status_code: int = 200,
):
    shift_obj = get_turno_by_id(db, shift_id)
    if not shift_obj:
        raise HTTPException(status_code=404, detail="Turno de sigilatura nÃ£o encontrado")
    shift = build_turno_detail(db, shift_obj)
    modules = shift["modules"]
    available = [m["code"] for m in modules]
    active_module_code = module_code if module_code in available else (available[0] if available else "sigilatura")
    module_state = build_module_editor_state(db, shift_obj, active_module_code)

    context = {
        "request": request,
        "page_title": f"Execução Sigilatura {shift['data_label']}",
        "page_description": "Execução principal do turno de Sigilatura.",
        "shift": shift,
        "active_module_code": active_module_code,
        "module_state": module_state,
        "module_meta": MODULE_META,
        "error_message": error_message,
        "schema_error_message": None if sigilatura_schema_available(db) else "Estrutura de Sigilatura nÃ£o instalada.",
        **layout_context(str(request.url.path), active_path="/turnos-sigilatura", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="turnos_sigilatura_execution.html", context=context, status_code=status_code)


@router.get("/turnos-sigilatura", name="turnos_sigilatura")
def turnos_sigilatura(request: Request, db: Session = Depends(get_db)):
    return _render_index(request, db)


@router.get("/turnos-sigilatura/iniciar", name="turnos_sigilatura_iniciar_form")
def turnos_sigilatura_iniciar_form():
    return RedirectResponse(url="/turnos-sigilatura?modal=iniciar", status_code=302)


@router.post("/turnos-sigilatura/iniciar", name="turnos_sigilatura_iniciar_post")
def turnos_sigilatura_iniciar_post(
    request: Request,
    db: Session = Depends(get_db),
    data_referencia: str = Form(...),
    turno: str = Form(...),
    responsavel: str = Form(None),
):
    data_ref = _coerce_date(data_referencia)
    try:
        shift = create_turno(db, data_ref, str(turno).strip(), responsavel=(responsavel or "").strip() or None)
        return RedirectResponse(url=_shift_exec_url(shift.id), status_code=303)
    except SigilaturaValidationError as error:
        return _render_index(
            request,
            db,
            error_message=str(error),
            form_data={"data_referencia": data_referencia, "turno": turno, "responsavel": responsavel},
            open_start_modal=True,
        )


@router.get("/turnos-sigilatura/{shift_id}", name="turnos_sigilatura_execucao")
def turnos_sigilatura_execucao(
    shift_id: int,
    request: Request,
    modulo: str | None = None,
    db: Session = Depends(get_db),
):
    shift_obj = get_turno_by_id(db, shift_id)
    if not shift_obj:
        raise HTTPException(status_code=404, detail="Turno de sigilatura nÃ£o encontrado")
    if shift_obj.status_geral == "CONCLUIDO":
        return RedirectResponse(url=f"/turnos-sigilatura/{shift_id}/visualizar", status_code=303)
    return _render_execution(request, db, shift_id, modulo)


@router.get("/turnos-sigilatura/{shift_id}/visualizar", name="turnos_sigilatura_visualizacao")
def turnos_sigilatura_visualizacao(
    shift_id: int,
    request: Request,
    modulo: str | None = None,
    db: Session = Depends(get_db),
):
    shift_obj = get_turno_by_id(db, shift_id)
    if not shift_obj:
        raise HTTPException(status_code=404, detail="Turno de sigilatura nÃ£o encontrado")
    shift = build_turno_detail(db, shift_obj)
    modules = shift["modules"]
    available = [m["code"] for m in modules]
    active_module_code = modulo if modulo in available else (available[0] if available else "sigilatura")
    module_state = build_module_editor_state(db, shift_obj, active_module_code)
    context = {
        "request": request,
        "page_title": f"VisualizaÃ§Ã£o Sigilatura {shift['data_label']}",
        "page_description": "VisualizaÃ§Ã£o somente leitura do turno de Sigilatura concluÃ­do.",
        "shift": shift,
        "active_module_code": active_module_code,
        "module_state": module_state,
        "module_meta": MODULE_META,
        "schema_error_message": None if sigilatura_schema_available(db) else "Estrutura de Sigilatura nÃ£o instalada.",
        **layout_context(str(request.url.path), active_path="/turnos-sigilatura", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="turnos_sigilatura_view.html", context=context)


@router.post("/turnos-sigilatura/{shift_id}/modulos/{module_code}/salvar", name="turnos_sigilatura_salvar_modulo")
async def turnos_sigilatura_salvar_modulo(
    shift_id: int,
    module_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shift_obj = get_turno_by_id(db, shift_id)
    if not shift_obj:
        raise HTTPException(status_code=404, detail="Turno de sigilatura não encontrado")
    if shift_obj.status_geral == "CONCLUIDO":
        return RedirectResponse(url=f"/turnos-sigilatura/{shift_id}/visualizar", status_code=303)
    form = await request.form()
    submit_action = "concluir" if (form.get("submit_action") or "").strip().lower() == "concluir" else "salvar"
    try:
        save_module(db, shift_obj, module_code, dict(form), action=submit_action)
        return RedirectResponse(url=_shift_exec_url(shift_id, module_code), status_code=303)
    except SigilaturaValidationError as error:
        return _render_execution(request, db, shift_id, module_code, error_message=str(error), status_code=400)


@router.post("/turnos-sigilatura/{shift_id}/modulos/escorrimento/imagens", name="turnos_sigilatura_upload_escorrimento_imagem")
async def turnos_sigilatura_upload_escorrimento_imagem(
    shift_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    shift_obj = get_turno_by_id(db, shift_id)
    if not shift_obj:
        raise HTTPException(status_code=404, detail="Turno de sigilatura nao encontrado")

    raw = await image.read()
    try:
        created = add_escorrimento_image(
            db,
            shift_obj,
            file_bytes=raw,
            content_type=image.content_type or "",
        )
    except SigilaturaValidationError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)

    module_state = build_module_editor_state(db, shift_obj, "escorrimento")
    return JSONResponse(
        {
            "success": True,
            "image": created,
            "images": module_state.get("escorrimento_images", []),
            "max_images": module_state.get("escorrimento_max_images", 2),
        }
    )


@router.post("/turnos-sigilatura/{shift_id}/modulos/escorrimento/imagens/{image_id}/remover", name="turnos_sigilatura_remover_escorrimento_imagem")
def turnos_sigilatura_remover_escorrimento_imagem(
    shift_id: int,
    image_id: int,
    db: Session = Depends(get_db),
):
    shift_obj = get_turno_by_id(db, shift_id)
    if not shift_obj:
        raise HTTPException(status_code=404, detail="Turno de sigilatura nao encontrado")
    try:
        remove_escorrimento_image(db, shift_obj, image_id)
    except SigilaturaValidationError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)

    module_state = build_module_editor_state(db, shift_obj, "escorrimento")
    return JSONResponse(
        {
            "success": True,
            "images": module_state.get("escorrimento_images", []),
            "max_images": module_state.get("escorrimento_max_images", 2),
        }
    )


@router.post("/turnos-sigilatura/{shift_id}/concluir", name="turnos_sigilatura_concluir")
def turnos_sigilatura_concluir(shift_id: int, request: Request, db: Session = Depends(get_db)):
    shift_obj = get_turno_by_id(db, shift_id)
    if not shift_obj:
        raise HTTPException(status_code=404, detail="Turno de sigilatura nÃ£o encontrado")
    try:
        conclude_turno(db, shift_obj)
        return RedirectResponse(url="/turnos-sigilatura?tab=concluidos", status_code=303)
    except SigilaturaValidationError as error:
        active_module = request.query_params.get("modulo")
        return _render_execution(request, db, shift_id, active_module, error_message=str(error), status_code=400)


