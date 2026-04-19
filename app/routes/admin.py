from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import OperationalModuleItem
from app.services.navigation import layout_context
from app.services.reference_service import (
    ADMIN_ENTITIES,
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
router = APIRouter(prefix="/cadastros", tags=["cadastros"])


def _format_temperature_parameter(valor_min: float | None, valor_max: float | None) -> str | None:
    if valor_min is not None and valor_max is not None:
        return f"{valor_min:g} a {valor_max:g} °C"
    if valor_min is not None:
        return f">= {valor_min:g} °C"
    if valor_max is not None:
        return f"<= {valor_max:g} °C"
    return None


@router.get("", name="cadastros_home")
def cadastros_home(request: Request):
    featured_cards = [
        {
            "title": "Faixas - Temperatura Forno ED",
            "description": "Edite rapidamente os valores minimo e maximo das zonas termicas usadas no turno.",
            "url": "/cadastros/modulos-itens/temperatura-forno-ed/faixas",
            "tag": "Faixas editaveis",
        }
    ]
    context = {
        "page_title": "Cadastros fixos",
        "page_description": "Estruturas iniciais para apoiar o crescimento do painel operacional.",
        "entities": ADMIN_ENTITIES.values(),
        "featured_cards": featured_cards,
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="admin/index.html", context=context)


@router.get("/modulos-itens/temperatura-forno-ed/faixas", name="admin_temperatura_faixas")
def admin_temperatura_faixas(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = None,
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
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="admin/temperature_ranges.html", context=context)


@router.post("/modulos-itens/temperatura-forno-ed/faixas", name="admin_temperatura_faixas_salvar")
async def admin_temperatura_faixas_salvar(request: Request, db: Session = Depends(get_db)):
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
            **layout_context(str(request.url.path)),
        }
        return templates.TemplateResponse(
            request=request,
            name="admin/temperature_ranges.html",
            context=context,
            status_code=400,
        )

    db.commit()
    return RedirectResponse(url="/cadastros/modulos-itens/temperatura-forno-ed/faixas?status=saved", status_code=303)


@router.get("/{entity}", name="admin_list")
def admin_list(entity: str, request: Request, db: Session = Depends(get_db)):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    active_filters = {}
    if entity == "modulos-itens":
        active_filters["module_code"] = request.query_params.get("module_code", "")

    records = list_records(db, entity, active_filters)
    context = {
        "page_title": config.title,
        "page_description": f"Gerencie os registros de {config.title.lower()}.",
        "entity": entity,
        "entity_config": config,
        "records": records,
        "column_labels": field_labels(config.list_fields, config),
        "active_filters": active_filters,
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="admin/list.html", context=context)


@router.get("/{entity}/novo", name="admin_create_form")
def admin_create_form(entity: str, request: Request):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    context = {
        "page_title": f"Novo registro - {config.title}",
        "page_description": f"Crie um novo registro para {config.title.lower()}.",
        "entity": entity,
        "entity_config": config,
        "record": None,
        "error_message": None,
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="admin/form.html", context=context)


@router.post("/{entity}/novo", name="admin_create")
async def admin_create(entity: str, request: Request, db: Session = Depends(get_db)):
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
        context = {
            "page_title": f"Novo registro - {config.title}",
            "page_description": f"Crie um novo registro para {config.title.lower()}.",
            "entity": entity,
            "entity_config": config,
            "record": payload,
            "error_message": "Nao foi possivel salvar. Verifique duplicidade ou campos obrigatorios.",
            **layout_context(str(request.url.path)),
        }
        return templates.TemplateResponse(request=request, name="admin/form.html", context=context, status_code=400)

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)


@router.get("/{entity}/{record_id}/editar", name="admin_edit_form")
def admin_edit_form(entity: str, record_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

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
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="admin/form.html", context=context)


@router.post("/{entity}/{record_id}/editar", name="admin_edit")
async def admin_edit(entity: str, record_id: int, request: Request, db: Session = Depends(get_db)):
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
            **layout_context(str(request.url.path)),
        }
        return templates.TemplateResponse(request=request, name="admin/form.html", context=context, status_code=400)

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)


@router.post("/{entity}/{record_id}/excluir", name="admin_delete")
def admin_delete(entity: str, record_id: int, db: Session = Depends(get_db)):
    try:
        get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado") from error

    deleted = delete_record(db, entity, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro nao encontrado")

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)
