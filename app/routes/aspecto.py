from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.aspecto_service import (
    MAX_REGISTROS_POR_LOTE,
    AspectoValidationError,
    build_form_entries,
    get_lancamento,
    list_context_options,
    list_history,
    parse_context_payload,
    parse_entries,
    save_lancamento,
    summarize_progress,
)
from app.services.navigation import layout_context


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(prefix="/aspecto", tags=["aspecto"])


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
    }


def _form_context(request: Request, db: Session, **extra) -> dict:
    options = list_context_options(db)
    context = {
        "request": request,
        "page_title": "Aspecto",
        "page_description": "Registro rápido de anomalias visuais por carroceria, em lote, com foco no ritmo operacional do turno.",
        "turno_options": options.turnos,
        "modelo_options": options.modelos,
        "responsavel_options": options.responsaveis,
        "max_registros": MAX_REGISTROS_POR_LOTE,
        **layout_context(str(request.url.path), active_path="/aspecto"),
    }
    context.update(extra)
    return context


@router.get("", name="aspecto_home")
def aspecto_home(request: Request, db: Session = Depends(get_db)):
    options = list_context_options(db)
    entries = build_form_entries(minimum_rows=1)
    context = _form_context(
        request,
        db,
        context_values=_empty_context_values(options),
        entries=entries,
        progress_summary=summarize_progress(entries),
        error_message=None,
        info_message="Preencha o contexto e adicione até 10 carrocerias com anomalias para salvar o lote de uma vez.",
    )
    return templates.TemplateResponse(request=request, name="aspecto/index.html", context=context)


@router.post("/salvar", name="aspecto_save")
async def aspecto_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        parsed_context = parse_context_payload(form)
        entries = parse_entries(form)
        lancamento = save_lancamento(db, parsed_context, entries)
        return RedirectResponse(url=f"/aspecto/{lancamento.id}", status_code=303)
    except AspectoValidationError as error:
        entries = build_form_entries(
            [
                {
                    "cis": cis,
                    "cod_posicao": cod_posicao,
                    "local": local,
                    "anomalia": anomalia,
                    "lado": lado,
                    "geracao": geracao,
                    "quantidade": quantidade,
                }
                for cis, cod_posicao, local, anomalia, lado, geracao, quantidade in zip(
                    form.getlist("cis"),
                    form.getlist("cod_posicao"),
                    form.getlist("local"),
                    form.getlist("anomalia"),
                    form.getlist("lado"),
                    form.getlist("geracao"),
                    form.getlist("quantidade"),
                    strict=False,
                )
            ],
            minimum_rows=1,
        )
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "turno": form.get("turno") or "",
                "modelo": form.get("modelo") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
            },
            entries=entries,
            progress_summary=summarize_progress(entries),
            error_message=str(error),
            info_message=None,
        )
        return templates.TemplateResponse(request=request, name="aspecto/index.html", context=context, status_code=400)


@router.get("/historico", name="aspecto_history")
def aspecto_history(
    request: Request,
    data_referencia: str | None = None,
    turno: str | None = None,
    modelo: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        history = list_history(db, data_referencia=data_referencia, turno=turno, modelo=modelo)
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
        },
        error_message=error_message,
    )
    return templates.TemplateResponse(request=request, name="aspecto/history.html", context=context)


@router.get("/{lancamento_id}", name="aspecto_detail")
def aspecto_detail(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento de aspecto não encontrado")

    context = _form_context(
        request,
        db,
        lancamento=lancamento,
        total_quantidade=sum(registro.quantidade for registro in lancamento.registros),
    )
    return templates.TemplateResponse(request=request, name="aspecto/detail.html", context=context)
