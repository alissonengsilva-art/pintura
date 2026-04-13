from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    EDLancamento,
    EDLancamentoItem,
    ItemED,
    PressaoFiltrosItem,
    PressaoFiltrosLancamento,
    TensaoRetificadoresItem,
    TensaoRetificadoresLancamento,
    TemperaturaFornoItem,
    TemperaturaFornoLancamento,
    Turno,
)
from app.services.ed_service import STATUS_CONCLUIDO as ED_STATUS_CONCLUIDO
from app.services.ed_service import STATUS_RASCUNHO as ED_STATUS_RASCUNHO
from app.services.ed_service import count_pending_launches as count_ed_pending_launches
from app.services.ed_service import list_context_options as list_ed_context_options
from app.services.ed_service import list_daily_launches as list_ed_daily_launches
from app.services.pressao_filtros_service import STATUS_CONCLUIDO as PRESSAO_STATUS_CONCLUIDO
from app.services.pressao_filtros_service import STATUS_RASCUNHO as PRESSAO_STATUS_RASCUNHO
from app.services.pressao_filtros_service import count_pending_launches as count_pressao_pending_launches
from app.services.pressao_filtros_service import list_daily_launches as list_pressao_daily_launches
from app.services.tensao_retificadores_service import STATUS_CONCLUIDO as TENSAO_STATUS_CONCLUIDO
from app.services.tensao_retificadores_service import STATUS_RASCUNHO as TENSAO_STATUS_RASCUNHO
from app.services.tensao_retificadores_service import count_outlier_zones as count_tensao_outlier_zones
from app.services.tensao_retificadores_service import count_pending_launches as count_tensao_pending_launches
from app.services.tensao_retificadores_service import list_daily_launches as list_tensao_daily_launches
from app.services.temperatura_forno_service import STATUS_CONCLUIDO as TEMPERATURA_STATUS_CONCLUIDO
from app.services.temperatura_forno_service import STATUS_RASCUNHO as TEMPERATURA_STATUS_RASCUNHO
from app.services.temperatura_forno_service import count_pending_launches as count_temperatura_pending_launches
from app.services.temperatura_forno_service import list_daily_launches as list_temperatura_daily_launches


@dataclass(frozen=True)
class DashboardMetric:
    label: str
    value: int
    helper: str
    tone: str = "primary"


@dataclass(frozen=True)
class DashboardModuleCard:
    title: str
    priority_label: str
    priority_tone: str
    priority_description: str
    total_launches: int
    concluded_launches: int
    pending_launches: int
    alert_count: int
    alert_label: str
    quick_action_url: str
    quick_action_label: str
    quick_action_tone: str
    history_url: str
    card_url: str


@dataclass(frozen=True)
class DashboardPendingRow:
    turno_codigo: str
    turno_label: str
    ed_pending: int
    pressao_pending: int
    tensao_pending: int

    @property
    def total_pending(self) -> int:
        return self.ed_pending + self.pressao_pending + self.tensao_pending


@dataclass(frozen=True)
class DashboardRecentLaunch:
    module_title: str
    occurrence_type: str
    reference_label: str
    value_label: str
    context_label: str
    updated_label: str
    detail_url: str
    tone: str


@dataclass(frozen=True)
class DashboardFilters:
    data_referencia: date
    turno: str
    turno_options: list[Turno]


@dataclass(frozen=True)
class DashboardSnapshot:
    filters: DashboardFilters
    has_global_alert: bool
    global_alert_message: str | None
    alert_summaries: list[DashboardAlertSummary]
    metrics: list[DashboardMetric]
    module_cards: list[DashboardModuleCard]
    pending_rows: list[DashboardPendingRow]
    occurrences: list[DashboardRecentLaunch]


@dataclass(frozen=True)
class DashboardAlertSummary:
    title: str
    count: int
    tone: str
    description: str
    action_url: str
    action_label: str


class DashboardValidationError(ValueError):
    pass


def list_turno_options(session: Session) -> list[Turno]:
    return list_ed_context_options(session).turnos


def parse_dashboard_filters(query_params, session: Session) -> DashboardFilters:
    data_value = (query_params.get("data_referencia") or query_params.get("data") or "").strip()
    turno = (query_params.get("turno") or "").strip()

    if not data_value:
        target_date = date.today()
    else:
        try:
            target_date = date.fromisoformat(data_value)
        except ValueError as error:
            raise DashboardValidationError("Data inválida para o dashboard.") from error

    return DashboardFilters(
        data_referencia=target_date,
        turno=turno,
        turno_options=list_turno_options(session),
    )


