from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    OperationalModuleRecord,
    OperationalShift,
    SHIFT_STATUS_CONCLUIDO,
    SHIFT_STATUS_EM_ANDAMENTO,
    SHIFT_STATUS_NAO_INICIADO,
    SHIFT_STATUS_PARCIAL,
)
from app.services.operational_module_service import (
    SETOR_LABELS,
    STATUS_LABELS,
    build_detail_context,
    build_history_row,
    get_master,
    get_module_config,
    list_all_modules,
    operational_schema_available,
)
from app.services.shift_service import build_shift_detail, get_shift_by_id, list_shared_options, shift_schema_available


STATUS_OPTIONS = [
    {"value": SHIFT_STATUS_NAO_INICIADO, "label": "Nao iniciado"},
    {"value": SHIFT_STATUS_EM_ANDAMENTO, "label": "Em andamento"},
    {"value": SHIFT_STATUS_PARCIAL, "label": "Parcial"},
    {"value": SHIFT_STATUS_CONCLUIDO, "label": "Concluido"},
]


@dataclass(frozen=True)
class ReportFilters:
    data_inicio: date | None = None
    data_fim: date | None = None
    turno: str | None = None
    modulo: str | None = None
    setor: str | None = None
    responsavel: str | None = None
    status: str | None = None
    visao: str = "modulos"


def report_filter_options(session: Session) -> dict[str, Any]:
    shared = list_shared_options(session)
    return {
        "turnos": shared.get("turnos", []),
        "responsaveis": shared.get("responsaveis", []),
        "modulos": list_all_modules(),
        "setores": [
            {"value": "", "label": "Todos"},
            {"value": "PTED", "label": SETOR_LABELS["PTED"]},
            {"value": "LABORATORIO", "label": SETOR_LABELS["LABORATORIO"]},
        ],
        "visoes": [
            {"value": "modulos", "label": "Por modulo"},
            {"value": "turnos", "label": "Turno completo"},
        ],
        "status_options": STATUS_OPTIONS,
    }


def _matches_responsavel(value: str | None, target: str | None) -> bool:
    if not target:
        return True
    return value == target


def _build_module_rows(session: Session, filters: ReportFilters) -> list[dict[str, Any]]:
    if not operational_schema_available(session):
        return []

    statement = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores), joinedload(OperationalModuleRecord.shift))
        .order_by(OperationalModuleRecord.data_referencia.desc(), OperationalModuleRecord.updated_at.desc())
    )
    if filters.data_inicio:
        statement = statement.where(OperationalModuleRecord.data_referencia >= filters.data_inicio)
    if filters.data_fim:
        statement = statement.where(OperationalModuleRecord.data_referencia <= filters.data_fim)
    if filters.turno:
        statement = statement.where(OperationalModuleRecord.turno == filters.turno)
    if filters.modulo:
        statement = statement.where(OperationalModuleRecord.module_code == filters.modulo)
    if filters.status:
        statement = statement.where(OperationalModuleRecord.status_geral == filters.status)

    rows: list[dict[str, Any]] = []
    for master in session.scalars(statement).unique().all():
        config = get_module_config(master.module_code)
        history = build_history_row(config, master)

        setor_specs = []
        if filters.setor == "PTED":
            setor_specs = [("PTED", history["responsavel_pted"], history["status_pted"], history["status_pted_label"], history["report_pted_url"])]
        elif filters.setor == "LABORATORIO":
            setor_specs = [("LABORATORIO", history["responsavel_lab"], history["status_lab"], history["status_lab_label"], history["report_lab_url"])]
        else:
            setor_specs = [(None, None, history["status_geral"], history["status_geral_label"], history["report_url"])]

        for setor, responsavel, status, status_label, pdf_url in setor_specs:
            if filters.responsavel and setor is not None and not _matches_responsavel(responsavel, filters.responsavel):
                continue
            if filters.responsavel and setor is None and filters.responsavel not in {history["responsavel_pted"], history["responsavel_lab"]}:
                continue
            if filters.status and status != filters.status:
                continue

            preenchidos = 0
            total = 0
            if setor is None:
                for item in master.setores:
                    metricas = item.metricas or {}
                    preenchidos += int(metricas.get("preenchidos") or 0)
                    total += int(metricas.get("total") or 0)
            else:
                item = next((sector for sector in master.setores if sector.setor_tipo == setor), None)
                metricas = item.metricas or {}
                preenchidos = int(metricas.get("preenchidos") or 0)
                total = int(metricas.get("total") or 0)

            rows.append(
                {
                    "kind": "modulo",
                    "record_id": master.id,
                    "module_code": master.module_code,
                    "data_label": history["data_label"],
                    "turno_label": master.turno or "-",
                    "modulo_label": config.title,
                    "setor_label": SETOR_LABELS[setor] if setor else "PTED + Laboratorio",
                    "responsavel_label": responsavel if setor else f"{history['responsavel_pted']} / {history['responsavel_lab']}",
                    "status_geral": status,
                    "status_label": status_label,
                    "preenchidos": preenchidos,
                    "total": total,
                    "desvios": int(history["desvios"] or 0),
                    "detail_url": f"/relatorios/visualizar/modulos/{master.module_code}/{master.id}" + (f"?setor={setor}" if setor else ""),
                    "pdf_url": pdf_url,
                }
            )
    return rows


