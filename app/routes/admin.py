from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import OperationalModuleItem
from app.services import operational_module_item_admin_service, operational_module_item_service
from app.services.auth_service import require_admin
from app.services.navigation import SETTINGS_HUB_ITEMS, layout_context
from app.services.operational_module_service import MODULE_CONFIGS
from app.services.reference_service import (
    create_record,
    delete_record,
    field_labels,
    get_entity_config,
    get_record,
    list_records,
    payload_from_form,
    update_record,
)


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["cadastros"])


def _format_temperature_parameter(valor_min: float | None, valor_max: float | None) -> str | None:
    if valor_min is not None and valor_max is not None:
        return f"{valor_min:g} a {valor_max:g} C"
    if valor_min is not None:
        return f">= {valor_min:g} C"
    if valor_max is not None:
        return f"<= {valor_max:g} C"
    return None


def _admin_list_context(
    request: Request,
    entity: str,
    db: Session,
    *,
    form_record=None,
    form_error_message: str | None = None,
):
    config = get_entity_config(entity)
    active_filters = {}
    available_setores = []
    if entity == "modulos-itens":
        active_filters["module_code"] = request.query_params.get("module_code", "")
    if entity == "responsaveis":
        available_setores = list_records(db, "setores")

    records = list_records(db, entity, active_filters)
    return {
        "page_title": config.title,
        "page_description": f"Gerencie os registros de {config.title.lower()}.",
        "entity": entity,
        "entity_config": config,
        "records": records,
        "column_labels": field_labels(config.list_fields, config),
        "active_filters": active_filters,
        "inline_form_record": form_record,
        "inline_form_error_message": form_error_message,
        "available_setores": available_setores,
        "open_responsavel_modal": bool(form_error_message),
        **layout_context(str(request.url.path), active_path="/configuracoes"),
    }


def _build_frequency_table_context(db: Session, module_code: str) -> dict:
    if module_code not in MODULE_CONFIGS:
        raise HTTPException(status_code=404, detail="Modulo invalido")
    return {
        "module_code": module_code,
        "module_title": MODULE_CONFIGS[module_code].title,
        "items": operational_module_item_service.get_itens_por_modulo(db, module_code),
        "frequency_options": operational_module_item_service.FREQUENCY_OPTIONS,
        "weekday_options": operational_module_item_service.WEEKDAY_OPTIONS,
    }


def _build_module_admin_context(db: Session, module_code: str) -> dict:
    try:
        module_context = operational_module_item_admin_service.build_module_context(db, module_code)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {
        "module_code": module_context.module_code,
        "module_title": module_context.module_title,
        "rows": module_context.rows,
        "sector_options": operational_module_item_admin_service.SECTOR_OPTIONS,
        "frequency_options": operational_module_item_service.FREQUENCY_OPTIONS,
        "weekday_options": operational_module_item_service.WEEKDAY_OPTIONS,
    }


@router.get("/configuracoes", name="configuracoes_home")
def configuracoes_home(request: Request, _admin=Depends(require_admin)):
    context = {
        "page_title": "Configurações",
        "page_description": "Central administrativa para ajustes estruturais do sistema.",
        "settings_items": SETTINGS_HUB_ITEMS,
        **layout_context(str(request.url.path), active_path="/configuracoes"),
    }
    return templates.TemplateResponse(request=request, name="admin/index.html", context=context)


