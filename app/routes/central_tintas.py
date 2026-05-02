from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.central_tintas_service import (
    CentralTintasValidationError,
    central_tintas_schema_available,
    create_registro,
    delete_registro,
    list_registros,
    update_registro,
)
from app.services.navigation import layout_context
from app.services.shift_service import list_shared_options as shift_list_options


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter()


@router.get("/central-tintas", name="central_tintas")
def central_tintas(request: Request, db: Session = Depends(get_db)):
    page = int(request.query_params.get("page", "1") or "1")
    per_page = 50

    filters = {
        "data_inicial": request.query_params.get("data_inicial", ""),
        "data_final": request.query_params.get("data_final", ""),
        "responsavel": request.query_params.get("responsavel", ""),
        "turno": request.query_params.get("turno", ""),
    }

    try:
        data = list_registros(
            db,
            page=page,
            per_page=per_page,
            data_inicial=filters["data_inicial"],
            data_final=filters["data_final"],
            responsavel=filters["responsavel"],
            turno=filters["turno"],
        )
    except CentralTintasValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    base_filters = {
        key: value
        for key, value in filters.items()
        if str(value or "").strip()
    }

    prev_query = urlencode({**base_filters, "page": max(1, data["page"] - 1)})
    next_query = urlencode({**base_filters, "page": min(data["total_pages"], data["page"] + 1)})

    context = {
        "request": request,
        "page_title": "Central de Tintas",
        "page_description": "Log operacional continuo da Central de Tintas.",
        "rows": data["items"],
        "pagination": {
            "page": data["page"],
            "per_page": data["per_page"],
            "total": data["total"],
            "total_pages": data["total_pages"],
            "has_prev": data["page"] > 1,
            "has_next": data["page"] < data["total_pages"],
            "prev_url": f"/central-tintas?{prev_query}",
            "next_url": f"/central-tintas?{next_query}",
        },
        "filters": data["filters"],
        "turnos": shift_list_options(db).get("turnos", []),
        "responsaveis": shift_list_options(db).get("responsaveis", []),
        "schema_error_message": None if central_tintas_schema_available(db) else "Estrutura da Central de Tintas nao instalada. Execute as migrations.",
        **layout_context(str(request.url.path), active_path="/central-tintas", scope_source=request.query_params),
    }
    return templates.TemplateResponse(request=request, name="central_tintas_index.html", context=context)


@router.post("/central-tintas", name="central_tintas_criar")
async def central_tintas_criar(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    try:
        row = create_registro(db, payload if isinstance(payload, dict) else {})
    except CentralTintasValidationError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)
    return JSONResponse({"success": True, "row": row})


@router.put("/central-tintas/{registro_id}", name="central_tintas_atualizar")
async def central_tintas_atualizar(registro_id: int, request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    try:
        row = update_registro(db, registro_id, payload if isinstance(payload, dict) else {})
    except CentralTintasValidationError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)
    return JSONResponse({"success": True, "row": row})


@router.delete("/central-tintas/{registro_id}", name="central_tintas_excluir")
def central_tintas_excluir(registro_id: int, db: Session = Depends(get_db)):
    try:
        delete_registro(db, registro_id)
    except CentralTintasValidationError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=400)
    return JSONResponse({"success": True})