def _build_shift_rows(session: Session, filters: ReportFilters) -> list[dict[str, Any]]:
    if not shift_schema_available(session):
        return []

    statement = (
        select(OperationalShift)
        .options(joinedload(OperationalShift.modulos))
        .order_by(OperationalShift.data_referencia.desc(), OperationalShift.turno.desc())
    )
    if filters.data_inicio:
        statement = statement.where(OperationalShift.data_referencia >= filters.data_inicio)
    if filters.data_fim:
        statement = statement.where(OperationalShift.data_referencia <= filters.data_fim)
    if filters.turno:
        statement = statement.where(OperationalShift.turno == filters.turno)
    if filters.status:
        statement = statement.where(OperationalShift.status_geral == filters.status)
    if filters.responsavel:
        statement = statement.where(
            (OperationalShift.responsavel_pted == filters.responsavel)
            | (OperationalShift.responsavel_lab == filters.responsavel)
        )

    rows: list[dict[str, Any]] = []
    for shift in session.scalars(statement).unique().all():
        detail = build_shift_detail(session, shift)
        if filters.modulo and not any(module["code"] == filters.modulo for module in detail.get("modules", [])):
            continue
        rows.append(
            {
                "kind": "turno",
                "shift_id": shift.id,
                "data_label": detail["data_label"],
                "turno_label": detail.get("turno") or "-",
                "modulo_label": "Turno completo",
                "setor_label": "PTED + Laboratorio",
                "responsavel_label": f"{detail.get('responsavel_pted') or '-'} / {detail.get('responsavel_lab') or '-'}",
                "status_geral": detail["status_geral"],
                "status_label": detail["status_geral_label"],
                "preenchidos": detail["concluidos"],
                "total": detail["total_modules"],
                "desvios": sum(int(module.get("desvios") or 0) for module in detail.get("modules", [])),
                "detail_url": f"/relatorios/visualizar/turnos/{shift.id}",
                "pdf_url": f"/relatorios/turnos/{shift.id}/pdf",
            }
        )
    return rows


def build_reports_snapshot(session: Session, filters: ReportFilters) -> dict[str, Any]:
    rows = _build_shift_rows(session, filters) if filters.visao == "turnos" else _build_module_rows(session, filters)
    metrics = [
        {"label": "Linhas", "value": len(rows)},
        {"label": "Turnos", "value": len({row.get("shift_id", row.get("record_id")) for row in rows})},
        {"label": "Concluidos", "value": sum(1 for row in rows if row["status_geral"] == SHIFT_STATUS_CONCLUIDO)},
        {"label": "Desvios", "value": sum(int(row["desvios"] or 0) for row in rows)},
    ]
    return {"filters": filters, "rows": rows, "metrics": metrics}


def build_shift_pdf_context(session: Session, shift_id: int) -> dict[str, Any] | None:
    shift = get_shift_by_id(session, shift_id)
    if not shift:
        return None
    return build_shift_detail(session, shift)


def build_shift_report_detail(session: Session, shift_id: int) -> dict[str, Any] | None:
    shift = get_shift_by_id(session, shift_id)
    if not shift:
        return None
    return build_shift_detail(session, shift)


def build_module_report_detail(session: Session, module_code: str, record_id: int, setor: str | None = None) -> dict[str, Any] | None:
    master = get_master(session, record_id)
    if master is None or master.module_code != module_code:
        return None
    config = get_module_config(module_code)
    detail = build_detail_context(session, config, master, report_setor=setor)
    detail["module_config"] = config
    detail["report_setor"] = setor
    return detail
