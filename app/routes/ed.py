from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import EDLancamento
from app.services.ed_service import (
    EVALUATION_LABELS,
    SETOR_OPTIONS,
    STATUS_BADGES,
    STATUS_CONCLUIDO,
    STATUS_RASCUNHO,
    TIPO_DIA_OPTIONS,
    EDValidationError,
    build_existing_context_status,
    build_item_rows,
    find_existing_lancamento_for_context,
    get_existing_row_map,
    get_lancamento,
    list_context_options,
    list_history,
    list_items_by_ids,
    load_items_for_context,
    parse_context_payload,
    save_lancamento,
    summarize_progress,
)
from app.services.navigation import layout_context


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(prefix="/ed", tags=["ed"])


def _default_turno_code(options) -> str:
    for turno in options.turnos:
        if (turno.codigo or "").strip() in {"1", "2", "3"}:
            return (turno.codigo or "").strip()
    return (options.turnos[0].codigo or options.turnos[0].nome) if options.turnos else ""


def _empty_context_values(options) -> dict:
    return {
        "data_referencia": date.today().isoformat(),
        "tipo_dia": "normal",
        "setor": "Laboratório",
        "turno": _default_turno_code(options),
        "responsavel_nome": "",
        "observacoes_gerais": "",
    }


def _form_context(request: Request, db: Session, **extra) -> dict:
    options = list_context_options(db)
    context = {
        "request": request,
        "page_title": "ED",
        "page_description": "Fluxo operacional para lançamento estruturado dos controles fixos da eletrodeposição.",
        "tipo_dia_options": TIPO_DIA_OPTIONS,
        "setor_options": SETOR_OPTIONS,
        "turno_options": options.turnos,
        "responsavel_options": options.responsaveis,
        "status_badges": STATUS_BADGES,
        "evaluation_labels": EVALUATION_LABELS,
        **layout_context(str(request.url.path), active_path="/ed"),
    }
    context.update(extra)
    return context


def _posted_item_map(form_data, item_ids: list[int]) -> dict[int, dict]:
    return {
        item_id: {
            "valor_informado": form_data.get(f"valor_{item_id}"),
            "observacao_item": form_data.get(f"observacao_{item_id}"),
        }
        for item_id in item_ids
    }


@router.get("", name="ed_home")
def ed_home(request: Request, db: Session = Depends(get_db)):
    options = list_context_options(db)
    context = _form_context(
        request,
        db,
        context_values=_empty_context_values(options),
        item_rows=[],
        progress_summary=summarize_progress([]),
        error_message=None,
        info_message="Selecione o contexto operacional e carregue os itens da ED.",
        existing_context=None,
        lancamento=None,
        form_mode="novo",
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="ed/index.html", context=context)


@router.post("/carregar", name="ed_load_items")
async def ed_load_items(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        parsed_context = parse_context_payload(form)
        items = load_items_for_context(db, parsed_context.setor, parsed_context.turno)
        item_rows = build_item_rows(items)
        existing_context = build_existing_context_status(
            find_existing_lancamento_for_context(
                db,
                parsed_context.data_referencia,
                parsed_context.setor,
                parsed_context.turno,
            )
        )
        info_message = None if items else "Nenhum item ED ativo foi encontrado para o contexto selecionado."
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": parsed_context.data_referencia.isoformat(),
                "tipo_dia": parsed_context.tipo_dia,
                "setor": parsed_context.setor,
                "turno": parsed_context.turno,
                "responsavel_nome": parsed_context.responsavel_nome,
                "observacoes_gerais": parsed_context.observacoes_gerais or "",
            },
            item_rows=item_rows,
            progress_summary=summarize_progress(item_rows),
            error_message=None,
            info_message=info_message,
            existing_context=existing_context,
            lancamento=None,
            form_mode="novo",
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="ed/index.html", context=context)
    except EDValidationError as error:
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "tipo_dia": form.get("tipo_dia") or "normal",
                "setor": form.get("setor") or "Laboratório",
                "turno": form.get("turno") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            item_rows=[],
            progress_summary=summarize_progress([]),
            error_message=str(error),
            info_message=None,
            existing_context=None,
            lancamento=None,
            form_mode="novo",
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="ed/index.html", context=context, status_code=400)


