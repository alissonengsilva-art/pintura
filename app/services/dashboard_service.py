from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import OperationalModuleRecord, Turno
from app.services.operational_module_service import (
    MISSING_SCHEMA_MESSAGE,
    MODULE_CONFIGS,
    STATUS_LABELS,
    build_dashboard_snapshot as build_operational_dashboard_snapshot,
    build_history_row,
    operational_schema_available,
)


class DashboardValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DashboardFilters:
    data_referencia: date
    turno: str | None
    turno_options: list[Turno]


@dataclass(frozen=True)
class PendingFilters:
    data_referencia: date
    turno: str | None
    turno_options: list[Turno]


@dataclass(frozen=True)
class PendingSnapshot:
    filters: PendingFilters
    status_metrics: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    status_options: list[str]
    modulo_options: list[str]


@dataclass(frozen=True)
class DashboardSnapshot:
    filters: DashboardFilters
    has_global_alert: bool
    global_alert_message: str
    metrics: list[dict[str, Any]]
    pending_summary: list[dict[str, Any]]
    module_cards: list[dict[str, Any]]
    pending_rows: list[dict[str, Any]]
    occurrences: list[dict[str, Any]]
    alert_summaries: list[dict[str, Any]]


def parse_dashboard_filters(params: Any, session: Session) -> DashboardFilters:
    data_value = (params.get("data_referencia") or "").strip() if hasattr(params, "get") else ""
    if not data_value:
        target_date = date.today()
    else:
        try:
            target_date = date.fromisoformat(data_value)
        except ValueError as error:
            raise DashboardValidationError("Data inválida para o dashboard.") from error
    turno = (params.get("turno") or "").strip() if hasattr(params, "get") else ""
    turnos = list(session.scalars(select(Turno).where(Turno.ativo.is_(True)).order_by(Turno.codigo)).all())
    return DashboardFilters(data_referencia=target_date, turno=turno or None, turno_options=turnos)


def parse_pending_filters(params: Any, session: Session) -> PendingFilters:
    dashboard = parse_dashboard_filters(params, session)
    return PendingFilters(
        data_referencia=dashboard.data_referencia,
        turno=dashboard.turno,
        turno_options=dashboard.turno_options,
    )