def build_dashboard_snapshot(session: Session, filters: DashboardFilters) -> DashboardSnapshot:
    ed_launches = list_ed_daily_launches(session, filters.data_referencia, turno=filters.turno or None)
    pressao_launches = list_pressao_daily_launches(session, filters.data_referencia, turno=filters.turno or None)
    tensao_launches = list_tensao_daily_launches(session, filters.data_referencia, turno=filters.turno or None)
    temperatura_launches = list_temperatura_daily_launches(session, filters.data_referencia)

    ed_pending = count_ed_pending_launches(session, filters.data_referencia, turno=filters.turno or None)
    pressao_pending = count_pressao_pending_launches(session, filters.data_referencia, turno=filters.turno or None)
    tensao_pending = count_tensao_pending_launches(session, filters.data_referencia, turno=filters.turno or None)
    temperatura_pending = count_temperatura_pending_launches(session, filters.data_referencia)

    ed_alert_count = _count_ed_outlier_items(session, filters.data_referencia, turno=filters.turno or None)
    pressao_alert_count = _count_pressao_alarm_filters(session, filters.data_referencia, turno=filters.turno or None)
    tensao_alert_count = count_tensao_outlier_zones(session, filters.data_referencia, turno=filters.turno or None)
    temperatura_alert_count = _count_temperatura_outlier_zones(session, filters.data_referencia)

    ed_alert_target = _get_ed_primary_alert_target(session, filters.data_referencia, turno=filters.turno or None)
    pressao_alert_target = _get_pressao_primary_alert_target(session, filters.data_referencia, turno=filters.turno or None)
    tensao_alert_target = _get_tensao_primary_alert_target(session, filters.data_referencia, turno=filters.turno or None)
    temperatura_alert_target = _get_temperatura_primary_alert_target(session, filters.data_referencia)

    module_cards = [
        _build_ed_module_card(ed_launches, ed_pending, ed_alert_count, ed_alert_target),
        _build_pressao_module_card(pressao_launches, pressao_pending, pressao_alert_count, pressao_alert_target),
        _build_tensao_module_card(tensao_launches, tensao_pending, tensao_alert_count, tensao_alert_target),
        _build_temperatura_module_card(
            temperatura_launches,
            temperatura_pending,
            temperatura_alert_count,
            temperatura_alert_target,
        ),
    ]

    modules_ok = sum(1 for row in module_cards if row.priority_tone == "success")
    modules_problem = sum(1 for row in module_cards if row.priority_tone in {"danger", "warning"})
    total_alerts = ed_alert_count + pressao_alert_count + tensao_alert_count + temperatura_alert_count
    total_pending = ed_pending + pressao_pending + tensao_pending + temperatura_pending

    metrics = [
        DashboardMetric("Módulos OK", modules_ok, "frentes concluídas e sem desvio", tone="success"),
        DashboardMetric("Módulos com problema", modules_problem, "críticos ou com atenção pendente", tone="warning"),
        DashboardMetric("Total de alertas", total_alerts, "desvios ativos no dia filtrado", tone="danger"),
        DashboardMetric("Pendências", total_pending, "lançamentos ainda em rascunho", tone="warning"),
    ]

    alert_summaries = [
        _build_alert_summary(
            title="Pressão dos Filtros ED",
            count=pressao_alert_count,
            tone="danger",
            singular="filtro em alarme",
            plural="filtros em alarme",
            action_url=pressao_alert_target["detail_url"] if pressao_alert_target else "/pressao-filtros-ed",
        ),
        _build_alert_summary(
            title="Temperatura Forno ED",
            count=temperatura_alert_count,
            tone="danger",
            singular="zona fora do padrão",
            plural="zonas fora do padrão",
            action_url=temperatura_alert_target["detail_url"] if temperatura_alert_target else "/temperatura-forno-ed",
        ),
        _build_alert_summary(
            title="Tensão dos Retificadores ED",
            count=tensao_alert_count,
            tone="danger",
            singular="zona fora do padrão",
            plural="zonas fora do padrão",
            action_url=tensao_alert_target["detail_url"] if tensao_alert_target else "/tensao-retificadores-ed",
        ),
        _build_alert_summary(
            title="ED",
            count=ed_alert_count,
            tone="warning",
            singular="item fora do padrão",
            plural="itens fora do padrão",
            action_url=ed_alert_target["detail_url"] if ed_alert_target else "/ed",
        ),
    ]

    pending_rows = [
        DashboardPendingRow(
            turno_codigo=_turno_value(turno),
            turno_label=_turno_label(turno),
            ed_pending=count_ed_pending_launches(session, filters.data_referencia, turno=_turno_value(turno) or None),
            pressao_pending=count_pressao_pending_launches(
                session,
                filters.data_referencia,
                turno=_turno_value(turno) or None,
            ),
            tensao_pending=count_tensao_pending_launches(
                session,
                filters.data_referencia,
                turno=_turno_value(turno) or None,
            ),
        )
        for turno in filters.turno_options
    ]

    occurrences = _build_occurrences(session, filters)
    return DashboardSnapshot(
        filters=filters,
        has_global_alert=total_alerts > 0,
        global_alert_message="Atenção: existem desvios no processo hoje" if total_alerts > 0 else None,
        alert_summaries=alert_summaries,
        metrics=metrics,
        module_cards=module_cards,
        pending_rows=pending_rows,
        occurrences=occurrences,
    )


