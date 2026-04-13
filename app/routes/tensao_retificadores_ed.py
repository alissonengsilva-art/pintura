from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.navigation import layout_context
from app.services.tensao_retificadores_service import (
    STATUS_BADGES,
    STATUS_CONCLUIDO,
    STATUS_RASCUNHO,
    TensaoRetificadoresValidationError,
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
router = APIRouter(prefix="/tensao-retificadores-ed", tags=["tensao-retificadores-ed"])


def _default_turno_code(options) -> str:
    for turno in options.turnos:
        if (turno.codigo or "").strip() in {"1", "2", "3"}:
            return (turno.codigo or "").strip()
    return (options.turnos[0].codigo or options.turnos[0].nome) if options.turnos else ""


def _default_model_name(options) -> str:
    return options.modelos[0].nome if options.modelos else ""


def _empty_context_values(options) -> dict:
    return {
        "data_referencia": date.today().isoformat(),
        "turno": _default_turno_code(options),
        "modelo": _default_model_name(options),
        "responsavel_nome": "",
        "observacoes_gerais": "",
    }


def _form_context(request: Request, db: Session, **extra) -> dict:
    options = list_context_options(db)
    context = {
        "request": request,
        "page_title": "Tensão dos Retificadores ED",
        "page_description": "Painel operacional para registrar a tensão das 29 zonas dos retificadores por data, turno e modelo.",
        "turno_options": options.turnos,
        "modelo_options": options.modelos,
        "responsavel_options": options.responsaveis,
        "status_badges": STATUS_BADGES,
        **layout_context(str(request.url.path), active_path="/tensao-retificadores-ed"),
    }
    context.update(extra)
    return context


@router.get("", name="tensao_retificadores_home")
def tensao_retificadores_home(request: Request, db: Session = Depends(get_db)):
    options = list_context_options(db)
    progress_rows = build_zone_rows()
    context = _form_context(
        request,
        db,
        context_values=_empty_context_values(options),
        zone_rows=[],
        progress_summary=summarize_progress(progress_rows),
        error_message=None,
        info_message="Selecione data, turno, modelo e responsável para carregar as 29 zonas dos retificadores.",
        existing_context=None,
        lancamento=None,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="tensao_retificadores_ed/index.html", context=context)


@router.post("/carregar", name="tensao_retificadores_load")
async def tensao_retificadores_load(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        parsed_context = parse_context_payload(form)
        zone_rows = build_zone_rows()
        existing_context = build_existing_context_status(
            find_existing_lancamento_for_context(db, parsed_context.data_referencia, parsed_context.turno, parsed_context.modelo)
        )
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": parsed_context.data_referencia.isoformat(),
                "turno": parsed_context.turno,
                "modelo": parsed_context.modelo,
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
        return templates.TemplateResponse(request=request, name="tensao_retificadores_ed/index.html", context=context)
    except TensaoRetificadoresValidationError as error:
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "turno": form.get("turno") or "",
                "modelo": form.get("modelo") or "",
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
        return templates.TemplateResponse(request=request, name="tensao_retificadores_ed/index.html", context=context, status_code=400)


@router.post("/salvar", name="tensao_retificadores_save")
async def tensao_retificadores_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    lancamento_id_raw = (form.get("lancamento_id") or "").strip()
    lancamento_id = int(lancamento_id_raw) if lancamento_id_raw else None
    submit_action = (form.get("submit_action") or STATUS_RASCUNHO).strip().lower()
    desired_status = STATUS_CONCLUIDO if submit_action == STATUS_CONCLUIDO else STATUS_RASCUNHO

    try:
        parsed_context = parse_context_payload(form)
        lancamento = save_lancamento(db, parsed_context, form, desired_status, lancamento_id=lancamento_id)
        return RedirectResponse(url=f"/tensao-retificadores-ed/lancamentos/{lancamento.id}", status_code=303)
    except TensaoRetificadoresValidationError as error:
        existing_context = None
        try:
            parsed_context = parse_context_payload(form)
            existing_context = build_existing_context_status(
                find_existing_lancamento_for_context(
                    db,
                    parsed_context.data_referencia,
                    parsed_context.turno,
                    parsed_context.modelo,
                    exclude_id=lancamento_id,
                )
            )
        except TensaoRetificadoresValidationError:
            existing_context = None
        existing_rows = {
            zona_numero: {"valor_tensao": form.get(f"zona_{zona_numero}")}
            for zona_numero in range(1, 30)
        }
        zone_rows = build_zone_rows(existing_rows)
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "turno": form.get("turno") or "",
                "modelo": form.get("modelo") or "",
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
        return templates.TemplateResponse(request=request, name="tensao_retificadores_ed/index.html", context=context, status_code=400)


@router.get("/historico", name="tensao_retificadores_history")
def tensao_retificadores_history(
    request: Request,
    data_inicial: str | None = None,
    data_final: str | None = None,
    turno: str | None = None,
    modelo: str | None = None,
    status: str | None = None,
    somente_fora_padrao: bool = False,
    db: Session = Depends(get_db),
):
    try:
        history = list_history(
            db,
            data_inicial=data_inicial,
            data_final=data_final,
            turno=turno,
            modelo=modelo,
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
            "turno": turno or "",
            "modelo": modelo or "",
            "status": status or "",
            "somente_fora_padrao": somente_fora_padrao,
        },
        error_message=error_message,
    )
    return templates.TemplateResponse(request=request, name="tensao_retificadores_ed/history.html", context=context)


@router.get("/lancamentos/{lancamento_id}", name="tensao_retificadores_detail")
def tensao_retificadores_detail(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de tensão dos retificadores não encontrado")

    zone_rows = build_zone_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        lancamento=lancamento,
        zone_rows=zone_rows,
        progress_summary=summarize_progress(zone_rows),
    )
    return templates.TemplateResponse(request=request, name="tensao_retificadores_ed/detail.html", context=context)


@router.get("/lancamentos/{lancamento_id}/editar", name="tensao_retificadores_edit")
def tensao_retificadores_edit(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de tensão dos retificadores não encontrado")
    if lancamento.status == STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/tensao-retificadores-ed/lancamentos/{lancamento.id}", status_code=303)

    zone_rows = build_zone_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        context_values={
            "data_referencia": lancamento.data_referencia.isoformat(),
            "turno": lancamento.turno,
            "modelo": lancamento.modelo,
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
    return templates.TemplateResponse(request=request, name="tensao_retificadores_ed/index.html", context=context)