@router.post("/salvar", name="ed_save")
async def ed_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    item_ids = [int(item_id) for item_id in form.getlist("item_ids") if str(item_id).strip()]
    lancamento_id_raw = (form.get("lancamento_id") or "").strip()
    lancamento_id = int(lancamento_id_raw) if lancamento_id_raw else None
    submit_action = (form.get("submit_action") or STATUS_RASCUNHO).strip().lower()
    desired_status = STATUS_CONCLUIDO if submit_action == STATUS_CONCLUIDO else STATUS_RASCUNHO

    try:
        parsed_context = parse_context_payload(form)
        lancamento = save_lancamento(db, parsed_context, item_ids, form, desired_status, lancamento_id=lancamento_id)
        return RedirectResponse(url=f"/ed/lancamentos/{lancamento.id}", status_code=303)
    except EDValidationError as error:
        items = list_items_by_ids(db, item_ids)
        existing_context = None
        try:
            parsed_context = parse_context_payload(form)
            existing_context = build_existing_context_status(
                find_existing_lancamento_for_context(
                    db,
                    parsed_context.data_referencia,
                    parsed_context.setor,
                    parsed_context.turno,
                    exclude_id=lancamento_id,
                )
            )
        except EDValidationError:
            existing_context = None
        item_rows = build_item_rows(items, _posted_item_map(form, item_ids))
        context = _form_context(
            request,
            db,
            context_values={
                "data_referencia": form.get("data_referencia") or "",
                "tipo_dia": form.get("tipo_dia") or "normal",
                "setor": form.get("setor") or "Laboratório",
                "turno": form.get("turno") or "",
                "responsavel_nome": form.get("responsavel_nome") or "",
                "observacoes_gerais": form.get("observacoes_gerais") or "",
            },
            item_rows=item_rows,
            progress_summary=summarize_progress(item_rows),
            error_message=str(error),
            info_message=None,
            existing_context=existing_context,
            lancamento={"id": lancamento_id} if lancamento_id else None,
            form_mode="edicao" if lancamento_id else "novo",
            readonly=False,
        )
        return templates.TemplateResponse(request=request, name="ed/index.html", context=context, status_code=400)


@router.get("/historico", name="ed_history")
def ed_history(
    request: Request,
    data_referencia: str | None = None,
    data_inicial: str | None = None,
    data_final: str | None = None,
    setor: str | None = None,
    turno: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        history = list_history(
            db,
            data_referencia=data_referencia,
            data_inicial=data_inicial,
            data_final=data_final,
            setor=setor,
            turno=turno,
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
            "data_inicial": data_inicial or "",
            "data_final": data_final or "",
            "setor": setor or "",
            "turno": turno or "",
            "status": status or "",
        },
        error_message=error_message,
    )
    return templates.TemplateResponse(request=request, name="ed/history.html", context=context)


@router.get("/lancamentos/{lancamento_id}", name="ed_detail")
def ed_detail(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento ED não encontrado")

    context = _form_context(
        request,
        db,
        lancamento=lancamento,
        progress_summary=summarize_progress(
            [
                {"valor_informado": row.valor_informado or ""}
                for row in lancamento.itens
            ]
        ),
        item_rows=[
            {
                "item": row.item_ed,
                "valor_informado": row.valor_informado or "",
                "observacao_item": row.observacao_item or "",
                "avaliacao": {
                    "status": "neutral" if row.fora_parametro is None else ("out" if row.fora_parametro else "ok"),
                    "fora_parametro": row.fora_parametro,
                    "label": EVALUATION_LABELS["neutral"] if row.fora_parametro is None else EVALUATION_LABELS["out" if row.fora_parametro else "ok"],
                },
                "is_out": row.fora_parametro is True,
            }
            for row in sorted(lancamento.itens, key=lambda item_row: (item_row.item_ed.ordem_exibicao, item_row.item_ed.id))
        ],
    )
    return templates.TemplateResponse(request=request, name="ed/detail.html", context=context)


@router.get("/lancamentos/{lancamento_id}/editar", name="ed_edit")
def ed_edit(lancamento_id: int, request: Request, db: Session = Depends(get_db)):
    lancamento = get_lancamento(db, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=404, detail="Lançamento ED não encontrado")
    if lancamento.status == STATUS_CONCLUIDO:
        return RedirectResponse(url=f"/ed/lancamentos/{lancamento.id}", status_code=303)

    items = [row.item_ed for row in sorted(lancamento.itens, key=lambda item_row: (item_row.item_ed.ordem_exibicao, item_row.item_ed.id))]
    item_rows = build_item_rows(items, get_existing_row_map(lancamento))
    context = _form_context(
        request,
        db,
        context_values={
            "data_referencia": lancamento.data_referencia.isoformat(),
            "tipo_dia": lancamento.tipo_dia,
            "setor": lancamento.setor,
            "turno": lancamento.turno,
            "responsavel_nome": lancamento.responsavel_nome,
            "observacoes_gerais": lancamento.observacoes_gerais or "",
        },
        item_rows=item_rows,
        progress_summary=summarize_progress(item_rows),
        error_message=None,
        info_message="Rascunho carregado para continuação do preenchimento.",
        existing_context=build_existing_context_status(lancamento),
        lancamento=lancamento,
        form_mode="edicao",
        readonly=False,
    )
    return templates.TemplateResponse(request=request, name="ed/index.html", context=context)