def _build_alert_summary(
    title: str,
    count: int,
    tone: str,
    singular: str,
    plural: str,
    action_url: str,
) -> DashboardAlertSummary:
    if count > 0:
        description = f"{count} {singular if count == 1 else plural}"
        return DashboardAlertSummary(title, count, tone, description, action_url, "Abrir ocorrência")
    return DashboardAlertSummary(title, 0, "success", "Sem problemas no dia", action_url, "Abrir módulo")


def _build_ed_module_card(
    ed_launches: list[EDLancamento],
    pending_launches: int,
    alert_count: int,
    alert_target: dict[str, str] | None,
) -> DashboardModuleCard:
    concluded_launches = sum(1 for row in ed_launches if row.status == ED_STATUS_CONCLUIDO)
    priority_label = "Não iniciado"
    priority_tone = "muted"
    priority_description = "Nenhum lançamento encontrado para o filtro atual."
    quick_action_label = "Iniciar"
    quick_action_url = "/ed"
    quick_action_tone = "secondary"
    card_url = "/ed"
    if ed_launches:
        latest = ed_launches[0]
        card_url = f"/ed/lancamentos/{latest.id}"
        if alert_count:
            priority_label = "Crítico"
            priority_tone = "danger"
            priority_description = "Existem itens fora do padrão na ED e exigem ação imediata."
            quick_action_label = "Ver problema"
            quick_action_url = alert_target["detail_url"] if alert_target else card_url
            quick_action_tone = "danger"
        elif pending_launches:
            draft = next((row for row in ed_launches if row.status == ED_STATUS_RASCUNHO), latest)
            priority_label = "Atenção"
            priority_tone = "warning"
            priority_description = "Há lançamento em rascunho aguardando conclusão."
            quick_action_label = "Continuar"
            quick_action_url = f"/ed/lancamentos/{draft.id}/editar"
            quick_action_tone = "primary"
        else:
            priority_label = "OK"
            priority_tone = "success"
            priority_description = "Lançamento concluído sem desvios registrados."
            quick_action_label = "Visualizar"
            quick_action_url = card_url
            quick_action_tone = "secondary"

    return DashboardModuleCard(
        title="ED",
        priority_label=priority_label,
        priority_tone=priority_tone,
        priority_description=priority_description,
        total_launches=len(ed_launches),
        concluded_launches=concluded_launches,
        pending_launches=pending_launches,
        alert_count=alert_count,
        alert_label="item(ns) fora do padrão",
        quick_action_url=quick_action_url,
        quick_action_label=quick_action_label,
        quick_action_tone=quick_action_tone,
        history_url="/ed/historico",
        card_url=card_url,
    )


