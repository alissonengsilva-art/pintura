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
from app.services import operational_module_item_admin_service, operational_module_item_service, sigilatura_service
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

RETIFICADOR_GROUP_OPTIONS = [
    {"value": "grupo_1", "label": "Grupo 1"},
    {"value": "grupo_2", "label": "Grupo 2"},
    {"value": "grupo_3", "label": "Grupo 3"},
]

MODULE_AREA_GROUPS: dict[str, list[str]] = {
    "pt": ["pt", "pressao-filtros-pt"],
    "ed": [
        "ed",
        "temperatura-forno-ed",
        "pressao-filtros-ed",
        "tensao-retificadores-ed",
        "poder-penetracao",
        "espessura-ed",
        "aspecto",
        "rugosidade",
    ],
    "sigilatura": ["sigilatura", "espessura-pvc", "temperatura-forno-sigilatura", "escorrimento"],
    "central-tintas": ["central-tintas"],
    "cabine-pintura": ["cabine-pintura"],
}


GENERAL_SCOPE_ED = "ed"
GENERAL_SCOPE_SIG = "sigilatura"

GENERAL_ED_TABS = [
    {"code": "pt", "title": "PT", "field_label": "Parametro", "editable": True},
    {"code": "ed", "title": "ED", "field_label": "Parmetro", "editable": True},
    {"code": "temperatura-forno-ed", "title": "Temperatura Forno", "field_label": "Faixa", "editable": True},
    {"code": "pressao-filtros-ed", "title": "Presso dos Filtros", "field_label": "Limite", "editable": True},
    {"code": "tensao-retificadores-ed", "title": "Tenso dos Retificadores", "field_label": "Faixa", "editable": True},
    {"code": "poder-penetracao", "title": "Poder de Penetrao", "field_label": "Referncia", "editable": True},
    {"code": "espessura-ed", "title": "Espessura", "field_label": "Faixa", "editable": True},
    {"code": "aspecto", "title": "Aspecto", "field_label": "", "editable": False},
    {"code": "rugosidade", "title": "Rugosidade", "field_label": "Limite", "editable": True},
]

GENERAL_SIG_TABS = [
    {"code": "sigilatura", "title": "Sigilatura", "field_label": "Parmetro", "editable": True},
    {"code": "espessura-pvc", "title": "Espessura PVC", "field_label": "Valor referncia", "editable": True},
    {"code": "temperatura-forno-sigilatura", "title": "Temperatura Forno", "field_label": "Referncia", "editable": True},
    {"code": "escorrimento", "title": "Escorrimento", "field_label": "", "editable": False},
]


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
        "available_abas": module_context.available_abas,
        "selected_aba": module_context.selected_aba,
        "sector_options": operational_module_item_admin_service.SECTOR_OPTIONS,
        "validation_type_options": operational_module_item_admin_service.VALIDATION_TYPE_OPTIONS,
        "frequency_options": operational_module_item_service.FREQUENCY_OPTIONS,
        "priority_options": operational_module_item_service.PRIORITY_OPTIONS,
        "weekday_options": operational_module_item_service.WEEKDAY_OPTIONS,
    }


def _build_module_admin_context_with_query(
    request: Request,
    db: Session,
    module_code: str,
    *,
    selected_aba: str | None = None,
) -> dict:
    aba = selected_aba
    if aba is None:
        aba = request.query_params.get("aba", "").strip() or None
    try:
        module_context = operational_module_item_admin_service.build_module_context(db, module_code, aba=aba)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {
        "module_code": module_context.module_code,
        "module_title": module_context.module_title,
        "rows": module_context.rows,
        "available_abas": module_context.available_abas,
        "selected_aba": module_context.selected_aba,
        "sector_options": operational_module_item_admin_service.SECTOR_OPTIONS,
        "validation_type_options": operational_module_item_admin_service.VALIDATION_TYPE_OPTIONS,
        "frequency_options": operational_module_item_service.FREQUENCY_OPTIONS,
        "priority_options": operational_module_item_service.PRIORITY_OPTIONS,
        "weekday_options": operational_module_item_service.WEEKDAY_OPTIONS,
    }


def _resolve_module_area(module_code: str) -> str:
    for area, codes in MODULE_AREA_GROUPS.items():
        if module_code in codes:
            return area
    return "ed"


def _module_tabs_for_scope(scope: str) -> list[dict[str, object]]:
    if scope == GENERAL_SCOPE_SIG:
        return GENERAL_SIG_TABS
    return GENERAL_ED_TABS


def _resolve_general_editor_scope(raw_scope: str | None) -> str:
    scope = str(raw_scope or "").strip().lower()
    return scope if scope in {GENERAL_SCOPE_ED, GENERAL_SCOPE_SIG} else GENERAL_SCOPE_ED


def _resolve_general_editor_module(scope: str, raw_module: str | None) -> str:
    tabs = _module_tabs_for_scope(scope)
    available = {str(tab["code"]) for tab in tabs}
    module_code = str(raw_module or "").strip()
    if module_code in available:
        return module_code
    editable = next((str(tab["code"]) for tab in tabs if bool(tab["editable"])), None)
    return editable or str(tabs[0]["code"])


def _build_ed_parameter_rows(db: Session, module_code: str) -> list[dict[str, object]]:
    items = list(
        db.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.module_code == module_code)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    rows: list[dict[str, object]] = []
    for item in items:
        key = (str(item.operacao or "").strip().lower(), str(item.controle or "").strip().lower())
        row = grouped.get(key)
        if row is None:
            row = {
                "id": item.id,
                "ordem": item.ordem or item.id,
                "operacao": item.operacao or "-",
                "controle": item.controle,
                "Parametro": item.Parametro or "",
                "ids": [item.id],
            }
            grouped[key] = row
            rows.append(row)
            continue
        row["ids"].append(item.id)
        if not str(row["Parametro"] or "").strip() and str(item.Parametro or "").strip():
            row["Parametro"] = item.Parametro or ""
    return rows


