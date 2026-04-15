from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.espessura_ed_service import (
    STATUS_BADGES,
    STATUS_CONCLUIDO,
    STATUS_RASCUNHO,
    EspessuraEDValidationError,
    build_existing_context_status,
    build_point_rows,
    find_existing_lancamento_for_context,
    get_existing_row_map,
    get_lancamento,
    list_context_options,
    list_history,
    parse_context_payload,
    save_lancamento,
    summarize_progress,
)
from app.services.navigation import layout_context


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(prefix="/espessura-ed", tags=["espessura-ed"])


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
        "cis": "",
        "observacoes_gerais": "",
    }


def _form_context(request: Request, db: Session, **extra) -> dict:
    options = list_context_options(db)
    context = {
        "request": request,
        "page_title": "Espessura ED",
        "page_description": "Painel técnico para registrar medições de espessura da cataforese em 38 pontos por modelo e turno.",
        "turno_options": options.turnos,
        "modelo_options": options.modelos,
        "responsavel_options": options.responsaveis,
        "status_badges": STATUS_BADGES,
        **layout_context(str(request.url.path), active_path="/espessura-ed"),
    }
    context.update(extra)
    return context


@router.get("", name="espessura_ed_home")
def espessura_ed_home(request: Request, db: Session = Depends(get_db)):
    options = list_context_options(db)
    point_rows = build_point_rows()
    context = _form_context(
        request,
        db,
        context_values=_empty_context_values(options),
        point_rows=[],
        progress_summary=summarize_progress(point_rows),
        error_message=None,
        info_message="Selecione data, turno, modelo e responsável para carregar os 38 pontos de espessura.",
        existing_context=None,
        lancamento=None,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="espessura_ed/index.html", context=context)


@router.post("/carregar", name="espessura_ed_load")
async def espessura_ed_load(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        parsed_context = parse_context_payload(form)
        point_rows = build_point_rows()
        existing_context = build_existing_context_status(
            find_existing_lancamento_for_context(
                db,
                parsed_context.data_referencia,
                parsed_context.turno,
                parsed_context.modelo,
                parsed_context.cis,
            )
        )
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": parsed_context.data_referencia.isoformat(),
                "turno": parsed_context.turno,
                "modelo": parsed_context.modelo,
                "responsavel_nome": parsed_context.responsavel_nome,
                "cis": parsed_context.cis or "",
                "observacoes_gerais": parsed_context.observacoes_gerais or "",
            },
            point_rows=point_rows,
            progress_summary=summarize_progress(point_rows),
            error_message=None,
            info_message=None,
            existing_context=existing_context,
            lancamento=None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="espessura_ed/index.html", context=context)
    except EspessuraEDValidationError as error:
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "turno": form.get("turno") or "",
                "modelo": form.get("modelo") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "cis": form.get("cis") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            point_rows=[],
            progress_summary=summarize_progress([]),
            error_message=str(error),
            info_message=None,
            existing_context=None,
            lancamento=None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="espessura_ed/index.html", context=context, status_code=400)


@router.post("/salvar", name="espessura_ed_save")
async def espessura_ed_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    lancamento_id_raw = (form.get("lancamento_id") or "").strip()
    lancamento_id = int(lancamento_id_raw) if lancamento_id_raw else None
    submit_action = (form.get("submit_action") or STATUS_RASCUNHO).strip().lower()
    desired_status = STATUS_CONCLUIDO if submit_action == STATUS_CONCLUIDO else STATUS_RASCUNHO

    try:
        parsed_context = parse_context_payload(form)
        lancamento = save_lancamento(db, parsed_context, form, desired_status, lancamento_id=lancamento_id)
        return RedirectResponse(url=f"/espessura-ed/lancamentos/{lancamento.id}", status_code=303)
    except EspessuraEDValidationError as error:
        existing_context = None
        try:
            parsed_context = parse_context_payload(form)
            existing_context = build_existing_context_status(
                find_existing_lancamento_for_context(
                    db,
                    parsed_context.data_referencia,
                    parsed_context.turno,
                    parsed_context.modelo,
                    parsed_context.cis,
                    exclude_id=lancamento_id,
                )
            )
        except EspessuraEDValidationError:
            existing_context = None
        existing_rows = {
            ponto_numero: {"valor_espessura": form.get(f"ponto_{ponto_numero}")}
            for ponto_numero in range(1, 39)
        }
        point_rows = build_point_rows(existing_rows)
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "turno": form.get("turno") or "",
                "modelo": form.get("modelo") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "cis": form.get("cis") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            point_rows=point_rows,
            progress_summary=summarize_progress(point_rows),
            error_message=str(error),
            info_message=None,
            existing_context=existing_context,
            lancamento={"id": lancamento_id} if lancamento_id else None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="espessura_ed/index.html", context=context, status_code=400)


@router.get("/historico", name="espessura_ed_history")
def espessura_ed_history(
    request: Request,
    data_referencia: str | None = None,
    turno: str | None = None,
    modelo: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        history = list_history(
            db,
            data_referencia=data_referencia,
            turno=turno,
            modelo=modelo,
            status=status,
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
            "data_referencia": data_referencia or "",
            "turno": turno or "",
            "modelo": modelo or "",
            "status": status or "",
        },
        error_message=error_message,
    )
    return templates.TemplateResponse(request=request, name="espessura_ed/history.html", context=context)


@router.get("/lancamentos/{lancamento_id}", name="espessura_ed_detail")
def espessura_ed_detail(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de espessura ED não encontrado")

    point_rows = build_point_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        lancamento=lancamento,
        point_rows=point_rows,
        progress_summary=summarize_progress(point_rows),
    )
    return templates.TemplateResponse(request=request, name="espessura_ed/detail.html", context=context)


@router.get("/lancamentos/{lancamento_id}/editar", name="espessura_ed_edit")
def espessura_ed_edit(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de espessura ED não encontrado")
    if lancamento.status == STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/espessura-ed/lancamentos/{lancamento.id}", status_code=303)

    point_rows = build_point_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        context_values={
            "data_referencia": lancamento.data_referencia.isoformat(),
            "turno": lancamento.turno,
            "modelo": lancamento.modelo,
            "responsavel_nome": lancamento.responsavel_nome,
            "cis": lancamento.cis or "",
            "observacoes_gerais": lancamento.observacoes_gerais or "",
        },
        point_rows=point_rows,
        progress_summary=summarize_progress(point_rows),
        error_message=None,
        info_message="Rascunho carregado para continuação do preenchimento.",
        existing_context=build_existing_context_status(lancamento),
        lancamento=lancamento,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="espessura_ed/index.html", context=context)