def _build_pressao_module_card(
    pressao_launches: list[PressaoFiltrosLancamento],
    pending_launches: int,
    alert_count: int,
    alert_target: dict[str, str] | None,
) -> DashboardModuleCard:
    concluded_launches = sum(1 for row in pressao_launches if row.status == PRESSAO_STATUS_CONCLUIDO)
    priority_label = "Não iniciado"
    priority_tone = "muted"
    priority_description = "Nenhum lançamento encontrado para o filtro atual."
    quick_action_label = "Iniciar"
    quick_action_url = "/pressao-filtros-ed"
    quick_action_tone = "secondary"
    card_url = "/pressao-filtros-ed"
    if pressao_launches:
        latest = pressao_launches[0]
        card_url = f"/pressao-filtros-ed/lancamentos/{latest.id}"
        if alert_count:
            priority_label = "Crítico"
            priority_tone = "danger"
            priority_description = "Há filtros em alarme e o processo precisa de intervenção."
            quick_action_label = "Ver problema"
            quick_action_url = alert_target["detail_url"] if alert_target else card_url
            quick_action_tone = "danger"
        elif pending_launches:
            draft = next((row for row in pressao_launches if row.status == PRESSAO_STATUS_RASCUNHO), latest)
            priority_label = "Atenção"
            priority_tone = "warning"
            priority_description = "Existe rascunho aberto aguardando fechamento."
            quick_action_label = "Continuar"
            quick_action_url = f"/pressao-filtros-ed/lancamentos/{draft.id}/editar"
            quick_action_tone = "primary"
        else:
            priority_label = "OK"
            priority_tone = "success"
            priority_description = "Lançamento concluído e sem alarmes ativos."
            quick_action_label = "Visualizar"
            quick_action_url = card_url
            quick_action_tone = "secondary"

    return DashboardModuleCard(
        title="Pressão dos Filtros ED",
        priority_label=priority_label,
        priority_tone=priority_tone,
        priority_description=priority_description,
        total_launches=len(pressao_launches),
        concluded_launches=concluded_launches,
        pending_launches=pending_launches,
        alert_count=alert_count,
        alert_label="filtro(s) em alarme",
        quick_action_url=quick_action_url,
        quick_action_label=quick_action_label,
        quick_action_tone=quick_action_tone,
        history_url="/pressao-filtros-ed/historico",
        card_url=card_url,
    )


def _build_temperatura_module_card(
    temperatura_launches: list[TemperaturaFornoLancamento],
    pending_launches: int,
    alert_count: int,
    alert_target: dict[str, str] | None,
) -> DashboardModuleCard:
    concluded_launches = sum(1 for row in temperatura_launches if row.status == TEMPERATURA_STATUS_CONCLUIDO)
    priority_label = "Não iniciado"
    priority_tone = "muted"
    priority_description = "Nenhum lançamento encontrado para o filtro atual."
    quick_action_label = "Iniciar"
    quick_action_url = "/temperatura-forno-ed"
    quick_action_tone = "secondary"
    card_url = "/temperatura-forno-ed"
    if temperatura_launches:
        latest = temperatura_launches[0]
        card_url = f"/temperatura-forno-ed/lancamentos/{latest.id}"
        if alert_count:
            priority_label = "Crítico"
            priority_tone = "danger"
            priority_description = "Existem zonas fora do padrão térmico no forno."
            quick_action_label = "Ver problema"
            quick_action_url = alert_target["detail_url"] if alert_target else card_url
            quick_action_tone = "danger"
        elif pending_launches:
            draft = next((row for row in temperatura_launches if row.status == TEMPERATURA_STATUS_RASCUNHO), latest)
            priority_label = "Atenção"
            priority_tone = "warning"
            priority_description = "Existe leitura térmica em rascunho aguardando conclusão."
            quick_action_label = "Continuar"
            quick_action_url = f"/temperatura-forno-ed/lancamentos/{draft.id}/editar"
            quick_action_tone = "primary"
        else:
            priority_label = "OK"
            priority_tone = "success"
            priority_description = "Lançamento concluído e sem desvios térmicos."
            quick_action_label = "Visualizar"
            quick_action_url = card_url
            quick_action_tone = "secondary"

    return DashboardModuleCard(
        title="Temperatura Forno ED",
        priority_label=priority_label,
        priority_tone=priority_tone,
        priority_description=priority_description,
        total_launches=len(temperatura_launches),
        concluded_launches=concluded_launches,
        pending_launches=pending_launches,
        alert_count=alert_count,
        alert_label="zona(s) fora do padrão",
        quick_action_url=quick_action_url,
        quick_action_label=quick_action_label,
        quick_action_tone=quick_action_tone,
        history_url="/temperatura-forno-ed/historico",
        card_url=card_url,
    )