def build_dashboard_snapshot(session: Session, filters: DashboardFilters) -> DashboardSnapshot:
    snapshot = build_operational_dashboard_snapshot(session, filters.data_referencia, filters.turno)
    schema_ready = operational_schema_available(session)
    occurrences = []
    for config in MODULE_CONFIGS.values():
        if not schema_ready:
            break
        statement = (
            select(OperationalModuleRecord)
            .options(joinedload(OperationalModuleRecord.setores))
            .where(OperationalModuleRecord.module_code == config.code)
            .where(OperationalModuleRecord.data_referencia == filters.data_referencia)
            .order_by(OperationalModuleRecord.updated_at.desc())
        )
        if filters.turno and config.supports_turno:
            statement = statement.where(OperationalModuleRecord.turno == filters.turno)
        record = session.scalars(statement).unique().first()
        if record is None:
            continue
        row = build_history_row(config, record)
        if row["desvios"] <= 0:
            continue
        occurrences.append(
            {
                "module_title": config.title,
                "occurrence_type": "Desvio",
                "reference_label": row["context_label"],
                "value_label": f"{row['desvios']} sinalizações",
                "context_label": row["status_geral_label"],
                "updated_label": row["data_label"],
                "detail_url": row["detail_url"],
                "tone": "warning",
            }
        )
    module_cards = []
    for card in snapshot["cards"]:
        tone = "success" if card["desvios"] == 0 and card["status_geral"] == STATUS_LABELS["CONCLUIDO"] else "warning"
        if card["status_geral"] == STATUS_LABELS["NAO_INICIADO"]:
            tone = "neutral"
        module_cards.append(
            {
                **card,
                "priority_tone": tone,
                "priority_label": card["status_geral"],
                "priority_description": f"PTED: {card['status_pted']} · Laboratório: {card['status_lab']}",
                "card_url": card["url"],
                "quick_action_label": card["action_label"],
                "quick_action_url": card["action_url"],
                "quick_action_tone": "primary" if card["action_label"] != "Visualizar" else "secondary",
                "history_url": card["history_url"],
                "total_launches": 1 if card["status_geral"] != STATUS_LABELS["NAO_INICIADO"] else 0,
                "concluded_launches": 1 if card["status_geral"] == STATUS_LABELS["CONCLUIDO"] else 0,
                "pending_launches": 1 if card["status_geral"] in {STATUS_LABELS['EM_ANDAMENTO'], STATUS_LABELS['PARCIAL']} else 0,
                "alert_count": card["desvios"],
            }
        )
    metrics = [
        {"label": "Módulos monitorados", "value": snapshot["total_modulos"], "tone": "neutral"},
        {"label": "Módulos com alerta", "value": snapshot["modulos_com_alerta"], "tone": "warning"},
        {"label": "Total de alertas", "value": snapshot["total_desvios"], "tone": "warning"},
    ]
    pending_summary = [
        {"label": "Pendências abertas", "value": sum(1 for card in module_cards if card["pending_launches"]), "tone": "warning"},
        {"label": "Em andamento", "value": sum(1 for card in module_cards if card["status_geral"] == STATUS_LABELS["EM_ANDAMENTO"]), "tone": "warning"},
        {"label": "Concluídas no período", "value": sum(1 for card in module_cards if card["status_geral"] == STATUS_LABELS["CONCLUIDO"]), "tone": "success"},
        {"label": "Vencidas", "value": 0, "tone": "neutral"},
    ]
    return DashboardSnapshot(
        filters=filters,
        has_global_alert=snapshot["total_desvios"] > 0,
        global_alert_message=(
            MISSING_SCHEMA_MESSAGE
            if not schema_ready
            else "Atenção: existem desvios operacionais no dia"
            if snapshot["total_desvios"] > 0
            else "Operação sem desvios ativos no recorte atual."
        ),
        metrics=metrics,
        pending_summary=pending_summary,
        module_cards=module_cards,
        pending_rows=[],
        occurrences=occurrences,
        alert_summaries=[],
    )


def build_pending_list_snapshot(session: Session, filters: PendingFilters) -> PendingSnapshot:
    rows = []
    for config in MODULE_CONFIGS.values():
        statement = (
            select(OperationalModuleRecord)
            .options(joinedload(OperationalModuleRecord.setores))
            .where(OperationalModuleRecord.module_code == config.code)
            .where(OperationalModuleRecord.data_referencia == filters.data_referencia)
            .order_by(OperationalModuleRecord.updated_at.desc())
        )
        if filters.turno and config.supports_turno:
            statement = statement.where(OperationalModuleRecord.turno == filters.turno)
        for record in session.scalars(statement).unique().all():
            row = build_history_row(config, record)
            if row["status_geral_label"] == STATUS_LABELS["CONCLUIDO"]:
                continue
            rows.append(
                {
                    "modulo": config.title,
                    "contexto": row["context_label"],
                    "status": row["status_geral_label"],
                    "pted": row["status_pted_label"],
                    "laboratorio": row["status_lab_label"],
                    "desvios": row["desvios"],
                    "detail_url": row["detail_url"],
                }
            )
    return PendingSnapshot(
        filters=filters,
        status_metrics=[
            {"label": "Pendências", "value": len(rows), "tone": "warning"},
            {"label": "Com desvio", "value": sum(1 for row in rows if row["desvios"] > 0), "tone": "warning"},
        ],
        rows=rows,
        status_options=[STATUS_LABELS["NAO_INICIADO"], STATUS_LABELS["EM_ANDAMENTO"], STATUS_LABELS["PARCIAL"]],
        modulo_options=[config.title for config in MODULE_CONFIGS.values()],
    )

