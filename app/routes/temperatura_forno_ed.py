from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.navigation import layout_context
from app.services.temperatura_forno_service import (
    STATUS_BADGES,
    STATUS_CONCLUIDO,
    STATUS_RASCUNHO,
    TemperaturaFornoValidationError,
    build_existing_context_status,
    build_zone_rows,
    find_existing_lancamento_for_context,
    get_existing_row_map,
    get_lancamento,
    list_context_options,
    list_history,
    parse_context_payload,
    save_lancamento,
    summarize_progress,
)


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(prefix="/temperatura-forno-ed", tags=["temperatura-forno-ed"])


def _empty_context_values() -> dict:
    return {
        "data_referencia": date.today().isoformat(),
        "responsavel_nome": "",
        "observacoes_gerais": "",
    }


def _form_context(request: Request, db: Session, **extra) -> dict:
    options = list_context_options(db)
    context = {
        "request": request,
        "page_title": "Temperatura Forno ED",
        "page_description": "Painel operacional para registrar as temperaturas das 12 zonas do forno da ED com destaque automático de desvios térmicos.",
        "responsavel_options": options.responsaveis,
        "status_badges": STATUS_BADGES,
        **layout_context(str(request.url.path), active_path="/temperatura-forno-ed"),
    }
    context.update(extra)
    return context


@router.get("", name="temperatura_forno_home")
def temperatura_forno_home(request: Request, db: Session = Depends(get_db)):
    progress_rows = build_zone_rows()
    context = _form_context(
        request,
        db,
        context_values=_empty_context_values(),
        zone_rows=[],
        progress_summary=summarize_progress(progress_rows),
        error_message=None,
        info_message="Selecione a data e o responsável para carregar as 12 zonas do forno.",
        existing_context=None,
        lancamento=None,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="temperatura_forno_ed/index.html", context=context)


@router.post("/carregar", name="temperatura_forno_load")
async def temperatura_forno_load(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        parsed_context = parse_context_payload(form)
        zone_rows = build_zone_rows()
        existing_context = build_existing_context_status(
            find_existing_lancamento_for_context(db, parsed_context.data_referencia)
        )
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": parsed_context.data_referencia.isoformat(),
                "responsavel_nome": parsed_context.responsavel_nome,
                "observacoes_gerais": parsed_context.observacoes_gerais or "",
            },
            zone_rows=zone_rows,
            progress_summary=summarize_progress(zone_rows),
            error_message=None,
            info_message=None,
            existing_context=existing_context,
            lancamento=None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="temperatura_forno_ed/index.html", context=context)
    except TemperaturaFornoValidationError as error:
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            zone_rows=[],
            progress_summary=summarize_progress([]),
            error_message=str(error),
            info_message=None,
            existing_context=None,
            lancamento=None,
            readonly=False,
        )
        return templates.TemplateResponse(
            request=request,
            name="temperatura_forno_ed/index.html",
            context=context,
            status_code=400,
        )


@router.post("/salvar", name="temperatura_forno_save")
async def temperatura_forno_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    lancamento_id_raw = (form.get("lancamento_id") or "").strip()
    lancamento_id = int(lancamento_id_raw) if lancamento_id_raw else None
    submit_action = (form.get("submit_action") or STATUS_RASCUNHO).strip().lower()
    desired_status = STATUS_CONCLUIDO if submit_action == STATUS_CONCLUIDO else STATUS_RASCUNHO

    try:
        parsed_context = parse_context_payload(form)
        lancamento = save_lancamento(db, parsed_context, form, desired_status, lancamento_id=lancamento_id)
        return RedirectResponse(url=f"/temperatura-forno-ed/lancamentos/{lancamento.id}", status_code=303)
    except TemperaturaFornoValidationError as error:
        existing_context = None
        try:
            parsed_context = parse_context_payload(form)
            existing_context = build_existing_context_status(
                find_existing_lancamento_for_context(
                    db,
                    parsed_context.data_referencia,
                    exclude_id=lancamento_id,
                )
            )
        except TemperaturaFornoValidationError:
            existing_context = None
        existing_rows = {
            zona_numero: {"valor_temperatura": form.get(f"zona_{zona_numero}")}
            for zona_numero in range(1, 13)
        }
        zone_rows = build_zone_rows(existing_rows)
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            zone_rows=zone_rows,
            progress_summary=summarize_progress(zone_rows),
            error_message=str(error),
            info_message=None,
            existing_context=existing_context,
            lancamento={"id": lancamento_id} if lancamento_id else None,
            readonly=False,
        )
        return templates.TemplateResponse(
            request=request,
            name="temperatura_forno_ed/index.html",
            context=context,
            status_code=400,
        )


@router.get("/historico", name="temperatura_forno_history")
def temperatura_forno_history(
    request: Request,
    data_inicial: str | None = None,
    data_final: str | None = None,
    status: str | None = None,
    somente_fora_padrao: bool = False,
    db: Session = Depends(get_db),
):
    try:
        history = list_history(
            db,
            data_inicial=data_inicial,
            data_final=data_final,
            status=status,
            somente_fora_padrao=somente_fora_padrao,
        )
        error_message = None
    except ValueError:
        history = []
        error_message = "Filtro de data inválido. Use o formato AAAA-MM-DD."

    context = _form_context(
        request,
        db,
        history=history,
        filters={
            "data_inicial": data_inicial or "",
            "data_final": data_final or "",
            "status": status or "",
            "somente_fora_padrao": somente_fora_padrao,
        },
        error_message=error_message,
    )
    return templates.TemplateResponse(request=request, name="temperatura_forno_ed/history.html", context=context)


@router.get("/lancamentos/{lancamento_id}", name="temperatura_forno_detail")
def temperatura_forno_detail(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de temperatura do forno não encontrado")

    zone_rows = build_zone_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        lancamento=lancamento,
        zone_rows=zone_rows,
        progress_summary=summarize_progress(zone_rows),
    )
    return templates.TemplateResponse(request=request, name="temperatura_forno_ed/detail.html", context=context)


@router.get("/lancamentos/{lancamento_id}/editar", name="temperatura_forno_edit")
def temperatura_forno_edit(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de temperatura do forno não encontrado")
    if lancamento.status == STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/temperatura-forno-ed/lancamentos/{lancamento.id}", status_code=303)

    zone_rows = build_zone_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        context_values={
            "data_referencia": lancamento.data_referencia.isoformat(),
            "responsavel_nome": lancamento.responsavel_nome,
            "observacoes_gerais": lancamento.observacoes_gerais or "",
        },
        zone_rows=zone_rows,
        progress_summary=summarize_progress(zone_rows),
        error_message=None,
        info_message="Rascunho carregado para continuação do preenchimento.",
        existing_context=build_existing_context_status(lancamento),
        lancamento=lancamento,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="temperatura_forno_ed/index.html", context=context)