def _build_tensao_module_card(
    tensao_launches: list[TensaoRetificadoresLancamento],
    pending_launches: int,
    alert_count: int,
    alert_target: dict[str, str] | None,
) -> DashboardModuleCard:
    concluded_launches = sum(1 for row in tensao_launches if row.status == TENSAO_STATUS_CONCLUIDO)
    priority_label = "Não iniciado"
    priority_tone = "muted"
    priority_description = "Nenhum lançamento encontrado para o filtro atual."
    quick_action_label = "Iniciar"
    quick_action_url = "/tensao-retificadores-ed"
    quick_action_tone = "secondary"
    card_url = "/tensao-retificadores-ed"
    if tensao_launches:
        latest = tensao_launches[0]
        card_url = f"/tensao-retificadores-ed/lancamentos/{latest.id}"
        if alert_count:
            priority_label = "Crítico"
            priority_tone = "danger"
            priority_description = "Existem zonas fora do padrão de tensão nos retificadores."
            quick_action_label = "Ver problema"
            quick_action_url = alert_target["detail_url"] if alert_target else card_url
            quick_action_tone = "danger"
        elif pending_launches:
            draft = next((row for row in tensao_launches if row.status == TENSAO_STATUS_RASCUNHO), latest)
            priority_label = "Atenção"
            priority_tone = "warning"
            priority_description = "Existe leitura de retificadores em rascunho aguardando conclusão."
            quick_action_label = "Continuar"
            quick_action_url = f"/tensao-retificadores-ed/lancamentos/{draft.id}/editar"
            quick_action_tone = "primary"
        else:
            priority_label = "OK"
            priority_tone = "success"
            priority_description = "Lançamentos concluídos sem desvios de tensão."
            quick_action_label = "Visualizar"
            quick_action_url = card_url
            quick_action_tone = "secondary"

    return DashboardModuleCard(
        title="Tensão dos Retificadores ED",
        priority_label=priority_label,
        priority_tone=priority_tone,
        priority_description=priority_description,
        total_launches=len(tensao_launches),
        concluded_launches=concluded_launches,
        pending_launches=pending_launches,
        alert_count=alert_count,
        alert_label="zona(s) fora do padrão",
        quick_action_url=quick_action_url,
        quick_action_label=quick_action_label,
        quick_action_tone=quick_action_tone,
        history_url="/tensao-retificadores-ed/historico",
        card_url=card_url,
    )


