from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.cabine_pintura_service import CabinePinturaValidationError, create_relatorio as create_cabine_relatorio
from app.services.central_tintas_service import CentralTintasValidationError, create_relatorio as create_central_relatorio
from app.services.navigation import layout_context
from app.services.operacoes_service import build_operacoes_context
from app.services.shift_service import ShiftValidationError, create_shift, list_shared_options as shift_list_options
from app.services.sigilatura_service import SigilaturaValidationError, create_turno as create_sigilatura_turno


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter()


def _coerce_date(raw_value: str | None) -> date:
    if raw_value:
        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            pass
    return date.today()


def _render_operacoes(
    request: Request,
    db: Session,
    *,
    data_referencia: date,
    error_message: str | None = None,
    open_start_modal: bool = False,
    selected_module_code: str | None = None,
    form_data: dict | None = None,
):
    options = shift_list_options(db)
    context = build_operacoes_context(db, data_referencia)
    return templates.TemplateResponse(
        request=request,
        name="operacoes/index.html",
        context={
            "request": request,
            "page_title": "Centro Operacional da Pintura",
            "page_description": "Acompanhamento dos turnos operacionais do dia.",
            "turnos": options.get("turnos", []),
            "responsaveis": options.get("responsaveis", []),
            "error_message": error_message,
            "open_start_modal": open_start_modal,
            "selected_module_code": selected_module_code or request.query_params.get("module") or "",
            "form_data": form_data or {},
            **context,
            **layout_context(str(request.url.path), active_path="/operacoes", scope_source=request.query_params),
        },
        status_code=400 if error_message else 200,
    )


@router.get("/operacoes", name="operacoes")
def operacoes(request: Request, db: Session = Depends(get_db)):
    data_referencia = _coerce_date(request.query_params.get("data_referencia"))
    return _render_operacoes(request, db, data_referencia=data_referencia)


@router.post("/operacoes/iniciar", name="operacoes_iniciar")
def operacoes_iniciar(
    request: Request,
    db: Session = Depends(get_db),
    module_code: str = Form(...),
    data_referencia: str = Form(...),
    turno: str = Form(...),
    responsavel: str = Form(None),
):
    data_ref = _coerce_date(data_referencia)
    turno_value = str(turno or "").strip()
    responsavel_value = (responsavel or "").strip() or None

    try:
        if module_code == "pt":
            shift = create_shift(
                session=db,
                data_referencia=data_ref,
                turno=turno_value or None,
                responsavel_pted=responsavel_value,
                responsavel_lab=None,
                observacoes=None,
                operation_scope="pt",
                module_codes=["pt", "pressao-filtros-pt"],
            )
            return RedirectResponse(url=f"/turnos-pt/{shift.id}", status_code=303)

        if module_code == "ed":
            shift = create_shift(
                session=db,
                data_referencia=data_ref,
                turno=turno_value or None,
                responsavel_pted=responsavel_value,
                responsavel_lab=responsavel_value,
                observacoes=None,
                operation_scope="ed",
            )
            return RedirectResponse(url=f"/turnos/{shift.id}", status_code=303)

        if module_code == "sigilatura":
            turno_obj = create_sigilatura_turno(db, data_ref, turno_value, responsavel=responsavel_value)
            return RedirectResponse(url=f"/turnos-sigilatura/{turno_obj.id}", status_code=303)

        if module_code == "central-tintas":
            relatorio = create_central_relatorio(
                db,
                {"data_referencia": data_ref.isoformat(), "turno": turno_value, "responsavel": responsavel_value},
            )
            return RedirectResponse(url=f"/central-tintas/{relatorio.id}", status_code=303)

        if module_code == "cabine-pintura":
            relatorio = create_cabine_relatorio(
                db,
                {"data_referencia": data_ref.isoformat(), "turno": turno_value, "responsavel": responsavel_value},
            )
            return RedirectResponse(url=f"/cabine-pintura/{relatorio.id}", status_code=303)
    except (
        ShiftValidationError,
        SigilaturaValidationError,
        CentralTintasValidationError,
        CabinePinturaValidationError,
    ) as error:
        return _render_operacoes(
            request,
            db,
            data_referencia=data_ref,
            error_message=str(error),
            open_start_modal=True,
            selected_module_code=module_code,
            form_data={
                "data_referencia": data_ref.isoformat(),
                "turno": turno_value,
                "responsavel": responsavel_value or "",
            },
        )

    return _render_operacoes(
        request,
        db,
        data_referencia=data_ref,
        error_message="Módulo inválido para iniciar turno.",
        open_start_modal=True,
        selected_module_code=module_code,
        form_data={"data_referencia": data_ref.isoformat(), "turno": turno_value, "responsavel": responsavel_value or ""},
    )