def _save_ed_parameter_rows(db: Session, module_code: str, form_data, rows: list[dict[str, object]]) -> None:
    for row in rows:
        row_id = int(row["id"])
        value = str(form_data.get(f"param_{row_id}") or "").strip()
        ids = [int(item_id) for item_id in (row.get("ids") or [])]
        if not ids:
            ids = [row_id]
        for item_id in ids:
            item = db.get(OperationalModuleItem, item_id)
            if item is None:
                continue
            item.Parametro = value or None
    db.commit()


def _build_sigilatura_parameter_rows(db: Session, module_code: str) -> list[dict[str, object]]:
    source_rows = sigilatura_service.build_admin_parameter_rows(db, module_code)
    rows: list[dict[str, object]] = []
    for row in source_rows:
        rows.append(
            {
                "id": str(row.get("key") or ""),
                "ordem": int(row.get("ordem") or 0),
                "operacao": str(row.get("operacao") or "").strip() or "-",
                "controle": str(row.get("controle") or "").strip() or "-",
                "Parametro": str(row.get("Parametro") or "").strip(),
            }
        )
    return rows


def _save_sigilatura_parameter_rows(db: Session, form_data, rows: list[dict[str, object]], module_code: str) -> None:
    updates = []
    for row in rows:
        row_id = str(row["id"])
        value = str(form_data.get(f"param_{row_id}") or "").strip()
        updates.append(
            {
                "operacao": str(row["operacao"]),
                "controle": str(row["controle"]),
                "Parametro": value,
            }
        )
    sigilatura_service.save_admin_parameter_overrides(db, module_code, updates)


def _build_general_editor_context(
    request: Request,
    db: Session,
    *,
    scope: str,
    module_code: str,
    status: str | None = None,
    error_message: str | None = None,
) -> dict:
    tabs = _module_tabs_for_scope(scope)
    active_tab = next((tab for tab in tabs if str(tab["code"]) == module_code), tabs[0])
    editable = bool(active_tab["editable"])

    if scope == GENERAL_SCOPE_SIG:
        rows = _build_sigilatura_parameter_rows(db, module_code)
    else:
        rows = _build_ed_parameter_rows(db, module_code)

    return {
        "page_title": "Edio Geral de Limites e Referncias",
        "page_description": "Ajuste rapidamente os parmetros operacionais por escopo e mdulo.",
        "scope": scope,
        "tabs": tabs,
        "active_module_code": module_code,
        "active_module_title": str(active_tab["title"]),
        "active_field_label": str(active_tab["field_label"]),
        "module_editable": editable,
        "rows": rows,
        "error_message": error_message,
        "success_message": "Parmetros atualizados com sucesso." if status == "saved" else None,
        "skip_message": "Este mdulo no possui edio nesta tela." if status == "skipped" else None,
        **layout_context(str(request.url.path), active_path="/configuracoes"),
    }


@router.get("/configuracoes", name="configuracoes_home")
def configuracoes_home(request: Request, _admin=Depends(require_admin)):
    context = {
        "page_title": "Configuraes",
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
    selected_area = (request.query_params.get("area", "") or "").strip().lower()
    if selected_area not in MODULE_AREA_GROUPS:
        selected_area = ""

    if not selected_module:
        if selected_area:
            allowed = set(MODULE_AREA_GROUPS[selected_area])
            selected_module = next((m["code"] for m in modules if m["code"] in allowed), "")
        selected_module = selected_module or (modules[0]["code"] if modules else "ed")

    resolved_area = selected_area or _resolve_module_area(selected_module)

    context = {
        "page_title": "Itens dos Modulos",
        "page_description": "Cadastre, edite e organize os itens e sua periodicidade operacional.",
        "modules": modules,
        "selected_module": selected_module,
        "selected_area": resolved_area,
        "module_area_groups": MODULE_AREA_GROUPS,
        **_build_module_admin_context_with_query(request, db, selected_module),
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
    selected_aba = request.query_params.get("aba", "").strip() or None
    context = {
        "request": request,
        **_build_module_admin_context_with_query(request, db, modulo_id, selected_aba=selected_aba),
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
    escopo: str | None = None,
    modulo: str | None = None,
    _admin=Depends(require_admin),
):
    scope = _resolve_general_editor_scope(escopo)
    module_code = _resolve_general_editor_module(scope, modulo)
    query = f"?modulo={quote_plus(module_code)}" if module_code else ""
    return RedirectResponse(url=f"/configuracoes/modulos-itens{query}", status_code=302)


@router.post("/cadastros/modulos-itens/temperatura-forno-ed/faixas", name="admin_temperatura_faixas_salvar")
async def admin_temperatura_faixas_salvar(
    _request: Request,
    _db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return RedirectResponse(url="/configuracoes/modulos-itens", status_code=303)


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
        "field_options": {"grupos_retificador": RETIFICADOR_GROUP_OPTIONS},
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
            "field_options": {"grupos_retificador": RETIFICADOR_GROUP_OPTIONS},
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
        "field_options": {"grupos_retificador": RETIFICADOR_GROUP_OPTIONS},
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
            "field_options": {"grupos_retificador": RETIFICADOR_GROUP_OPTIONS},
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