def _build_occurrences(
    session: Session,
    filters: DashboardFilters,
) -> list[DashboardRecentLaunch]:
    occurrences: list[tuple[Any, DashboardRecentLaunch]] = []

    ed_statement = (
        select(EDLancamento, EDLancamentoItem, ItemED)
        .join(EDLancamentoItem, EDLancamentoItem.lancamento_id == EDLancamento.id)
        .join(ItemED, ItemED.id == EDLancamentoItem.item_ed_id)
        .where(EDLancamento.data_referencia == filters.data_referencia)
        .where(EDLancamentoItem.fora_parametro.is_(True))
        .order_by(EDLancamento.updated_at.desc(), EDLancamentoItem.id.asc())
    )
    if filters.turno:
        ed_statement = ed_statement.where(EDLancamento.turno == filters.turno)
    for lancamento, item, item_ed in session.execute(ed_statement).all():
        occurrences.append(
            (
                lancamento.updated_at,
                DashboardRecentLaunch(
                    module_title="ED",
                    occurrence_type="Item fora do padrão",
                    reference_label=item_ed.descricao_controle,
                    value_label=item.valor_informado or "-",
                    context_label=f"{lancamento.setor} · Turno {lancamento.turno}",
                    updated_label=_format_timestamp(lancamento.updated_at),
                    detail_url=f"/ed/lancamentos/{lancamento.id}",
                    tone="warning",
                ),
            )
        )

    pressao_statement = (
        select(PressaoFiltrosLancamento, PressaoFiltrosItem)
        .join(PressaoFiltrosItem, PressaoFiltrosItem.lancamento_id == PressaoFiltrosLancamento.id)
        .where(PressaoFiltrosLancamento.data_referencia == filters.data_referencia)
        .where(PressaoFiltrosItem.em_alarme.is_(True))
        .order_by(PressaoFiltrosLancamento.updated_at.desc(), PressaoFiltrosItem.filtro_numero.asc())
    )
    if filters.turno:
        pressao_statement = pressao_statement.where(PressaoFiltrosLancamento.turno == filters.turno)
    for lancamento, item in session.execute(pressao_statement).all():
        occurrences.append(
            (
                lancamento.updated_at,
                DashboardRecentLaunch(
                    module_title="Pressão dos Filtros ED",
                    occurrence_type="Filtro em alarme",
                    reference_label=f"Filtro {item.filtro_numero}",
                    value_label=f"{_format_float(item.valor_pressao)} bar",
                    context_label=f"Turno {lancamento.turno}",
                    updated_label=_format_timestamp(lancamento.updated_at),
                    detail_url=f"/pressao-filtros-ed/lancamentos/{lancamento.id}",
                    tone="danger",
                ),
            )
        )

    temperatura_statement = (
        select(TemperaturaFornoLancamento, TemperaturaFornoItem)
        .join(TemperaturaFornoItem, TemperaturaFornoItem.lancamento_id == TemperaturaFornoLancamento.id)
        .where(TemperaturaFornoLancamento.data_referencia == filters.data_referencia)
        .where(TemperaturaFornoItem.fora_padrao.is_(True))
        .order_by(TemperaturaFornoLancamento.updated_at.desc(), TemperaturaFornoItem.zona_numero.asc())
    )
    for lancamento, item in session.execute(temperatura_statement).all():
        occurrences.append(
            (
                lancamento.updated_at,
                DashboardRecentLaunch(
                    module_title="Temperatura Forno ED",
                    occurrence_type="Zona fora do padrão",
                    reference_label=f"Zona {item.zona_numero}",
                    value_label=f"{_format_float(item.valor_temperatura)} °C",
                    context_label="Leitura diária do forno",
                    updated_label=_format_timestamp(lancamento.updated_at),
                    detail_url=f"/temperatura-forno-ed/lancamentos/{lancamento.id}",
                    tone="danger",
                ),
            )
        )

    tensao_statement = (
        select(TensaoRetificadoresLancamento, TensaoRetificadoresItem)
        .join(TensaoRetificadoresItem, TensaoRetificadoresItem.lancamento_id == TensaoRetificadoresLancamento.id)
        .where(TensaoRetificadoresLancamento.data_referencia == filters.data_referencia)
        .where(TensaoRetificadoresItem.fora_padrao.is_(True))
        .order_by(TensaoRetificadoresLancamento.updated_at.desc(), TensaoRetificadoresItem.zona_numero.asc())
    )
    if filters.turno:
        tensao_statement = tensao_statement.where(TensaoRetificadoresLancamento.turno == filters.turno)
    for lancamento, item in session.execute(tensao_statement).all():
        occurrences.append(
            (
                lancamento.updated_at,
                DashboardRecentLaunch(
                    module_title="Tensão dos Retificadores ED",
                    occurrence_type="Zona fora do padrão",
                    reference_label=f"Zona {item.zona_numero}",
                    value_label=f"{_format_float(item.valor_tensao)} V",
                    context_label=f"Turno {lancamento.turno} · {lancamento.modelo}",
                    updated_label=_format_timestamp(lancamento.updated_at),
                    detail_url=f"/tensao-retificadores-ed/lancamentos/{lancamento.id}",
                    tone="danger",
                ),
            )
        )

    occurrences.sort(key=lambda row: row[0], reverse=True)
    return [row for _, row in occurrences[:12]]


