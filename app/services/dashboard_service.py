from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AspectoLancamento,
    AspectoRegistro,
    EDLancamento,
    EDLancamentoItem,
    EspessuraEDItem,
    EspessuraEDLancamento,
    ItemED,
    PoderPenetracaoItem,
    PoderPenetracaoLancamento,
    PressaoFiltrosItem,
    PressaoFiltrosLancamento,
    RugosidadeItem,
    RugosidadeLancamento,
    TensaoRetificadoresItem,
    TensaoRetificadoresLancamento,
    TemperaturaFornoItem,
    TemperaturaFornoLancamento,
    Turno,
)
from app.services.aspecto_service import count_daily_records as count_aspecto_daily_records
from app.services.aspecto_service import list_daily_launches as list_aspecto_daily_launches
from app.services.ed_service import STATUS_CONCLUIDO as ED_STATUS_CONCLUIDO
from app.services.ed_service import STATUS_RASCUNHO as ED_STATUS_RASCUNHO
from app.services.ed_service import count_pending_launches as count_ed_pending_launches
from app.services.ed_service import list_context_options as list_ed_context_options
from app.services.ed_service import list_daily_launches as list_ed_daily_launches
from app.services.espessura_ed_service import STATUS_CONCLUIDO as ESPESSURA_STATUS_CONCLUIDO
from app.services.espessura_ed_service import STATUS_RASCUNHO as ESPESSURA_STATUS_RASCUNHO
from app.services.espessura_ed_service import count_daily_filled_points as count_espessura_daily_filled_points
from app.services.espessura_ed_service import count_pending_launches as count_espessura_pending_launches
from app.services.espessura_ed_service import list_daily_launches as list_espessura_daily_launches
from app.services.poder_penetracao_service import STATUS_CONCLUIDO as PODER_STATUS_CONCLUIDO
from app.services.poder_penetracao_service import STATUS_RASCUNHO as PODER_STATUS_RASCUNHO
from app.services.poder_penetracao_service import average_approval as average_poder_approval
from app.services.poder_penetracao_service import count_pending_launches as count_poder_pending_launches
from app.services.poder_penetracao_service import count_reproved_points as count_poder_reproved_points
from app.services.poder_penetracao_service import list_weekly_launches as list_poder_weekly_launches
from app.services.pressao_filtros_service import STATUS_CONCLUIDO as PRESSAO_STATUS_CONCLUIDO
from app.services.pressao_filtros_service import STATUS_RASCUNHO as PRESSAO_STATUS_RASCUNHO
from app.services.pressao_filtros_service import count_pending_launches as count_pressao_pending_launches
from app.services.pressao_filtros_service import list_daily_launches as list_pressao_daily_launches
from app.services.rugosidade_service import STATUS_CONCLUIDO as RUGOSIDADE_STATUS_CONCLUIDO
from app.services.rugosidade_service import STATUS_RASCUNHO as RUGOSIDADE_STATUS_RASCUNHO
from app.services.rugosidade_service import average_filled_percentage as average_rugosidade_filled_percentage
from app.services.rugosidade_service import count_outlier_models as count_rugosidade_outlier_models
from app.services.rugosidade_service import count_pending_launches as count_rugosidade_pending_launches
from app.services.rugosidade_service import list_daily_launches as list_rugosidade_daily_launches
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
    espessura_pending: int
    pressao_pending: int
    tensao_pending: int

    @property
    def total_pending(self) -> int:
        return self.ed_pending + self.espessura_pending + self.pressao_pending + self.tensao_pending


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
    data_inicial: date
    data_final: date
    turno: str
    turno_options: list[Turno]

    @property
    def data_referencia(self) -> date:
        return self.data_final


@dataclass(frozen=True)
class PendingStatusMetric:
    label: str
    value: int
    tone: str
    helper: str


@dataclass(frozen=True)
class PendingListRow:
    data_referencia: date
    data_label: str
    modulo: str
    descricao: str
    responsavel: str
    turno: str
    status: str
    prazo: str
    status_tone: str
    detail_url: str
    edit_url: str
    setor: str = "-"


@dataclass(frozen=True)
class PendingListFilters:
    data_inicial: date
    data_final: date
    turno: str
    status: str
    responsavel: str
    modulo_setor: str
    turno_options: list[Turno]


@dataclass(frozen=True)
class PendingListSnapshot:
    filters: PendingListFilters
    status_metrics: list[PendingStatusMetric]
    rows: list[PendingListRow]
    status_options: list[tuple[str, str]]
    modulo_options: list[tuple[str, str]]


@dataclass(frozen=True)
class DashboardSnapshot:
    filters: DashboardFilters
    has_global_alert: bool
    global_alert_message: str | None
    alert_summaries: list[DashboardAlertSummary]
    metrics: list[DashboardMetric]
    pending_summary: list[PendingStatusMetric]
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
    data_inicial_value = (query_params.get("data_inicial") or "").strip()
    data_final_value = (query_params.get("data_final") or "").strip()
    data_legacy_value = (query_params.get("data_referencia") or query_params.get("data") or "").strip()
    turno = (query_params.get("turno") or "").strip()

    if not data_inicial_value and not data_final_value:
        base_date = date.today()
        if data_legacy_value:
            try:
                base_date = date.fromisoformat(data_legacy_value)
            except ValueError as error:
                raise DashboardValidationError("Data inválida para o dashboard.") from error
        data_inicial = base_date
        data_final = base_date
    else:
        try:
            data_inicial = date.fromisoformat(data_inicial_value) if data_inicial_value else date.today()
            data_final = date.fromisoformat(data_final_value) if data_final_value else data_inicial
        except ValueError as error:
            raise DashboardValidationError("Período inválido para o dashboard.") from error

    if data_inicial > data_final:
        raise DashboardValidationError("A data inicial não pode ser maior que a data final.")

    return DashboardFilters(
        data_inicial=data_inicial,
        data_final=data_final,
        turno=turno,
        turno_options=list_turno_options(session),
    )


