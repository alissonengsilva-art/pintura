from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.navigation import layout_context
from app.services.rugosidade_service import (
    MODELOS_FIXOS,
    STATUS_BADGES,
    STATUS_CONCLUIDO,
    STATUS_RASCUNHO,
    RugosidadeValidationError,
    build_existing_context_status,
    build_matrix_rows,
    find_existing_lancamento_for_context,
    get_existing_row_map,
    get_lancamento,
    list_context_options,
    list_history,
    parse_context_payload,
    save_lancamento,
    summarize_matrix,
)


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(prefix="/rugosidade", tags=["rugosidade"])


def _empty_context_values() -> dict:
    return {
        "data_referencia": date.today().isoformat(),
        "sequencia": "",
        "responsavel_nome": "",
        "observacoes_gerais": "",
    }


def _form_context(request: Request, db: Session, **extra) -> dict:
    options = list_context_options(db)
    context = {
        "request": request,
        "page_title": "Rugosidade",
        "page_description": "Controle matricial de rugosidade por modelo e sequência com destaque automático de desvios acima de 14 µin.",
        "responsavel_options": options.responsaveis,
        "status_badges": STATUS_BADGES,
        "modelos_fixos": MODELOS_FIXOS,
        **layout_context(str(request.url.path), active_path="/rugosidade"),
    }
    context.update(extra)
    return context


@router.get("", name="rugosidade_home")
def rugosidade_home(request: Request, db: Session = Depends(get_db)):
    matrix_rows = build_matrix_rows()
    context = _form_context(
        request,
        db,
        context_values=_empty_context_values(),
        matrix_rows=[],
        summary=summarize_matrix(matrix_rows),
        error_message=None,
        info_message="Informe data, sequência e responsável para carregar a matriz dos modelos fixos.",
        existing_context=None,
        lancamento=None,
    )
    return templates.TemplateResponse(request=request, name="rugosidade/index.html", context=context)


@router.post("/carregar", name="rugosidade_load")
async def rugosidade_load(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        parsed_context = parse_context_payload(form)
        matrix_rows = build_matrix_rows()
        existing_context = build_existing_context_status(
            find_existing_lancamento_for_context(db, parsed_context.data_referencia, parsed_context.sequencia)
        )
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": parsed_context.data_referencia.isoformat(),
                "sequencia": parsed_context.sequencia,
                "responsavel_nome": parsed_context.responsavel_nome,
                "observacoes_gerais": parsed_context.observacoes_gerais or "",
            },
            matrix_rows=matrix_rows,
            summary=summarize_matrix(matrix_rows),
            error_message=None,
            info_message=None,
            existing_context=existing_context,
            lancamento=None,
        )
        return templates.TemplateResponse(request=request, name="rugosidade/index.html", context=context)
    except RugosidadeValidationError as error:
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "sequencia": form.get("sequencia") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            matrix_rows=[],
            summary=summarize_matrix([]),
            error_message=str(error),
            info_message=None,
            existing_context=None,
            lancamento=None,
        )
        return templates.TemplateResponse(request=request, name="rugosidade/index.html", context=context, status_code=400)


@router.post("/salvar", name="rugosidade_save")
async def rugosidade_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    lancamento_id_raw = (form.get("lancamento_id") or "").strip()
    lancamento_id = int(lancamento_id_raw) if lancamento_id_raw else None
    submit_action = (form.get("submit_action") or STATUS_RASCUNHO).strip().lower()
    desired_status = STATUS_CONCLUIDO if submit_action == STATUS_CONCLUIDO else STATUS_RASCUNHO

    try:
        parsed_context = parse_context_payload(form)
        lancamento = save_lancamento(db, parsed_context, form, desired_status, lancamento_id=lancamento_id)
        return RedirectResponse(url=f"/rugosidade/lancamentos/{lancamento.id}", status_code=303)
    except RugosidadeValidationError as error:
        existing_context = None
        try:
            parsed_context = parse_context_payload(form)
            existing_context = build_existing_context_status(
                find_existing_lancamento_for_context(
                    db,
                    parsed_context.data_referencia,
                    parsed_context.sequencia,
                    exclude_id=lancamento_id,
                )
            )
        except RugosidadeValidationError:
            existing_context = None
        existing_rows = {
            modelo_codigo: {"valor_rugosidade": form.get(f"modelo_{modelo_codigo}")}
            for modelo_codigo in MODELOS_FIXOS
        }
        matrix_rows = build_matrix_rows(existing_rows)
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "sequencia": form.get("sequencia") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            matrix_rows=matrix_rows,
            summary=summarize_matrix(matrix_rows),
            error_message=str(error),
            info_message=None,
            existing_context=existing_context,
            lancamento={"id": lancamento_id} if lancamento_id else None,
        )
        return templates.TemplateResponse(request=request, name="rugosidade/index.html", context=context, status_code=400)


@router.get("/historico", name="rugosidade_history")
def rugosidade_history(
    request: Request,
    data_referencia: str | None = None,
    sequencia: str | None = None,
    status: str | None = None,
    somente_desvio: bool = False,
    db: Session = Depends(get_db),
):
    try:
        history = list_history(
            db,
            data_referencia=data_referencia,
            sequencia=sequencia,
            status=status,
            somente_desvio=somente_desvio,
        )
        error_message = None
    except ValueError:
        history = []
        error_message = "Filtro inválido. Revise a data informada."

    context = _form_context(
        request,
        db,
        history=history,
        filters={
            "data_referencia": data_referencia or "",
            "sequencia": sequencia or "",
            "status": status or "",
            "somente_desvio": somente_desvio,
        },
        error_message=error_message,
    )
    return templates.TemplateResponse(request=request, name="rugosidade/history.html", context=context)


@router.get("/lancamentos/{lancamento_id}", name="rugosidade_detail")
def rugosidade_detail(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de rugosidade não encontrado")

    matrix_rows = build_matrix_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        lancamento=lancamento,
        matrix_rows=matrix_rows,
        summary=summarize_matrix(matrix_rows),
    )
    return templates.TemplateResponse(request=request, name="rugosidade/detail.html", context=context)


@router.get("/lancamentos/{lancamento_id}/editar", name="rugosidade_edit")
def rugosidade_edit(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de rugosidade não encontrado")
    if lancamento.status == STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/rugosidade/lancamentos/{lancamento.id}", status_code=303)

    matrix_rows = build_matrix_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        context_values={
            "data_referencia": lancamento.data_referencia.isoformat(),
            "sequencia": lancamento.sequencia,
            "responsavel_nome": lancamento.responsavel_nome,
            "observacoes_gerais": lancamento.observacoes_gerais or "",
        },
        matrix_rows=matrix_rows,
        summary=summarize_matrix(matrix_rows),
        error_message=None,
        info_message="Rascunho de rugosidade carregado para continuação da matriz.",
        existing_context=build_existing_context_status(lancamento),
        lancamento=lancamento,
    )
    return templates.TemplateResponse(request=request, name="rugosidade/index.html", context=context)
