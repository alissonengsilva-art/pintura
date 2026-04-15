from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.navigation import layout_context
from app.services.poder_penetracao_service import (
    STATUS_BADGES,
    STATUS_CONCLUIDO,
    STATUS_RASCUNHO,
    PoderPenetracaoValidationError,
    build_existing_context_status,
    build_point_rows,
    default_week_label,
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
router = APIRouter(prefix="/poder-penetracao", tags=["poder-penetracao"])


def _default_model_name(options) -> str:
    return options.modelos[0].nome if options.modelos else ""


def _empty_context_values(options) -> dict:
    today = date.today()
    return {
        "data_referencia": today.isoformat(),
        "semana_referencia": default_week_label(today),
        "modelo": _default_model_name(options),
        "responsavel_nome": "",
        "cis": "",
        "velocidade": "",
        "tipo": "",
        "observacoes": "",
        "acao_corretiva": "",
    }


def _form_context(request: Request, db: Session, **extra) -> dict:
    options = list_context_options(db)
    context = {
        "request": request,
        "page_title": "Poder de Penetração",
        "page_description": "Controle semanal do ensaio de poder de penetração com cálculo automático de aprovação por ponto.",
        "modelo_options": options.modelos,
        "responsavel_options": options.responsaveis,
        "status_badges": STATUS_BADGES,
        **layout_context(str(request.url.path), active_path="/poder-penetracao"),
    }
    context.update(extra)
    return context


@router.get("", name="poder_penetracao_home")
def poder_penetracao_home(request: Request, db: Session = Depends(get_db)):
    options = list_context_options(db)
    point_rows = build_point_rows()
    context = _form_context(
        request,
        db,
        context_values=_empty_context_values(options),
        point_rows=[],
        progress_summary=summarize_progress(point_rows),
        error_message=None,
        info_message="Selecione a semana, o modelo e o responsável para carregar os 30 pontos do ensaio.",
        existing_context=None,
        lancamento=None,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="poder_penetracao/index.html", context=context)


@router.post("/carregar", name="poder_penetracao_load")
async def poder_penetracao_load(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        parsed_context = parse_context_payload(form)
        point_rows = build_point_rows()
        existing_context = build_existing_context_status(
            find_existing_lancamento_for_context(
                db,
                parsed_context.semana_referencia,
                parsed_context.modelo,
                parsed_context.cis,
            )
        )
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": parsed_context.data_referencia.isoformat(),
                "semana_referencia": parsed_context.semana_referencia,
                "modelo": parsed_context.modelo,
                "responsavel_nome": parsed_context.responsavel_nome,
                "cis": parsed_context.cis or "",
                "velocidade": parsed_context.velocidade or "",
                "tipo": parsed_context.tipo or "",
                "observacoes": parsed_context.observacoes or "",
                "acao_corretiva": parsed_context.acao_corretiva or "",
            },
            point_rows=point_rows,
            progress_summary=summarize_progress(point_rows),
            error_message=None,
            info_message=None,
            existing_context=existing_context,
            lancamento=None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="poder_penetracao/index.html", context=context)
    except PoderPenetracaoValidationError as error:
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "semana_referencia": form.get("semana_referencia") or "",
                "modelo": form.get("modelo") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "cis": form.get("cis") or "",
                "velocidade": form.get("velocidade") or "",
                "tipo": form.get("tipo") or "",
                "observacoes": form.get("observacoes") or "",
                "acao_corretiva": form.get("acao_corretiva") or "",
            },
            point_rows=[],
            progress_summary=summarize_progress([]),
            error_message=str(error),
            info_message=None,
            existing_context=None,
            lancamento=None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="poder_penetracao/index.html", context=context, status_code=400)