def build_dashboard_snapshot(session: Session, filters: DashboardFilters) -> DashboardSnapshot:
    aspecto_launches = list_aspecto_daily_launches(session, filters.data_referencia, turno=filters.turno or None)
    ed_launches = list_ed_daily_launches(session, filters.data_referencia, turno=filters.turno or None)
    espessura_launches = list_espessura_daily_launches(session, filters.data_referencia, turno=filters.turno or None)
    poder_launches = list_poder_weekly_launches(session, filters.data_referencia)
    pressao_launches = list_pressao_daily_launches(session, filters.data_referencia, turno=filters.turno or None)
    rugosidade_launches = list_rugosidade_daily_launches(session, filters.data_referencia)
    tensao_launches = list_tensao_daily_launches(session, filters.data_referencia, turno=filters.turno or None)
    temperatura_launches = list_temperatura_daily_launches(session, filters.data_referencia)

    aspecto_pending = 0
    ed_pending = count_ed_pending_launches(session, filters.data_referencia, turno=filters.turno or None)
    espessura_pending = count_espessura_pending_launches(session, filters.data_referencia, turno=filters.turno or None)
    poder_pending = count_poder_pending_launches(session, filters.data_referencia)
    pressao_pending = count_pressao_pending_launches(session, filters.data_referencia, turno=filters.turno or None)
    rugosidade_pending = count_rugosidade_pending_launches(session, filters.data_referencia)
    tensao_pending = count_tensao_pending_launches(session, filters.data_referencia, turno=filters.turno or None)
    temperatura_pending = count_temperatura_pending_launches(session, filters.data_referencia)

    aspecto_alert_count = count_aspecto_daily_records(session, filters.data_referencia, turno=filters.turno or None)
    ed_alert_count = _count_ed_outlier_items(session, filters.data_referencia, turno=filters.turno or None)
    espessura_alert_count = count_espessura_daily_filled_points(session, filters.data_referencia, turno=filters.turno or None)
    poder_alert_count = count_poder_reproved_points(session, filters.data_referencia)
    pressao_alert_count = _count_pressao_alarm_filters(session, filters.data_referencia, turno=filters.turno or None)
    rugosidade_alert_count = count_rugosidade_outlier_models(session, filters.data_referencia)
    tensao_alert_count = count_tensao_outlier_zones(session, filters.data_referencia, turno=filters.turno or None)
    temperatura_alert_count = _count_temperatura_outlier_zones(session, filters.data_referencia)

    aspecto_alert_target = _get_aspecto_primary_alert_target(session, filters.data_referencia, turno=filters.turno or None)
    ed_alert_target = _get_ed_primary_alert_target(session, filters.data_referencia, turno=filters.turno or None)
    poder_alert_target = _get_poder_primary_alert_target(session, filters.data_referencia)
    pressao_alert_target = _get_pressao_primary_alert_target(session, filters.data_referencia, turno=filters.turno or None)
    rugosidade_alert_target = _get_rugosidade_primary_alert_target(session, filters.data_referencia)
    tensao_alert_target = _get_tensao_primary_alert_target(session, filters.data_referencia, turno=filters.turno or None)
    temperatura_alert_target = _get_temperatura_primary_alert_target(session, filters.data_referencia)

    module_cards = [
        _build_aspecto_module_card(aspecto_launches, aspecto_pending, aspecto_alert_count, aspecto_alert_target),
        _build_ed_module_card(ed_launches, ed_pending, ed_alert_count, ed_alert_target),
        _build_espessura_module_card(espessura_launches, espessura_pending, espessura_alert_count),
        _build_poder_module_card(
            poder_launches,
            poder_pending,
            poder_alert_count,
            average_poder_approval(session, filters.data_referencia),
            poder_alert_target,
        ),
        _build_pressao_module_card(pressao_launches, pressao_pending, pressao_alert_count, pressao_alert_target),
        _build_rugosidade_module_card(
            rugosidade_launches,
            rugosidade_pending,
            rugosidade_alert_count,
            average_rugosidade_filled_percentage(session, filters.data_referencia),
            rugosidade_alert_target,
        ),
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
    total_alerts = (
        aspecto_alert_count
        + ed_alert_count
        + poder_alert_count
        + pressao_alert_count
        + rugosidade_alert_count
        + tensao_alert_count
        + temperatura_alert_count
    )
    total_pending = (
        aspecto_pending
        + ed_pending
        + espessura_pending
        + poder_pending
        + pressao_pending
        + rugosidade_pending
        + tensao_pending
        + temperatura_pending
    )

    metrics = [
        DashboardMetric("Módulos OK", modules_ok, "frentes concluídas e sem desvio", tone="success"),
        DashboardMetric("Módulos com problema", modules_problem, "críticos ou com atenção pendente", tone="warning"),
        DashboardMetric("Total de alertas", total_alerts, "desvios ativos no dia filtrado", tone="danger"),
        DashboardMetric("Pendências", total_pending, "lançamentos ainda em rascunho", tone="warning"),
    ]
    pending_summary = _build_pending_status_summary(session, filters)

    alert_summaries = [
        _build_alert_summary(
            title="Aspecto",
            count=aspecto_alert_count,
            tone="danger",
            singular="registro de anomalia",
            plural="registros de anomalia",
            action_url=aspecto_alert_target["detail_url"] if aspecto_alert_target else "/aspecto",
        ),
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
            title="Poder de Penetração",
            count=poder_alert_count,
            tone="warning",
            singular="ponto reprovado",
            plural="pontos reprovados",
            action_url=poder_alert_target["detail_url"] if poder_alert_target else "/poder-penetracao",
        ),
        _build_alert_summary(
            title="Rugosidade",
            count=rugosidade_alert_count,
            tone="warning",
            singular="modelo fora do padrão",
            plural="modelos fora do padrão",
            action_url=rugosidade_alert_target["detail_url"] if rugosidade_alert_target else "/rugosidade",
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
            espessura_pending=count_espessura_pending_launches(
                session,
                filters.data_referencia,
                turno=_turno_value(turno) or None,
            ),
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
        pending_summary=pending_summary,
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


def _build_aspecto_module_card(
    aspecto_launches: list[AspectoLancamento],
    pending_launches: int,
    alert_count: int,
    alert_target: dict[str, str] | None,
) -> DashboardModuleCard:
    concluded_launches = len(aspecto_launches)
    priority_label = "OK"
    priority_tone = "success"
    priority_description = "Nenhuma anomalia de aspecto registrada no dia filtrado."
    quick_action_label = "Novo registro"
    quick_action_url = "/aspecto"
    quick_action_tone = "secondary"
    card_url = "/aspecto"
    if aspecto_launches:
        latest = aspecto_launches[0]
        card_url = f"/aspecto/{latest.id}"
        priority_label = "Crítico"
        priority_tone = "danger"
        priority_description = "Existem anomalias visuais registradas e prontas para análise posterior."
        quick_action_label = "Ver ocorrências"
        quick_action_url = alert_target["detail_url"] if alert_target else card_url
        quick_action_tone = "danger"

    return DashboardModuleCard(
        title="Aspecto",
        priority_label=priority_label,
        priority_tone=priority_tone,
        priority_description=priority_description,
        total_launches=len(aspecto_launches),
        concluded_launches=concluded_launches,
        pending_launches=pending_launches,
        alert_count=alert_count,
        alert_label="registro(s) de anomalia",
        quick_action_url=quick_action_url,
        quick_action_label=quick_action_label,
        quick_action_tone=quick_action_tone,
        history_url="/aspecto/historico",
        card_url=card_url,
    )


def _build_espessura_module_card(
    espessura_launches: list[EspessuraEDLancamento],
    pending_launches: int,
    filled_points: int,
) -> DashboardModuleCard:
    concluded_launches = sum(1 for row in espessura_launches if row.status == ESPESSURA_STATUS_CONCLUIDO)
    priority_label = "Não iniciado"
    priority_tone = "muted"
    priority_description = "Nenhum lançamento técnico encontrado para o filtro atual."
    quick_action_label = "Iniciar"
    quick_action_url = "/espessura-ed"
    quick_action_tone = "secondary"
    card_url = "/espessura-ed"
    if espessura_launches:
        latest = espessura_launches[0]
        card_url = f"/espessura-ed/lancamentos/{latest.id}"
        if pending_launches:
            draft = next((row for row in espessura_launches if row.status == ESPESSURA_STATUS_RASCUNHO), latest)
            priority_label = "Atenção"
            priority_tone = "warning"
            priority_description = "Existe medição de espessura em rascunho aguardando conclusão."
            quick_action_label = "Continuar"
            quick_action_url = f"/espessura-ed/lancamentos/{draft.id}/editar"
            quick_action_tone = "primary"
        else:
            priority_label = "OK"
            priority_tone = "success"
            priority_description = "Lançamento técnico concluído com pontos rastreados para análise futura."
            quick_action_label = "Visualizar"
            quick_action_url = card_url
            quick_action_tone = "secondary"

    return DashboardModuleCard(
        title="Espessura ED",
        priority_label=priority_label,
        priority_tone=priority_tone,
        priority_description=priority_description,
        total_launches=len(espessura_launches),
        concluded_launches=concluded_launches,
        pending_launches=pending_launches,
        alert_count=filled_points,
        alert_label="ponto(s) preenchidos",
        quick_action_url=quick_action_url,
        quick_action_label=quick_action_label,
        quick_action_tone=quick_action_tone,
        history_url="/espessura-ed/historico",
        card_url=card_url,
    )


def _build_poder_module_card(
    poder_launches: list[PoderPenetracaoLancamento],
    pending_launches: int,
    alert_count: int,
    approval_average: float,
    alert_target: dict[str, str] | None,
) -> DashboardModuleCard:
    concluded_launches = sum(1 for row in poder_launches if row.status == PODER_STATUS_CONCLUIDO)
    priority_label = "Não iniciado"
    priority_tone = "muted"
    priority_description = "Nenhum ensaio semanal encontrado para a semana da data filtrada."
    quick_action_label = "Iniciar"
    quick_action_url = "/poder-penetracao"
    quick_action_tone = "secondary"
    card_url = "/poder-penetracao"
    if poder_launches:
        latest = poder_launches[0]
        card_url = f"/poder-penetracao/lancamentos/{latest.id}"
        if alert_count:
            priority_label = "Crítico"
            priority_tone = "danger"
            priority_description = "Existem pontos reprovados no ensaio semanal e a aprovação precisa de ação."
            quick_action_label = "Ver problema"
            quick_action_url = alert_target["detail_url"] if alert_target else card_url
            quick_action_tone = "danger"
        elif pending_launches:
            draft = next((row for row in poder_launches if row.status == PODER_STATUS_RASCUNHO), latest)
            priority_label = "Atenção"
            priority_tone = "warning"
            priority_description = "Existe ensaio semanal em rascunho aguardando conclusão."
            quick_action_label = "Continuar"
            quick_action_url = f"/poder-penetracao/lancamentos/{draft.id}/editar"
            quick_action_tone = "primary"
        else:
            priority_label = "OK"
            priority_tone = "success"
            priority_description = f"Ensaio semanal concluído com média de {approval_average:.1f}% de aprovação."
            quick_action_label = "Visualizar"
            quick_action_url = card_url
            quick_action_tone = "secondary"

    return DashboardModuleCard(
        title="Poder de Penetração",
        priority_label=priority_label,
        priority_tone=priority_tone,
        priority_description=priority_description,
        total_launches=len(poder_launches),
        concluded_launches=concluded_launches,
        pending_launches=pending_launches,
        alert_count=alert_count,
        alert_label="ponto(s) reprovados",
        quick_action_url=quick_action_url,
        quick_action_label=quick_action_label,
        quick_action_tone=quick_action_tone,
        history_url="/poder-penetracao/historico",
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


def _build_rugosidade_module_card(
    rugosidade_launches: list[RugosidadeLancamento],
    pending_launches: int,
    alert_count: int,
    average_filled_percentage: float,
    alert_target: dict[str, str] | None,
) -> DashboardModuleCard:
    concluded_launches = sum(1 for row in rugosidade_launches if row.status == RUGOSIDADE_STATUS_CONCLUIDO)
    priority_label = "Não iniciado"
    priority_tone = "muted"
    priority_description = "Nenhuma matriz de rugosidade encontrada para a data filtrada."
    quick_action_label = "Iniciar"
    quick_action_url = "/rugosidade"
    quick_action_tone = "secondary"
    card_url = "/rugosidade"
    if rugosidade_launches:
        latest = rugosidade_launches[0]
        card_url = f"/rugosidade/lancamentos/{latest.id}"
        if alert_count:
            priority_label = "Crítico"
            priority_tone = "danger"
            priority_description = "Há modelos com rugosidade acima de 14 µin e a qualidade precisa de ação."
            quick_action_label = "Ver problema"
            quick_action_url = alert_target["detail_url"] if alert_target else card_url
            quick_action_tone = "danger"
        elif pending_launches:
            draft = next((row for row in rugosidade_launches if row.status == RUGOSIDADE_STATUS_RASCUNHO), latest)
            priority_label = "Atenção"
            priority_tone = "warning"
            priority_description = "Existe matriz de rugosidade em rascunho aguardando conclusão."
            quick_action_label = "Continuar"
            quick_action_url = f"/rugosidade/lancamentos/{draft.id}/editar"
            quick_action_tone = "primary"
        else:
            priority_label = "OK"
            priority_tone = "success"
            priority_description = f"Matriz concluída com média de {average_filled_percentage:.1f}% de preenchimento."
            quick_action_label = "Visualizar"
            quick_action_url = card_url
            quick_action_tone = "secondary"

    return DashboardModuleCard(
        title="Rugosidade",
        priority_label=priority_label,
        priority_tone=priority_tone,
        priority_description=priority_description,
        total_launches=len(rugosidade_launches),
        concluded_launches=concluded_launches,
        pending_launches=pending_launches,
        alert_count=alert_count,
        alert_label="modelo(s) fora do padrão",
        quick_action_url=quick_action_url,
        quick_action_label=quick_action_label,
        quick_action_tone=quick_action_tone,
        history_url="/rugosidade/historico",
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
    week_label = f"{filters.data_referencia.isocalendar()[0]}-S{filters.data_referencia.isocalendar()[1]:02d}"

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

    espessura_statement = (
        select(EspessuraEDLancamento, EspessuraEDItem)
        .join(EspessuraEDItem, EspessuraEDItem.lancamento_id == EspessuraEDLancamento.id)
        .where(EspessuraEDLancamento.data_referencia == filters.data_referencia)
        .where(EspessuraEDItem.valor_espessura.is_not(None))
        .order_by(EspessuraEDLancamento.updated_at.desc(), EspessuraEDItem.ponto_numero.asc())
    )
    if filters.turno:
        espessura_statement = espessura_statement.where(EspessuraEDLancamento.turno == filters.turno)
    for lancamento, item in session.execute(espessura_statement).all()[:12]:
        occurrences.append(
            (
                lancamento.updated_at,
                DashboardRecentLaunch(
                    module_title="Espessura ED",
                    occurrence_type="Medição técnica",
                    reference_label=f"Ponto {item.ponto_numero}",
                    value_label=f"{_format_float(item.valor_espessura)} µm",
                    context_label=f"Turno {lancamento.turno} · {lancamento.modelo}",
                    updated_label=_format_timestamp(lancamento.updated_at),
                    detail_url=f"/espessura-ed/lancamentos/{lancamento.id}",
                    tone="warning" if lancamento.status == ESPESSURA_STATUS_RASCUNHO else "danger",
                ),
            )
        )

    aspecto_statement = (
        select(AspectoLancamento, AspectoRegistro)
        .join(AspectoRegistro, AspectoRegistro.lancamento_id == AspectoLancamento.id)
        .where(AspectoLancamento.data_referencia == filters.data_referencia)
        .order_by(AspectoLancamento.updated_at.desc(), AspectoRegistro.id.desc())
    )
    if filters.turno:
        aspecto_statement = aspecto_statement.where(AspectoLancamento.turno == filters.turno)
    for lancamento, registro in session.execute(aspecto_statement).all():
        occurrences.append(
            (
                lancamento.updated_at,
                DashboardRecentLaunch(
                    module_title="Aspecto",
                    occurrence_type="Anomalia visual",
                    reference_label=f"CIS {registro.cis} · {registro.local}",
                    value_label=f"QTD {registro.quantidade} · {registro.anomalia}",
                    context_label=f"Turno {registro.turno} · {registro.modelo}",
                    updated_label=_format_timestamp(lancamento.updated_at),
                    detail_url=f"/aspecto/{lancamento.id}",
                    tone="danger",
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

    rugosidade_statement = (
        select(RugosidadeLancamento, RugosidadeItem)
        .join(RugosidadeItem, RugosidadeItem.lancamento_id == RugosidadeLancamento.id)
        .where(RugosidadeLancamento.data_referencia == filters.data_referencia)
        .where(RugosidadeItem.fora_padrao.is_(True))
        .order_by(RugosidadeLancamento.updated_at.desc(), RugosidadeItem.modelo_codigo.asc())
    )
    for lancamento, item in session.execute(rugosidade_statement).all():
        occurrences.append(
            (
                lancamento.updated_at,
                DashboardRecentLaunch(
                    module_title="Rugosidade",
                    occurrence_type="Modelo fora do padrão",
                    reference_label=f"Modelo {item.modelo_codigo}",
                    value_label=f"{_format_float(item.valor_rugosidade)} µin",
                    context_label=f"Seq. {lancamento.sequencia}",
                    updated_label=_format_timestamp(lancamento.updated_at),
                    detail_url=f"/rugosidade/lancamentos/{lancamento.id}",
                    tone="danger",
                ),
            )
        )

    poder_statement = (
        select(PoderPenetracaoLancamento, PoderPenetracaoItem)
        .join(PoderPenetracaoItem, PoderPenetracaoItem.lancamento_id == PoderPenetracaoLancamento.id)
        .where(PoderPenetracaoLancamento.semana_referencia == week_label)
        .where(PoderPenetracaoItem.aprovado.is_(False))
        .order_by(PoderPenetracaoLancamento.updated_at.desc(), PoderPenetracaoItem.ponto_numero.asc())
    )
    for lancamento, item in session.execute(poder_statement).all():
        occurrences.append(
            (
                lancamento.updated_at,
                DashboardRecentLaunch(
                    module_title="Poder de Penetração",
                    occurrence_type="Ponto reprovado",
                    reference_label=f"Ponto {item.ponto_numero}",
                    value_label=f"{_format_float(item.valor_medido)}",
                    context_label=f"{lancamento.modelo} · {lancamento.semana_referencia}",
                    updated_label=_format_timestamp(lancamento.updated_at),
                    detail_url=f"/poder-penetracao/lancamentos/{lancamento.id}",
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


def _get_aspecto_primary_alert_target(session: Session, target_date: date, turno: str | None = None) -> dict[str, str] | None:
    statement = (
        select(AspectoLancamento)
        .where(AspectoLancamento.data_referencia == target_date)
        .order_by(AspectoLancamento.updated_at.desc(), AspectoLancamento.id.desc())
    )
    if turno:
        statement = statement.where(AspectoLancamento.turno == turno)
    lancamento = session.scalars(statement).first()
    if lancamento is None:
        return None
    return {"detail_url": f"/aspecto/{lancamento.id}"}


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


def _get_poder_primary_alert_target(session: Session, target_date: date) -> dict[str, str] | None:
    week_label = f"{target_date.isocalendar()[0]}-S{target_date.isocalendar()[1]:02d}"
    statement = (
        select(PoderPenetracaoLancamento)
        .where(PoderPenetracaoLancamento.semana_referencia == week_label)
        .where(PoderPenetracaoLancamento.total_reprovados > 0)
        .order_by(PoderPenetracaoLancamento.updated_at.desc(), PoderPenetracaoLancamento.id.desc())
    )
    lancamento = session.scalars(statement).first()
    if lancamento is None:
        return None
    return {"detail_url": f"/poder-penetracao/lancamentos/{lancamento.id}"}


def _get_rugosidade_primary_alert_target(session: Session, target_date: date) -> dict[str, str] | None:
    statement = (
        select(RugosidadeLancamento)
        .where(RugosidadeLancamento.data_referencia == target_date)
        .where(RugosidadeLancamento.total_modelos_fora_padrao > 0)
        .order_by(RugosidadeLancamento.updated_at.desc(), RugosidadeLancamento.id.desc())
    )
    lancamento = session.scalars(statement).first()
    if lancamento is None:
        return None
    return {"detail_url": f"/rugosidade/lancamentos/{lancamento.id}"}


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


def _build_pending_status_summary(session: Session, filters: DashboardFilters) -> list[PendingStatusMetric]:
    abertas = _count_pending_open(session, filters.data_inicial, filters.data_final, filters.turno or None)
    concluidas = _count_pending_concluded(session, filters.data_inicial, filters.data_final, filters.turno or None)
    em_andamento = 0
    vencidas = 0
    return [
        PendingStatusMetric("Pendências abertas", abertas, "warning", "lançamentos em rascunho no período"),
        PendingStatusMetric("Em andamento", em_andamento, "primary", "aguardando status intermediário dedicado"),
        PendingStatusMetric("Vencidas", vencidas, "danger", "aguardando integração de prazo/SLA"),
        PendingStatusMetric("Concluídas no período", concluidas, "success", "lançamentos finalizados no período"),
    ]


def parse_pending_filters(query_params, session: Session) -> PendingListFilters:
    data_inicial_value = (query_params.get("data_inicial") or "").strip()
    data_final_value = (query_params.get("data_final") or "").strip()
    turno = (query_params.get("turno") or "").strip()
    status = (query_params.get("status") or "").strip().lower()
    responsavel = (query_params.get("responsavel") or "").strip()
    modulo_setor = (query_params.get("modulo_setor") or "").strip()

    try:
        data_inicial = date.fromisoformat(data_inicial_value) if data_inicial_value else date.today()
        data_final = date.fromisoformat(data_final_value) if data_final_value else data_inicial
    except ValueError as error:
        raise DashboardValidationError("Período inválido para pendências.") from error

    if data_inicial > data_final:
        raise DashboardValidationError("A data inicial não pode ser maior que a data final.")

    status_allowed = {"", "aberta", "em_andamento", "concluida", "vencida"}
    if status not in status_allowed:
        raise DashboardValidationError("Status inválido para pendências.")

    return PendingListFilters(
        data_inicial=data_inicial,
        data_final=data_final,
        turno=turno,
        status=status,
        responsavel=responsavel,
        modulo_setor=modulo_setor,
        turno_options=list_turno_options(session),
    )


def build_pending_list_snapshot(session: Session, filters: PendingListFilters) -> PendingListSnapshot:
    rows: list[PendingListRow] = []
    rows.extend(_collect_ed_pending_rows(session, filters))
    rows.extend(_collect_espessura_pending_rows(session, filters))
    rows.extend(_collect_pressao_pending_rows(session, filters))
    rows.extend(_collect_tensao_pending_rows(session, filters))
    rows.extend(_collect_poder_pending_rows(session, filters))
    rows.extend(_collect_rugosidade_pending_rows(session, filters))
    rows.extend(_collect_temperatura_pending_rows(session, filters))

    rows = [row for row in rows if _row_matches_pending_filters(row, filters)]
    rows.sort(key=lambda row: row.data_referencia, reverse=True)

    status_metrics = _build_pending_status_summary(
        session,
        DashboardFilters(
            data_inicial=filters.data_inicial,
            data_final=filters.data_final,
            turno=filters.turno,
            turno_options=filters.turno_options,
        ),
    )
    return PendingListSnapshot(
        filters=filters,
        status_metrics=status_metrics,
        rows=rows,
        status_options=[
            ("", "Todos os status"),
            ("aberta", "Aberta"),
            ("em_andamento", "Em andamento"),
            ("concluida", "Concluída"),
            ("vencida", "Vencida"),
        ],
        modulo_options=[
            ("", "Todos os módulos/setores"),
            ("ed", "ED"),
            ("espessura-ed", "Espessura ED"),
            ("pressao-filtros-ed", "Pressão dos Filtros ED"),
            ("tensao-retificadores-ed", "Tensão dos Retificadores ED"),
            ("poder-penetracao", "Poder de Penetração"),
            ("rugosidade", "Rugosidade"),
            ("temperatura-forno-ed", "Temperatura Forno ED"),
        ],
    )


def _collect_ed_pending_rows(session: Session, filters: PendingListFilters) -> list[PendingListRow]:
    statement = (
        select(EDLancamento)
        .where(EDLancamento.data_referencia >= filters.data_inicial)
        .where(EDLancamento.data_referencia <= filters.data_final)
        .order_by(EDLancamento.data_referencia.desc(), EDLancamento.updated_at.desc())
    )
    if filters.turno:
        statement = statement.where(EDLancamento.turno == filters.turno)
    statement = _apply_status_filter(statement, EDLancamento.status, filters.status)
    return [
        PendingListRow(
            data_referencia=row.data_referencia,
            data_label=row.data_referencia.strftime("%d/%m/%Y"),
            modulo="ED",
            descricao=f"Checklist operacional · {row.setor}",
            responsavel=row.responsavel_nome,
            turno=row.turno,
            status=_map_pending_status(row.status),
            prazo="A definir",
            status_tone=_map_pending_tone(row.status),
            detail_url=f"/ed/lancamentos/{row.id}",
            edit_url=f"/ed/lancamentos/{row.id}/editar",
            setor=row.setor,
        )
        for row in session.scalars(statement).all()
    ]


def _collect_espessura_pending_rows(session: Session, filters: PendingListFilters) -> list[PendingListRow]:
    statement = (
        select(EspessuraEDLancamento)
        .where(EspessuraEDLancamento.data_referencia >= filters.data_inicial)
        .where(EspessuraEDLancamento.data_referencia <= filters.data_final)
        .order_by(EspessuraEDLancamento.data_referencia.desc(), EspessuraEDLancamento.updated_at.desc())
    )
    if filters.turno:
        statement = statement.where(EspessuraEDLancamento.turno == filters.turno)
    statement = _apply_status_filter(statement, EspessuraEDLancamento.status, filters.status)
    return [
        PendingListRow(
            data_referencia=row.data_referencia,
            data_label=row.data_referencia.strftime("%d/%m/%Y"),
            modulo="Espessura ED",
            descricao=f"Medições por modelo · {row.modelo}",
            responsavel=row.responsavel_nome,
            turno=row.turno,
            status=_map_pending_status(row.status),
            prazo="A definir",
            status_tone=_map_pending_tone(row.status),
            detail_url=f"/espessura-ed/lancamentos/{row.id}",
            edit_url=f"/espessura-ed/lancamentos/{row.id}/editar",
        )
        for row in session.scalars(statement).all()
    ]


def _collect_pressao_pending_rows(session: Session, filters: PendingListFilters) -> list[PendingListRow]:
    statement = (
        select(PressaoFiltrosLancamento)
        .where(PressaoFiltrosLancamento.data_referencia >= filters.data_inicial)
        .where(PressaoFiltrosLancamento.data_referencia <= filters.data_final)
        .order_by(PressaoFiltrosLancamento.data_referencia.desc(), PressaoFiltrosLancamento.updated_at.desc())
    )
    if filters.turno:
        statement = statement.where(PressaoFiltrosLancamento.turno == filters.turno)
    statement = _apply_status_filter(statement, PressaoFiltrosLancamento.status, filters.status)
    return [
        PendingListRow(
            data_referencia=row.data_referencia,
            data_label=row.data_referencia.strftime("%d/%m/%Y"),
            modulo="Pressão dos Filtros ED",
            descricao="Leitura dos 24 filtros de pressão",
            responsavel=row.responsavel_nome,
            turno=row.turno,
            status=_map_pending_status(row.status),
            prazo="A definir",
            status_tone=_map_pending_tone(row.status),
            detail_url=f"/pressao-filtros-ed/lancamentos/{row.id}",
            edit_url=f"/pressao-filtros-ed/lancamentos/{row.id}/editar",
        )
        for row in session.scalars(statement).all()
    ]


def _collect_tensao_pending_rows(session: Session, filters: PendingListFilters) -> list[PendingListRow]:
    statement = (
        select(TensaoRetificadoresLancamento)
        .where(TensaoRetificadoresLancamento.data_referencia >= filters.data_inicial)
        .where(TensaoRetificadoresLancamento.data_referencia <= filters.data_final)
        .order_by(TensaoRetificadoresLancamento.data_referencia.desc(), TensaoRetificadoresLancamento.updated_at.desc())
    )
    if filters.turno:
        statement = statement.where(TensaoRetificadoresLancamento.turno == filters.turno)
    statement = _apply_status_filter(statement, TensaoRetificadoresLancamento.status, filters.status)
    return [
        PendingListRow(
            data_referencia=row.data_referencia,
            data_label=row.data_referencia.strftime("%d/%m/%Y"),
            modulo="Tensão dos Retificadores ED",
            descricao=f"Leitura por modelo · {row.modelo}",
            responsavel=row.responsavel_nome,
            turno=row.turno,
            status=_map_pending_status(row.status),
            prazo="A definir",
            status_tone=_map_pending_tone(row.status),
            detail_url=f"/tensao-retificadores-ed/lancamentos/{row.id}",
            edit_url=f"/tensao-retificadores-ed/lancamentos/{row.id}/editar",
        )
        for row in session.scalars(statement).all()
    ]


def _collect_poder_pending_rows(session: Session, filters: PendingListFilters) -> list[PendingListRow]:
    statement = (
        select(PoderPenetracaoLancamento)
        .where(PoderPenetracaoLancamento.data_referencia >= filters.data_inicial)
        .where(PoderPenetracaoLancamento.data_referencia <= filters.data_final)
        .order_by(PoderPenetracaoLancamento.data_referencia.desc(), PoderPenetracaoLancamento.id.desc())
    )
    statement = _apply_status_filter(statement, PoderPenetracaoLancamento.status, filters.status)
    return [
        PendingListRow(
            data_referencia=row.data_referencia,
            data_label=row.data_referencia.strftime("%d/%m/%Y"),
            modulo="Poder de Penetração",
            descricao=f"Controle semanal · {row.modelo}",
            responsavel=row.responsavel_nome,
            turno="-",
            status=_map_pending_status(row.status),
            prazo="A definir",
            status_tone=_map_pending_tone(row.status),
            detail_url=f"/poder-penetracao/lancamentos/{row.id}",
            edit_url=f"/poder-penetracao/lancamentos/{row.id}/editar",
        )
        for row in session.scalars(statement).all()
    ]


def _collect_rugosidade_pending_rows(session: Session, filters: PendingListFilters) -> list[PendingListRow]:
    statement = (
        select(RugosidadeLancamento)
        .where(RugosidadeLancamento.data_referencia >= filters.data_inicial)
        .where(RugosidadeLancamento.data_referencia <= filters.data_final)
        .order_by(RugosidadeLancamento.data_referencia.desc(), RugosidadeLancamento.id.desc())
    )
    statement = _apply_status_filter(statement, RugosidadeLancamento.status, filters.status)
    return [
        PendingListRow(
            data_referencia=row.data_referencia,
            data_label=row.data_referencia.strftime("%d/%m/%Y"),
            modulo="Rugosidade",
            descricao=f"Matriz por sequência · {row.sequencia}",
            responsavel=row.responsavel_nome,
            turno="-",
            status=_map_pending_status(row.status),
            prazo="A definir",
            status_tone=_map_pending_tone(row.status),
            detail_url=f"/rugosidade/lancamentos/{row.id}",
            edit_url=f"/rugosidade/lancamentos/{row.id}/editar",
        )
        for row in session.scalars(statement).all()
    ]


def _collect_temperatura_pending_rows(session: Session, filters: PendingListFilters) -> list[PendingListRow]:
    statement = (
        select(TemperaturaFornoLancamento)
        .where(TemperaturaFornoLancamento.data_referencia >= filters.data_inicial)
        .where(TemperaturaFornoLancamento.data_referencia <= filters.data_final)
        .order_by(TemperaturaFornoLancamento.data_referencia.desc(), TemperaturaFornoLancamento.updated_at.desc())
    )
    statement = _apply_status_filter(statement, TemperaturaFornoLancamento.status, filters.status)
    return [
        PendingListRow(
            data_referencia=row.data_referencia,
            data_label=row.data_referencia.strftime("%d/%m/%Y"),
            modulo="Temperatura Forno ED",
            descricao="Leitura térmica das 12 zonas",
            responsavel=row.responsavel_nome,
            turno="-",
            status=_map_pending_status(row.status),
            prazo="A definir",
            status_tone=_map_pending_tone(row.status),
            detail_url=f"/temperatura-forno-ed/lancamentos/{row.id}",
            edit_url=f"/temperatura-forno-ed/lancamentos/{row.id}/editar",
        )
        for row in session.scalars(statement).all()
    ]


def _apply_status_filter(statement, status_column, status: str):
    if status == "aberta":
        return statement.where(status_column == "rascunho")
    if status == "concluida":
        return statement.where(status_column == "concluido")
    if status in {"em_andamento", "vencida"}:
        return statement.where(status_column == "__sem_registro__")
    return statement


def _row_matches_pending_filters(row: PendingListRow, filters: PendingListFilters) -> bool:
    if filters.turno and row.turno != filters.turno:
        return False
    if filters.status and filters.status not in {"em_andamento", "vencida"}:
        if filters.status == "aberta" and row.status != "Aberta":
            return False
        if filters.status == "concluida" and row.status != "Concluída":
            return False
    if filters.status in {"em_andamento", "vencida"}:
        return False
    if filters.responsavel and filters.responsavel.lower() not in row.responsavel.lower():
        return False
    if filters.modulo_setor:
        filter_value = filters.modulo_setor.lower()
        if filter_value not in row.modulo.lower() and filter_value not in row.setor.lower():
            return False
    return True


def _map_pending_status(status: str) -> str:
    if status == "concluido":
        return "Concluída"
    return "Aberta"


def _map_pending_tone(status: str) -> str:
    if status == "concluido":
        return "success"
    return "warning"


def _count_pending_open(session: Session, start_date: date, end_date: date, turno: str | None) -> int:
    return (
        _count_status_in_period(session, EDLancamento, "data_referencia", "status", "rascunho", turno, "turno", start_date, end_date)
        + _count_status_in_period(
            session,
            EspessuraEDLancamento,
            "data_referencia",
            "status",
            "rascunho",
            turno,
            "turno",
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            PressaoFiltrosLancamento,
            "data_referencia",
            "status",
            "rascunho",
            turno,
            "turno",
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            TensaoRetificadoresLancamento,
            "data_referencia",
            "status",
            "rascunho",
            turno,
            "turno",
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            PoderPenetracaoLancamento,
            "data_referencia",
            "status",
            "rascunho",
            None,
            None,
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            RugosidadeLancamento,
            "data_referencia",
            "status",
            "rascunho",
            None,
            None,
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            TemperaturaFornoLancamento,
            "data_referencia",
            "status",
            "rascunho",
            None,
            None,
            start_date,
            end_date,
        )
    )


def _count_pending_concluded(session: Session, start_date: date, end_date: date, turno: str | None) -> int:
    return (
        _count_status_in_period(session, EDLancamento, "data_referencia", "status", "concluido", turno, "turno", start_date, end_date)
        + _count_status_in_period(
            session,
            EspessuraEDLancamento,
            "data_referencia",
            "status",
            "concluido",
            turno,
            "turno",
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            PressaoFiltrosLancamento,
            "data_referencia",
            "status",
            "concluido",
            turno,
            "turno",
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            TensaoRetificadoresLancamento,
            "data_referencia",
            "status",
            "concluido",
            turno,
            "turno",
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            PoderPenetracaoLancamento,
            "data_referencia",
            "status",
            "concluido",
            None,
            None,
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            RugosidadeLancamento,
            "data_referencia",
            "status",
            "concluido",
            None,
            None,
            start_date,
            end_date,
        )
        + _count_status_in_period(
            session,
            TemperaturaFornoLancamento,
            "data_referencia",
            "status",
            "concluido",
            None,
            None,
            start_date,
            end_date,
        )
    )


def _count_status_in_period(
    session: Session,
    model,
    date_field: str,
    status_field: str,
    status_value: str,
    turno: str | None,
    turno_field: str | None,
    start_date: date,
    end_date: date,
) -> int:
    date_column = getattr(model, date_field)
    status_column = getattr(model, status_field)
    statement = (
        select(func.count(model.id))
        .where(date_column >= start_date)
        .where(date_column <= end_date)
        .where(status_column == status_value)
    )
    if turno and turno_field and hasattr(model, turno_field):
        statement = statement.where(getattr(model, turno_field) == turno)
    return int(session.scalar(statement) or 0)


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