def _count_ed_outlier_items(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = (
        select(func.count(EDLancamentoItem.id))
        .join(EDLancamento, EDLancamento.id == EDLancamentoItem.lancamento_id)
        .where(EDLancamento.data_referencia == target_date)
        .where(EDLancamentoItem.fora_parametro.is_(True))
    )
    if turno:
        statement = statement.where(EDLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def _count_pressao_alarm_filters(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = (
        select(func.count(PressaoFiltrosItem.id))
        .join(PressaoFiltrosLancamento, PressaoFiltrosLancamento.id == PressaoFiltrosItem.lancamento_id)
        .where(PressaoFiltrosLancamento.data_referencia == target_date)
        .where(PressaoFiltrosItem.em_alarme.is_(True))
    )
    if turno:
        statement = statement.where(PressaoFiltrosLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def _count_temperatura_outlier_zones(session: Session, target_date: date) -> int:
    statement = (
        select(func.count(TemperaturaFornoItem.id))
        .join(TemperaturaFornoLancamento, TemperaturaFornoLancamento.id == TemperaturaFornoItem.lancamento_id)
        .where(TemperaturaFornoLancamento.data_referencia == target_date)
        .where(TemperaturaFornoItem.fora_padrao.is_(True))
    )
    return int(session.scalar(statement) or 0)


def _count_ed_launches_with_deviation(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = (
        select(func.count(distinct(EDLancamento.id)))
        .join(EDLancamentoItem, EDLancamentoItem.lancamento_id == EDLancamento.id)
        .where(EDLancamento.data_referencia == target_date)
        .where(EDLancamentoItem.fora_parametro.is_(True))
    )
    if turno:
        statement = statement.where(EDLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def _get_ed_primary_alert_target(session: Session, target_date: date, turno: str | None = None) -> dict[str, str] | None:
    statement = (
        select(EDLancamento)
        .options(joinedload(EDLancamento.itens))
        .join(EDLancamentoItem, EDLancamentoItem.lancamento_id == EDLancamento.id)
        .where(EDLancamento.data_referencia == target_date)
        .where(EDLancamentoItem.fora_parametro.is_(True))
        .order_by(EDLancamento.updated_at.desc(), EDLancamento.id.desc())
    )
    if turno:
        statement = statement.where(EDLancamento.turno == turno)
    lancamento = session.scalars(statement).unique().first()
    if lancamento is None:
        return None
    return {"detail_url": f"/ed/lancamentos/{lancamento.id}"}


def _get_pressao_primary_alert_target(session: Session, target_date: date, turno: str | None = None) -> dict[str, str] | None:
    statement = (
        select(PressaoFiltrosLancamento)
        .where(PressaoFiltrosLancamento.data_referencia == target_date)
        .where(PressaoFiltrosLancamento.total_filtros_em_alarme > 0)
        .order_by(PressaoFiltrosLancamento.updated_at.desc(), PressaoFiltrosLancamento.id.desc())
    )
    if turno:
        statement = statement.where(PressaoFiltrosLancamento.turno == turno)
    lancamento = session.scalars(statement).first()
    if lancamento is None:
        return None
    return {"detail_url": f"/pressao-filtros-ed/lancamentos/{lancamento.id}"}


def _get_temperatura_primary_alert_target(session: Session, target_date: date) -> dict[str, str] | None:
    statement = (
        select(TemperaturaFornoLancamento)
        .where(TemperaturaFornoLancamento.data_referencia == target_date)
        .where(TemperaturaFornoLancamento.total_zonas_fora_padrao > 0)
        .order_by(TemperaturaFornoLancamento.updated_at.desc(), TemperaturaFornoLancamento.id.desc())
    )
    lancamento = session.scalars(statement).first()
    if lancamento is None:
        return None
    return {"detail_url": f"/temperatura-forno-ed/lancamentos/{lancamento.id}"}


def _get_tensao_primary_alert_target(session: Session, target_date: date, turno: str | None = None) -> dict[str, str] | None:
    statement = (
        select(TensaoRetificadoresLancamento)
        .where(TensaoRetificadoresLancamento.data_referencia == target_date)
        .where(TensaoRetificadoresLancamento.total_zonas_fora_padrao > 0)
        .order_by(TensaoRetificadoresLancamento.updated_at.desc(), TensaoRetificadoresLancamento.id.desc())
    )
    if turno:
        statement = statement.where(TensaoRetificadoresLancamento.turno == turno)
    lancamento = session.scalars(statement).first()
    if lancamento is None:
        return None
    return {"detail_url": f"/tensao-retificadores-ed/lancamentos/{lancamento.id}"}


def _list_ed_alert_ids(session: Session, target_date: date, turno: str | None = None) -> set[int]:
    statement = (
        select(distinct(EDLancamento.id))
        .join(EDLancamentoItem, EDLancamentoItem.lancamento_id == EDLancamento.id)
        .where(EDLancamento.data_referencia == target_date)
        .where(EDLancamentoItem.fora_parametro.is_(True))
    )
    if turno:
        statement = statement.where(EDLancamento.turno == turno)
    return set(session.scalars(statement).all())


def _turno_value(turno: Turno) -> str:
    return (turno.codigo or turno.nome or "").strip()


def _turno_label(turno: Turno) -> str:
    codigo = (turno.codigo or "").strip()
    if codigo:
        return f"Turno {codigo}"
    return turno.nome


def _format_timestamp(value) -> str:
    if value is None:
        return "-"
    return value.strftime("%d/%m/%Y %H:%M")


def _format_float(value: float | None) -> str:
    if value is None:
        return "-"
    texto = f"{value:.1f}"
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto
