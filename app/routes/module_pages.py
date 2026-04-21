from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.navigation import layout_context
from app.services.operational_module_service import (
    MISSING_SCHEMA_MESSAGE,
    MODULE_STATUS_CONCLUIDO,
    STATUS_LABELS,
    SETOR_LABELS,
    SETOR_SEQUENCE,
    build_context_from_source,
    build_detail_context,
    build_history_rows,
    build_sector_view,
    context_to_form_values,
    get_master,
    get_master_by_context,
    get_module_config,
    get_or_create_master,
    operational_schema_available,
    resolve_context_defaults,
    save_sector,
)
from app.services.shift_service import (
    get_shift_by_id,
    shift_schema_available,
    update_shift_status,
)


templates = Jinja2Templates(directory=str(settings.templates_dir))


def _split_rows_by_status(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Separa registros em concluídos e em andamento."""
    concluidos = []
    andamento = []
    for row in rows:
        if row.get("status_geral") == MODULE_STATUS_CONCLUIDO:
            concluidos.append(row)
        else:
            andamento.append(row)
    return concluidos, andamento


def build_module_router(module_key: str) -> APIRouter:
    config = get_module_config(module_key)
    router = APIRouter(prefix=f"/{config.slug}", tags=[config.slug])

    def _base_context(request: Request, db: Session, **extra) -> dict:
        return {
            "request": request,
            "module_config": config,
            "page_title": config.title,
            "page_description": config.description,
            "setor_sequence": config.sector_sequence,
            "setor_labels": SETOR_LABELS,
            **layout_context(str(request.url.path), active_path=f"/{config.slug}", scope_source=request.query_params),
            **extra,
        }

    @router.get("")
    def module_hub(request: Request, db: Session = Depends(get_db), tab: str | None = None):
        """Central de registros com abas Concluídos e Em andamento."""
        rows = build_history_rows(db, config)
        rows_concluidos, rows_andamento = _split_rows_by_status(rows)
        active_tab = tab if tab in ("concluidos", "andamento") else "concluidos"
        shift_id_raw = request.query_params.get("shift_id")
        shift_id = None
        shift = None
        if shift_id_raw:
            try:
                shift_id = int(shift_id_raw)
                if shift_schema_available(db):
                    shift = get_shift_by_id(db, shift_id)
            except (ValueError, TypeError):
                pass
        turno_atual_url = None
        if shift:
            turno_atual_url = f"/turnos/{shift.id}?modulo={config.code}"
        return templates.TemplateResponse(
            request=request,
            name="modules/hub.html",
            context=_base_context(
                request,
                db,
                rows_concluidos=rows_concluidos,
                rows_andamento=rows_andamento,
                active_tab=active_tab,
                shift_id=shift_id,
                shift=shift,
                turno_atual_url=turno_atual_url,
                error_message=None if operational_schema_available(db) else MISSING_SCHEMA_MESSAGE,
            ),
        )

    @router.get("/checklist")
    def module_checklist(request: Request, db: Session = Depends(get_db), record_id: int | None = None):
        """Rota legada - redireciona para o hub ou checklist vinculado."""
        if record_id:
            # Redirecionar para a nova rota de checklist vinculado
            return RedirectResponse(
                url=f"/{config.slug}/registros/{record_id}/checklist",
                status_code=302,
            )
        # Sem record_id, redirecionar para o hub
        return RedirectResponse(
            url=f"/{config.slug}",
            status_code=302,
        )

    @router.get("/checklist-interno")
    def module_checklist_interno(request: Request, db: Session = Depends(get_db), record_id: int | None = None, action: str | None = None):
        """Formulário operacional do módulo (interno, usado pelo fluxo de inicialização)."""
        if record_id:
            return RedirectResponse(
                url=f"/{config.slug}/registros/{record_id}/checklist",
                status_code=302,
            )
        return RedirectResponse(url=f"/{config.slug}", status_code=302)

    @router.post("/setores/{setor_tipo}/salvar")
    async def module_save_sector(setor_tipo: str, request: Request, db: Session = Depends(get_db)):
        if setor_tipo not in config.sector_sequence:
            raise HTTPException(status_code=404, detail="Setor inválido")
        form = await request.form()
        error_message = None
        shift_id_raw = form.get("shift_id") or request.query_params.get("shift_id")
        shift_id = None
        if shift_id_raw:
            try:
                shift_id = int(str(shift_id_raw))
            except (TypeError, ValueError):
                shift_id = None
        try:
            parsed_context = build_context_from_source(config, form)
            action = "concluir" if (form.get("submit_action") or "").strip().lower() == "concluir" else "salvar"
            master = save_sector(db, config, parsed_context, setor_tipo, form, action, shift_id=shift_id)
            if shift_id and shift_schema_available(db):
                shift = get_shift_by_id(db, shift_id)
                if shift:
                    update_shift_status(db, shift)
        except ValueError as error:
            try:
                parsed_context = build_context_from_source(config, dict(form))
            except ValueError:
                parsed_context = build_context_from_source(config, resolve_context_defaults(config, db, form)[0])
            master = get_master_by_context(db, config, parsed_context)
            error_message = str(error)
        options = resolve_context_defaults(config, db, form)[1]
        setor_views = [build_sector_view(db, config, parsed_context, master, setor) for setor in config.sector_sequence]
        return templates.TemplateResponse(
            request=request,
            name="modules/index.html",
            context=_base_context(
                request,
                db,
                context_values=context_to_form_values(config, parsed_context),
                context_fields=config.context_fields,
                context_options=options,
                setor_views=setor_views,
                status_geral_label=master.status_geral if master else "NAO_INICIADO",
                status_geral_texto=STATUS_LABELS[master.status_geral] if master else STATUS_LABELS["NAO_INICIADO"],
                master=master,
                context_locked=bool(master and master.shift_id),
                turno_atual_url=_turno_atual_url(master),
                error_message=error_message,
            ),
            status_code=400 if error_message else 200,
        )

    @router.get("/historico")
    def module_history(request: Request, db: Session = Depends(get_db)):
        """Rota legada - redireciona para o hub com aba de concluídos."""
        return RedirectResponse(
            url=f"/{config.slug}?tab=concluidos",
            status_code=302,
        )

    @router.get("/registros/{record_id}")
    def module_detail(record_id: int, request: Request, db: Session = Depends(get_db)):
        master = get_master(db, record_id)
        if master is None or master.module_code != config.code:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        detail = build_detail_context(db, config, master)
        return templates.TemplateResponse(
            request=request,
            name="modules/detail.html",
            context=_base_context(request, db, turno_atual_url=_turno_atual_url(master), **detail),
        )

    @router.get("/registros/{record_id}/relatorio")
    def module_report(record_id: int, request: Request, setor: str | None = None, db: Session = Depends(get_db)):
        master = get_master(db, record_id)
        if master is None or master.module_code != config.code:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        detail = build_detail_context(db, config, master, report_setor=setor)
        return templates.TemplateResponse(
            request=request,
            name="modules/report.html",
            context=_base_context(request, db, page_title=config.report_title, report_setor=setor, **detail),
        )

    @router.get("/registros/{record_id}/checklist")
    def module_record_checklist(record_id: int, request: Request, db: Session = Depends(get_db)):
        """Compatibilidade: registros vinculados ao turno executam pela tela do turno."""
        master = get_master(db, record_id)
        if master is None or master.module_code != config.code:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        if master.shift_id:
            return RedirectResponse(url=f"/turnos/{master.shift_id}?modulo={config.code}", status_code=302)
        return RedirectResponse(url=f"/{config.slug}/registros/{record_id}", status_code=302)

    @router.post("/iniciar")
    async def module_start_cycle(request: Request, db: Session = Depends(get_db)):
        """Compatibilidade: redireciona o início para o turno atual."""
        form = await request.form()
        shift_id_raw = form.get("shift_id") or request.query_params.get("shift_id")
        if shift_id_raw:
            try:
                shift_id = int(str(shift_id_raw))
                if shift_schema_available(db):
                    shift = get_shift_by_id(db, shift_id)
                    if shift:
                        return RedirectResponse(
                            url=f"/turnos/{shift.id}?modulo={config.code}",
                            status_code=303,
                        )
            except (ValueError, TypeError):
                pass
        return RedirectResponse(url="/turno-atual", status_code=303)

    @router.get("/legado/{legacy_id}")
    def module_legacy_detail(legacy_id: int, request: Request, db: Session = Depends(get_db)):
        lancamento = config.legacy_detail_loader(db, legacy_id)
        if lancamento is None:
            raise HTTPException(status_code=404, detail="Registro legado não encontrado")
        return templates.TemplateResponse(
            request=request,
            name="modules/legacy_detail.html",
            context=_base_context(request, db, legacy=lancamento),
        )

    @router.get("/novo-turno")
    def module_new_cycle(request: Request, db: Session = Depends(get_db), from_id: int | None = None):
        """Compatibilidade: execução nova deve partir do turno atual."""
        master = get_master(db, from_id) if from_id else None
        redirect_url = _turno_atual_url(master)
        return RedirectResponse(url=redirect_url or "/turno-atual", status_code=302)

    return router


def _turno_atual_url(master) -> str | None:
    if master is None or master.shift_id is None:
        return None
    return f"/turnos/{master.shift_id}?modulo={master.module_code}"

