from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
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


@router.get("", name="cadastros_home")
def cadastros_home(request: Request):
    context = {
        "page_title": "Cadastros fixos",
        "page_description": "Estruturas iniciais para apoiar o crescimento do painel operacional.",
        "entities": ADMIN_ENTITIES.values(),
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="admin/index.html", context=context)


@router.get("/{entity}", name="admin_list")
def admin_list(entity: str, request: Request, db: Session = Depends(get_db)):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro não encontrado") from error

    records = list_records(db, entity)
    context = {
        "page_title": config.title,
        "page_description": f"Gerencie os registros de {config.title.lower()}.",
        "entity": entity,
        "entity_config": config,
        "records": records,
        "column_labels": field_labels(config.list_fields, config),
        **layout_context(str(request.url.path)),
    }
    return templates.TemplateResponse(request=request, name="admin/list.html", context=context)


@router.get("/{entity}/novo", name="admin_create_form")
def admin_create_form(entity: str, request: Request):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro não encontrado") from error

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
        raise HTTPException(status_code=404, detail="Cadastro não encontrado") from error

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
            "error_message": "Não foi possível salvar. Verifique duplicidade ou campos obrigatórios.",
            **layout_context(str(request.url.path)),
        }
        return templates.TemplateResponse(request=request, name="admin/form.html", context=context, status_code=400)

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)


@router.get("/{entity}/{record_id}/editar", name="admin_edit_form")
def admin_edit_form(entity: str, record_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        config = get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro não encontrado") from error

    record = get_record(db, entity, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Registro não encontrado")

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
        raise HTTPException(status_code=404, detail="Cadastro não encontrado") from error

    record = get_record(db, entity, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Registro não encontrado")

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
            "error_message": "Não foi possível atualizar. Verifique duplicidade ou campos obrigatórios.",
            **layout_context(str(request.url.path)),
        }
        return templates.TemplateResponse(request=request, name="admin/form.html", context=context, status_code=400)

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)


@router.post("/{entity}/{record_id}/excluir", name="admin_delete")
def admin_delete(entity: str, record_id: int, db: Session = Depends(get_db)):
    try:
        get_entity_config(entity)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Cadastro não encontrado") from error

    deleted = delete_record(db, entity, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro não encontrado")

    return RedirectResponse(url=f"/cadastros/{entity}", status_code=303)
