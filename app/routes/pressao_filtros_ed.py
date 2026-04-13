from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.navigation import layout_context
from app.services.pressao_filtros_service import (
    STATUS_BADGES,
    STATUS_CONCLUIDO,
    STATUS_RASCUNHO,
    PressaoFiltrosValidationError,
    build_existing_context_status,
    build_filter_rows,
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
router = APIRouter(prefix="/pressao-filtros-ed", tags=["pressao-filtros-ed"])


def _default_turno_code(options) -> str:
    for turno in options.turnos:
        if (turno.codigo or "").strip() in {"1", "2", "3"}:
            return (turno.codigo or "").strip()
    return (options.turnos[0].codigo or options.turnos[0].nome) if options.turnos else ""


def _empty_context_values(options) -> dict:
    return {
        "data_referencia": date.today().isoformat(),
        "turno": _default_turno_code(options),
        "responsavel_nome": "",
        "observacoes_gerais": "",
    }


def _form_context(request: Request, db: Session, **extra) -> dict:
    options = list_context_options(db)
    context = {
        "request": request,
        "page_title": "Pressão dos Filtros ED",
        "page_description": "Painel operacional para leitura rápida dos 24 filtros da ED com destaque automático de alarmes.",
        "turno_options": options.turnos,
        "responsavel_options": options.responsaveis,
        "status_badges": STATUS_BADGES,
        **layout_context(str(request.url.path), active_path="/pressao-filtros-ed"),
    }
    context.update(extra)
    return context


@router.get("", name="pressao_filtros_home")
def pressao_filtros_home(request: Request, db: Session = Depends(get_db)):
    options = list_context_options(db)
    progress_rows = build_filter_rows()
    context = _form_context(
        request,
        db,
        context_values=_empty_context_values(options),
        filter_rows=[],
        progress_summary=summarize_progress(progress_rows),
        error_message=None,
        info_message="Selecione data, turno e responsável para carregar os 24 filtros.",
        existing_context=None,
        lancamento=None,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="pressao_filtros_ed/index.html", context=context)


@router.post("/carregar", name="pressao_filtros_load")
async def pressao_filtros_load(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        parsed_context = parse_context_payload(form)
        filter_rows = build_filter_rows()
        existing_context = build_existing_context_status(
            find_existing_lancamento_for_context(db, parsed_context.data_referencia, parsed_context.turno)
        )
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": parsed_context.data_referencia.isoformat(),
                "turno": parsed_context.turno,
                "responsavel_nome": parsed_context.responsavel_nome,
                "observacoes_gerais": parsed_context.observacoes_gerais or "",
            },
            filter_rows=filter_rows,
            progress_summary=summarize_progress(filter_rows),
            error_message=None,
            info_message=None,
            existing_context=existing_context,
            lancamento=None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="pressao_filtros_ed/index.html", context=context)
    except PressaoFiltrosValidationError as error:
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "turno": form.get("turno") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            filter_rows=[],
            progress_summary=summarize_progress([]),
            error_message=str(error),
            info_message=None,
            existing_context=None,
            lancamento=None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="pressao_filtros_ed/index.html", context=context, status_code=400)


@router.post("/salvar", name="pressao_filtros_save")
async def pressao_filtros_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    lancamento_id_raw = (form.get("lancamento_id") or "").strip()
    lancamento_id = int(lancamento_id_raw) if lancamento_id_raw else None
    submit_action = (form.get("submit_action") or STATUS_RASCUNHO).strip().lower()
    desired_status = STATUS_CONCLUIDO if submit_action == STATUS_CONCLUIDO else STATUS_RASCUNHO

    try:
        parsed_context = parse_context_payload(form)
        lancamento = save_lancamento(db, parsed_context, form, desired_status, lancamento_id=lancamento_id)
        return RedirectResponse(url=f"/pressao-filtros-ed/lancamentos/{lancamento.id}", status_code=303)
    except PressaoFiltrosValidationError as error:
        existing_context = None
        try:
            parsed_context = parse_context_payload(form)
            existing_context = build_existing_context_status(
                find_existing_lancamento_for_context(
                    db,
                    parsed_context.data_referencia,
                    parsed_context.turno,
                    exclude_id=lancamento_id,
                )
            )
        except PressaoFiltrosValidationError:
            existing_context = None
        existing_rows = {
            filtro_numero: {"valor_pressao": form.get(f"filtro_{filtro_numero}")}
            for filtro_numero in range(1, 25)
        }
        filter_rows = build_filter_rows(existing_rows)
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "turno": form.get("turno") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            filter_rows=filter_rows,
            progress_summary=summarize_progress(filter_rows),
            error_message=str(error),
            info_message=None,
            existing_context=existing_context,
            lancamento={"id": lancamento_id} if lancamento_id else None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="pressao_filtros_ed/index.html", context=context, status_code=400)


@router.get("/historico", name="pressao_filtros_history")
def pressao_filtros_history(
    request: Request,
    data_inicial: str | None = None,
    data_final: str | None = None,
    turno: str | None = None,
    status: str | None = None,
    somente_alarme: bool = False,
    db: Session = Depends(get_db),
):
    try:
        history = list_history(
            db,
            data_inicial=data_inicial,
            data_final=data_final,
            turno=turno,
            status=status,
            somente_alarme=somente_alarme,
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
            "turno": turno or "",
            "status": status or "",
            "somente_alarme": somente_alarme,
        },
        error_message=error_message,
    )
    return templates.TemplateResponse(request=request, name="pressao_filtros_ed/history.html", context=context)


@router.get("/lancamentos/{lancamento_id}", name="pressao_filtros_detail")
def pressao_filtros_detail(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de pressão dos filtros não encontrado")

    filter_rows = build_filter_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        lancamento=lancamento,
        filter_rows=filter_rows,
        progress_summary=summarize_progress(filter_rows),
    )
    return templates.TemplateResponse(request=request, name="pressao_filtros_ed/detail.html", context=context)


@router.get("/lancamentos/{lancamento_id}/editar", name="pressao_filtros_edit")
def pressao_filtros_edit(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de pressão dos filtros não encontrado")
    if lancamento.status == STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/pressao-filtros-ed/lancamentos/{lancamento.id}", status_code=303)

    filter_rows = build_filter_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        context_values={
            "data_referencia": lancamento.data_referencia.isoformat(),
            "turno": lancamento.turno,
            "responsavel_nome": lancamento.responsavel_nome,
            "observacoes_gerais": lancamento.observacoes_gerais or "",
        },
        filter_rows=filter_rows,
        progress_summary=summarize_progress(filter_rows),
        error_message=None,
        info_message="Rascunho carregado para continuação do preenchimento.",
        existing_context=build_existing_context_status(lancamento),
        lancamento=lancamento,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="pressao_filtros_ed/index.html", context=context)