@router.post("/salvar", name="poder_penetracao_save")
async def poder_penetracao_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    lancamento_id_raw = (form.get("lancamento_id") or "").strip()
    lancamento_id = int(lancamento_id_raw) if lancamento_id_raw else None
    submit_action = (form.get("submit_action") or STATUS_RASCUNHO).strip().lower()
    desired_status = STATUS_CONCLUIDO if submit_action == STATUS_CONCLUIDO else STATUS_RASCUNHO

    try:
        parsed_context = parse_context_payload(form)
        lancamento = save_lancamento(db, parsed_context, form, desired_status, lancamento_id=lancamento_id)
        return RedirectResponse(url=f"/poder-penetracao/lancamentos/{lancamento.id}", status_code=303)
    except PoderPenetracaoValidationError as error:
        existing_context = None
        try:
            parsed_context = parse_context_payload(form)
            existing_context = build_existing_context_status(
                find_existing_lancamento_for_context(
                    db,
                    parsed_context.semana_referencia,
                    parsed_context.modelo,
                    parsed_context.cis,
                    exclude_id=lancamento_id,
                )
            )
        except PoderPenetracaoValidationError:
            existing_context = None
        existing_rows = {
            ponto_numero: {"valor_medido": form.get(f"ponto_{ponto_numero}")}
            for ponto_numero in range(1, 31)
        }
        point_rows = build_point_rows(existing_rows)
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "semana_referencia": form.get("semana_referencia") or "",
                "modelo": form.get("modelo") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "cis": form.get("cis") or "",
                "velocidade": form.get("velocidade") or "",
                "tipo": form.get("tipo") or "",
                "observacoes": form.get("observacoes") or "",
                "acao_corretiva": form.get("acao_corretiva") or "",
            },
            point_rows=point_rows,
            progress_summary=summarize_progress(point_rows),
            error_message=str(error),
            info_message=None,
            existing_context=existing_context,
            lancamento={"id": lancamento_id} if lancamento_id else None,
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="poder_penetracao/index.html", context=context, status_code=400)


@router.get("/historico", name="poder_penetracao_history")
def poder_penetracao_history(
    request: Request,
    semana_referencia: str | None = None,
    modelo: str | None = None,
    data_referencia: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        history = list_history(
            db,
            semana_referencia=semana_referencia,
            modelo=modelo,
            data_referencia=data_referencia,
            status=status,
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
            "semana_referencia": semana_referencia or "",
            "modelo": modelo or "",
            "data_referencia": data_referencia or "",
            "status": status or "",
        },
        error_message=error_message,
    )
    return templates.TemplateResponse(request=request, name="poder_penetracao/history.html", context=context)


@router.get("/lancamentos/{lancamento_id}", name="poder_penetracao_detail")
def poder_penetracao_detail(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de poder de penetração não encontrado")

    point_rows = build_point_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        lancamento=lancamento,
        point_rows=point_rows,
        progress_summary=summarize_progress(point_rows),
    )
    return templates.TemplateResponse(request=request, name="poder_penetracao/detail.html", context=context)


@router.get("/lancamentos/{lancamento_id}/editar", name="poder_penetracao_edit")
def poder_penetracao_edit(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de poder de penetração não encontrado")
    if lancamento.status == STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/poder-penetracao/lancamentos/{lancamento.id}", status_code=303)

    point_rows = build_point_rows(get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        context_values={
            "data_referencia": lancamento.data_referencia.isoformat(),
            "semana_referencia": lancamento.semana_referencia,
            "modelo": lancamento.modelo,
            "responsavel_nome": lancamento.responsavel_nome,
            "cis": lancamento.cis or "",
            "velocidade": lancamento.velocidade or "",
            "tipo": lancamento.tipo or "",
            "observacoes": lancamento.observacoes or "",
            "acao_corretiva": lancamento.acao_corretiva or "",
        },
        point_rows=point_rows,
        progress_summary=summarize_progress(point_rows),
        error_message=None,
        info_message="Rascunho semanal carregado para continuação do ensaio.",
        existing_context=build_existing_context_status(lancamento),
        lancamento=lancamento,
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="poder_penetracao/index.html", context=context)