@router.get("/configuracoes/frequencias", name="configuracoes_frequencias")
def configuracoes_frequencias(request: Request, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    selected_module = request.query_params.get("modulo", "")
    query = f"?modulo={quote_plus(selected_module)}" if selected_module else ""
    return RedirectResponse(url=f"/configuracoes/modulos-itens{query}", status_code=302)


@router.get("/configuracoes/frequencias/{modulo_id}", name="configuracoes_frequencias_modulo", response_class=HTMLResponse)
def configuracoes_frequencias_modulo(
    modulo_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return RedirectResponse(url=f"/configuracoes/modulos-itens/{quote_plus(modulo_id)}", status_code=302)


@router.post("/configuracoes/frequencias/{item_id}", name="configuracoes_frequencias_salvar")
async def configuracoes_frequencias_salvar(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    payload = await request.json()
    try:
        operational_module_item_service.atualizar_frequencia_item(db, item_id, payload)
    except ValueError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)
    return JSONResponse({"success": True})


@router.get("/configuracoes/modulos-itens", name="configuracoes_modulos_itens")
def configuracoes_modulos_itens(request: Request, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    modules = operational_module_item_admin_service.list_modules()
    selected_module = request.query_params.get("modulo", "").strip()
    if not selected_module:
        selected_module = modules[0]["code"] if modules else next(iter(MODULE_CONFIGS.keys()))

    context = {
        "page_title": "Itens dos Modulos",
        "page_description": "Cadastre, edite e organize os itens e sua periodicidade operacional.",
        "modules": modules,
        "selected_module": selected_module,
        **_build_module_admin_context(db, selected_module),
        **layout_context(str(request.url.path), active_path="/configuracoes"),
    }
    return templates.TemplateResponse(request=request, name="admin/module_items_admin.html", context=context)


@router.get("/configuracoes/modulos-itens/{modulo_id}", name="configuracoes_modulos_itens_modulo", response_class=HTMLResponse)
def configuracoes_modulos_itens_modulo(
    modulo_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    context = {
        "request": request,
        **_build_module_admin_context(db, modulo_id),
    }
    return templates.TemplateResponse(request=request, name="admin/_module_items_table.html", context=context)


@router.post("/configuracoes/modulos-itens/{modulo_id}/batch", name="configuracoes_modulos_itens_batch")
async def configuracoes_modulos_itens_batch(
    modulo_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    try:
        result = operational_module_item_admin_service.save_module_batch(module_code=modulo_id, session=db, payload=await request.json())
    except ValueError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)
    return JSONResponse({"success": True, **result})


@router.get("/cadastros/modulos-itens", name="admin_modulos_itens_redirect")
def admin_modulos_itens_redirect(request: Request, _admin=Depends(require_admin)):
    selected_module = request.query_params.get("module_code", "").strip()
    query = f"?modulo={quote_plus(selected_module)}" if selected_module else ""
    return RedirectResponse(url=f"/configuracoes/modulos-itens{query}", status_code=302)


@router.get("/cadastros/modulos-itens/novo", name="admin_modulos_itens_new_redirect")
def admin_modulos_itens_new_redirect(_admin=Depends(require_admin)):
    return RedirectResponse(url="/configuracoes/modulos-itens", status_code=302)


@router.get("/cadastros", name="cadastros_home")
def cadastros_home(_admin=Depends(require_admin)):
    return RedirectResponse(url="/configuracoes", status_code=302)


@router.get("/cadastros/modulos-itens/temperatura-forno-ed/faixas", name="admin_temperatura_faixas")
def admin_temperatura_faixas(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = None,
    _admin=Depends(require_admin),
):
    items = list(
        db.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "temperatura-forno-ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )
    context = {
        "page_title": "Faixas - Temperatura Forno ED",
        "page_description": "Edicao em lote das faixas minimas e maximas das zonas termicas.",
        "items": items,
        "error_message": None,
        "success_message": "Faixas atualizadas com sucesso." if status == "saved" else None,
        **layout_context(str(request.url.path), active_path="/configuracoes"),
    }
    return templates.TemplateResponse(request=request, name="admin/temperature_ranges.html", context=context)


@router.post("/cadastros/modulos-itens/temperatura-forno-ed/faixas", name="admin_temperatura_faixas_salvar")
async def admin_temperatura_faixas_salvar(
    request: Request,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    form = await request.form()
    items = list(
        db.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == "temperatura-forno-ed")
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )

    invalid_ranges = []
    for item in items:
        valor_min_raw = str(form.get(f"valor_min_{item.id}") or "").strip()
        valor_max_raw = str(form.get(f"valor_max_{item.id}") or "").strip()
        valor_min = float(valor_min_raw.replace(",", ".")) if valor_min_raw else None
        valor_max = float(valor_max_raw.replace(",", ".")) if valor_max_raw else None

        item.valor_min = valor_min
        item.valor_max = valor_max
        item.parametro = _format_temperature_parameter(valor_min, valor_max)
        item.range_error = bool(valor_min is not None and valor_max is not None and valor_min > valor_max)
        if item.range_error:
            invalid_ranges.append(item)

    if invalid_ranges:
        db.rollback()
        context = {
            "page_title": "Faixas - Temperatura Forno ED",
            "page_description": "Edicao em lote das faixas minimas e maximas das zonas termicas.",
            "items": items,
            "error_message": "Existem faixas invalidas. O valor minimo nao pode ser maior que o valor maximo.",
            "success_message": None,
            **layout_context(str(request.url.path), active_path="/configuracoes"),
        }
        return templates.TemplateResponse(
            request=request,
            name="admin/temperature_ranges.html",
            context=context,
            status_code=400,
        )

    db.commit()
    return RedirectResponse(url="/cadastros/modulos-itens/temperatura-forno-ed/faixas?status=saved", status_code=303)


@router.get("/cadastros/{entity}", name="admin_list")
def admin_list(entity: str, request: Request, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    try:
        get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    context = _admin_list_context(request, entity, db)
    return templates.TemplateResponse(request=request, name="admin/list.html", context=context)


@router.get("/cadastros/{entity}/novo", name="admin_create_form")
def admin_create_form(entity: str, request: Request, _admin=Depends(require_admin)):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    if entity == "modulos-itens":
        return RedirectResponse(url="/configuracoes/modulos-itens", status_code=302)

    if entity == "responsaveis":
        return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)

    context = {
        "page_title": f"Novo registro - {config.title}",
        "page_description": f"Crie um novo registro para {config.title.lower()}.",
        "entity": entity,
        "entity_config": config,
        "record": None,
        "error_message": None,
        "available_setores": [],
        **layout_context(str(request.url.path), active_path="/configuracoes"),
    }
    return templates.TemplateResponse(request=request, name="admin/form.html", context=context)


@router.post("/cadastros/{entity}/novo", name="admin_create")
async def admin_create(
    entity: str,
    request: Request,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    form = await request.form()
    payload = payload_from_form(config, form)
    try:
        create_record(db, entity, payload)
    except IntegrityError:
        db.rollback()
        if entity == "responsaveis":
            context = _admin_list_context(
                request,
                entity,
                db,
                form_record=payload,
                form_error_message="Nao foi possivel salvar. Verifique duplicidade ou campos obrigatorios.",
            )
            return templates.TemplateResponse(request=request, name="admin/list.html", context=context, status_code=400)

        context = {
            "page_title": f"Novo registro - {config.title}",
            "page_description": f"Crie um novo registro para {config.title.lower()}.",
            "entity": entity,
            "entity_config": config,
            "record": payload,
            "error_message": "Nao foi possivel salvar. Verifique duplicidade ou campos obrigatorios.",
            "available_setores": [],
            **layout_context(str(request.url.path), active_path="/configuracoes"),
        }
        return templates.TemplateResponse(request=request, name="admin/form.html", context=context, status_code=400)

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)


@router.get("/cadastros/{entity}/{record_id}/editar", name="admin_edit_form")
def admin_edit_form(
    entity: str,
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    if entity == "modulos-itens":
        return RedirectResponse(url="/configuracoes/modulos-itens", status_code=302)

    record = get_record(db, entity, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Registro nao encontrado")

    context = {
        "page_title": f"Editar registro - {config.title}",
        "page_description": f"Atualize os dados do cadastro de {config.title.lower()}.",
        "entity": entity,
        "entity_config": config,
        "record": record,
        "error_message": None,
        "available_setores": list_records(db, "setores") if entity == "responsaveis" else [],
        **layout_context(str(request.url.path), active_path="/configuracoes"),
    }
    return templates.TemplateResponse(request=request, name="admin/form.html", context=context)


@router.post("/cadastros/{entity}/{record_id}/editar", name="admin_edit")
async def admin_edit(
    entity: str,
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    record = get_record(db, entity, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Registro nao encontrado")

    form = await request.form()
    payload = payload_from_form(config, form)
    try:
        update_record(db, entity, record_id, payload)
    except IntegrityError:
        db.rollback()
        merged_record = {field.name: payload.get(field.name) for field in config.fields}
        context = {
            "page_title": f"Editar registro - {config.title}",
            "page_description": f"Atualize os dados do cadastro de {config.title.lower()}.",
            "entity": entity,
            "entity_config": config,
            "record": merged_record,
            "error_message": "Nao foi possivel atualizar. Verifique duplicidade ou campos obrigatorios.",
            "available_setores": list_records(db, "setores") if entity == "responsaveis" else [],
            **layout_context(str(request.url.path), active_path="/configuracoes"),
        }
        return templates.TemplateResponse(request=request, name="admin/form.html", context=context, status_code=400)

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)


@router.post("/cadastros/{entity}/{record_id}/excluir", name="admin_delete")
def admin_delete(entity: str, record_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    try:
        get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    deleted = delete_record(db, entity, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro nao encontrado")

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)
