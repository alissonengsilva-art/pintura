from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Callable

from sqlalchemy import Select, case, inspect, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Modelo,
    OperationalModuleRecord,
    OperationalModuleSectorEntry,
    OperationalModuleSectorRecord,
    Responsavel,
    Turno,
)
from app.services import aspecto_service
from app.services import ed_service
from app.services import espessura_ed_service
from app.services import poder_penetracao_service
from app.services import pressao_filtros_service
from app.services import rugosidade_service
from app.services import temperatura_forno_service
from app.services import tensao_retificadores_service

SETOR_PTED = "PTED"
SETOR_LAB = "LABORATORIO"
SETOR_SEQUENCE = [SETOR_PTED, SETOR_LAB]
SETOR_LABELS = {
    SETOR_PTED: "PTED",
    SETOR_LAB: "Laboratório",
}
SETOR_SOURCE_LABELS = {
    SETOR_PTED: "PT/ED",
    SETOR_LAB: "Laboratório",
}

SETOR_STATUS_NAO_INICIADO = "NAO_INICIADO"
SETOR_STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"
SETOR_STATUS_CONCLUIDO = "CONCLUIDO"

MODULE_STATUS_NAO_INICIADO = "NAO_INICIADO"
MODULE_STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"
MODULE_STATUS_PARCIAL = "PARCIAL"
MODULE_STATUS_CONCLUIDO = "CONCLUIDO"

STATUS_LABELS = {
    SETOR_STATUS_NAO_INICIADO: "Não iniciado",
    SETOR_STATUS_EM_ANDAMENTO: "Em andamento",
    SETOR_STATUS_CONCLUIDO: "Concluído",
    MODULE_STATUS_NAO_INICIADO: "Não iniciado",
    MODULE_STATUS_EM_ANDAMENTO: "Em andamento",
    MODULE_STATUS_PARCIAL: "Parcial",
    MODULE_STATUS_CONCLUIDO: "Concluído",
}


@dataclass(frozen=True)
class ContextField:
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    options_key: str | None = None
    placeholder: str | None = None


@dataclass(frozen=True)
class TableColumn:
    key: str
    label: str
    kind: str = "text"
    input_type: str = "text"
    placeholder: str | None = None
    width: str | None = None


@dataclass(frozen=True)
class ModuleConfig:
    code: str
    slug: str
    title: str
    description: str
    history_title: str
    report_title: str
    context_fields: tuple[ContextField, ...]
    columns: tuple[TableColumn, ...]
    default_rows_builder: Callable[[Session, dict[str, Any], str], list[dict[str, Any]]]
    parse_rows: Callable[[Session, dict[str, Any], str, Any], tuple[list[dict[str, Any]], dict[str, Any]]]
    legacy_history_builder: Callable[[Session], list[dict[str, Any]]]
    legacy_detail_loader: Callable[[Session, int], Any | None]
    legacy_detail_template: str
    supports_turno: bool = False


class OperationalModuleValidationError(ValueError):
    pass


MISSING_SCHEMA_MESSAGE = (
    "A nova estrutura operacional ainda nao foi instalada no banco. "
    "Execute 'alembic upgrade head' antes de usar o fluxo setorial."
)


def operational_schema_available(session: Session) -> bool:
    bind = session.get_bind()
    inspector = inspect(bind)
    required_tables = (
        "operational_module_records",
        "operational_module_sector_records",
        "operational_module_sector_entries",
    )
    return all(inspector.has_table(table_name) for table_name in required_tables)


def list_shared_options(session: Session) -> dict[str, list[Any]]:
    responsaveis = list(
        session.scalars(select(Responsavel).where(Responsavel.ativo.is_(True)).order_by(Responsavel.nome)).all()
    )
    turnos = list(
        session.scalars(
            select(Turno)
            .where(Turno.ativo.is_(True))
            .order_by(case((Turno.codigo.in_(["1", "2", "3"]), 0), else_=1), Turno.codigo, Turno.nome)
        ).all()
    )
    modelos = list(
        session.scalars(select(Modelo).where(Modelo.ativo.is_(True)).order_by(Modelo.nome)).all()
    )
    return {
        "responsaveis": responsaveis,
        "turnos": turnos,
        "modelos": modelos,
        "tipo_dia": [{"value": value, "label": label} for value, label in ed_service.TIPO_DIA_OPTIONS],
        "sequencias_rugosidade": [
            {"value": "1Âª coleta", "label": "1Âª coleta"},
            {"value": "2Âª coleta", "label": "2Âª coleta"},
            {"value": "3Âª coleta", "label": "3Âª coleta"},
        ],
    }


def resolve_context_defaults(config: ModuleConfig, session: Session, source: Any | None = None) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    source = source or {}
    options = list_shared_options(session)
    values: dict[str, Any] = {}
    for field in config.context_fields:
        raw = ""
        if hasattr(source, "get"):
            raw = source.get(field.name, "")
        if not raw:
            if field.name == "data_referencia":
                raw = date.today().isoformat()
            elif field.name == "semana_referencia":
                raw = poder_penetracao_service.default_week_label(date.today())
            elif field.options_key:
                raw = _first_option_value(options.get(field.options_key, [])) or ""
        values[field.name] = raw
    return values, options


def build_context_from_source(config: ModuleConfig, source: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    missing: list[str] = []
    for field in config.context_fields:
        raw = ""
        if hasattr(source, "get"):
            raw = source.get(field.name, "")
        raw = str(raw or "").strip()
        if field.required and not raw:
            missing.append(field.label.lower())
        values[field.name] = raw
    if missing:
        raise OperationalModuleValidationError(f"Preencha: {', '.join(missing)}.")

    try:
        values["data_referencia"] = date.fromisoformat(str(values["data_referencia"]))
    except ValueError as error:
        raise OperationalModuleValidationError("Data inválida para o contexto.") from error

    return values


def context_to_form_values(config: ModuleConfig, context: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in config.context_fields:
        value = context.get(field.name)
        if isinstance(value, date):
            values[field.name] = value.isoformat()
        else:
            values[field.name] = "" if value is None else str(value)
    return values


def context_label(config: ModuleConfig, context_data: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in config.context_fields:
        value = context_data.get(field.name)
        if not value:
            continue
        if field.name == "data_referencia":
            if isinstance(value, str):
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    pass
            if isinstance(value, date):
                parts.append(value.strftime("%d/%m/%Y"))
                continue
        parts.append(f"{field.label}: {value}")
    return " Â· ".join(parts)


def build_context_key(config: ModuleConfig, context: dict[str, Any]) -> str:
    parts = [config.code]
    for field in config.context_fields:
        value = context.get(field.name)
        normalized = value.isoformat() if isinstance(value, date) else str(value or "").strip().lower()
        parts.append(f"{field.name}={normalized}")
    return "|".join(parts)


def get_or_create_master(session: Session, config: ModuleConfig, context: dict[str, Any]) -> OperationalModuleRecord:
    if not operational_schema_available(session):
        raise OperationalModuleValidationError(MISSING_SCHEMA_MESSAGE)
    key = build_context_key(config, context)
    statement = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores).joinedload(OperationalModuleSectorRecord.respostas))
        .where(OperationalModuleRecord.module_code == config.code)
        .where(OperationalModuleRecord.context_key == key)
    )
    master = session.scalars(statement).unique().first()
    if master is None:
        now = datetime.now(UTC).replace(tzinfo=None)
        master = OperationalModuleRecord(
            module_code=config.code,
            data_referencia=context["data_referencia"],
            turno=str(context.get("turno") or "") or None,
            context_key=key,
            context_data=_serialize_context(config, context),
            status_geral=MODULE_STATUS_NAO_INICIADO,
            created_at=now,
            updated_at=now,
        )
        session.add(master)
        session.flush()
        for setor_tipo in SETOR_SEQUENCE:
            session.add(
                OperationalModuleSectorRecord(
                    registro_mestre_id=master.id,
                    setor_tipo=setor_tipo,
                    status_setor=SETOR_STATUS_NAO_INICIADO,
                    metricas={},
                )
            )
        session.flush()
        master = session.scalars(statement).unique().first()
    else:
        master.data_referencia = context["data_referencia"]
        master.turno = str(context.get("turno") or "") or None
        master.context_data = _serialize_context(config, context)
    return master


def get_master(session: Session, record_id: int) -> OperationalModuleRecord | None:
    if not operational_schema_available(session):
        return None
    statement = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores).joinedload(OperationalModuleSectorRecord.respostas))
        .where(OperationalModuleRecord.id == record_id)
    )
    return session.scalars(statement).unique().first()


def get_master_by_context(session: Session, config: ModuleConfig, context: dict[str, Any]) -> OperationalModuleRecord | None:
    if not operational_schema_available(session):
        return None
    statement = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores).joinedload(OperationalModuleSectorRecord.respostas))
        .where(OperationalModuleRecord.module_code == config.code)
        .where(OperationalModuleRecord.context_key == build_context_key(config, context))
    )
    return session.scalars(statement).unique().first()


def build_sector_view(
    session: Session,
    config: ModuleConfig,
    context: dict[str, Any],
    master: OperationalModuleRecord | None,
    setor_tipo: str,
) -> dict[str, Any]:
    sector_record = _find_sector(master, setor_tipo) if master else None
    entry_map = _entry_map(sector_record) if sector_record else {}
    rows = config.default_rows_builder(session, context, setor_tipo)
    hydrated_rows = _hydrate_rows(rows, entry_map)
    summary = _summarize_rows(hydrated_rows)
    return {
        "setor_tipo": setor_tipo,
        "setor_label": SETOR_LABELS[setor_tipo],
        "responsavel_nome": sector_record.responsavel_nome if sector_record and sector_record.responsavel_nome else "",
        "observacoes_setor": sector_record.observacoes_setor if sector_record and sector_record.observacoes_setor else "",
        "status_setor": sector_record.status_setor if sector_record else SETOR_STATUS_NAO_INICIADO,
        "status_label": STATUS_LABELS[sector_record.status_setor] if sector_record else STATUS_LABELS[SETOR_STATUS_NAO_INICIADO],
        "rows": hydrated_rows,
        "summary": summary,
        "metricas": sector_record.metricas if sector_record else {},
    }


def save_sector(
    session: Session,
    config: ModuleConfig,
    context: dict[str, Any],
    setor_tipo: str,
    form_data: Any,
    action: str,
) -> OperationalModuleRecord:
    if not operational_schema_available(session):
        raise OperationalModuleValidationError(MISSING_SCHEMA_MESSAGE)
    master = get_or_create_master(session, config, context)
    sector = _find_sector(master, setor_tipo)
    if sector is None:
        raise OperationalModuleValidationError("Setor não encontrado para o registro mestre.")

    responsavel_nome = (form_data.get(f"responsavel_nome_{setor_tipo}") or "").strip()
    if not responsavel_nome:
        raise OperationalModuleValidationError(f"Informe o responsável do setor {SETOR_LABELS[setor_tipo]}.")
    observacoes_setor = (form_data.get(f"observacoes_setor_{setor_tipo}") or "").strip() or None

    rows, metricas = config.parse_rows(session, context, setor_tipo, form_data)
    sector.responsavel_nome = responsavel_nome
    sector.observacoes_setor = observacoes_setor
    now = datetime.now(UTC).replace(tzinfo=None)
    if sector.iniciado_em is None:
        sector.iniciado_em = now
    sector.atualizado_em = now
    sector.status_setor = SETOR_STATUS_CONCLUIDO if action == "concluir" else SETOR_STATUS_EM_ANDAMENTO
    sector.concluido_em = now if sector.status_setor == SETOR_STATUS_CONCLUIDO else None
    sector.metricas = metricas
    sector.respostas.clear()
    for index, row in enumerate(rows, start=1):
        value_number = row.get("value_number")
        sector.respostas.append(
            OperationalModuleSectorEntry(
                referencia=str(row.get("reference") or index),
                ordem=int(row.get("order") or index),
                valor_texto=None if row.get("value") is None else str(row.get("value")),
                valor_numero=float(value_number) if isinstance(value_number, (int, float)) else None,
                observacao=None if row.get("row_observation") is None else str(row.get("row_observation")),
                fora_padrao=row.get("flag"),
                dados=row,
                created_at=now,
                updated_at=now,
            )
        )

    master.status_geral = _calculate_module_status(master.setores)
    master.updated_at = now
    session.commit()
    refreshed = get_master(session, master.id)
    if refreshed is None:
        raise OperationalModuleValidationError("Falha ao recarregar registro salvo.")
    return refreshed


def list_module_history(session: Session, config: ModuleConfig) -> list[OperationalModuleRecord]:
    if not operational_schema_available(session):
        return []
    statement: Select[tuple[OperationalModuleRecord]] = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores))
        .where(OperationalModuleRecord.module_code == config.code)
        .order_by(OperationalModuleRecord.data_referencia.desc(), OperationalModuleRecord.updated_at.desc())
    )
    return list(session.scalars(statement).unique().all())


def build_history_row(config: ModuleConfig, master: OperationalModuleRecord) -> dict[str, Any]:
    pted = _find_sector(master, SETOR_PTED)
    lab = _find_sector(master, SETOR_LAB)
    total_flags = sum(int((sector.metricas or {}).get("flag_count", 0)) for sector in master.setores)
    return {
        "id": master.id,
        "context_label": context_label(config, master.context_data),
        "data_label": master.data_referencia.strftime("%d/%m/%Y"),
        "status_geral": master.status_geral,
        "status_geral_label": STATUS_LABELS[master.status_geral],
        "status_pted": pted.status_setor if pted else SETOR_STATUS_NAO_INICIADO,
        "status_pted_label": STATUS_LABELS[pted.status_setor] if pted else STATUS_LABELS[SETOR_STATUS_NAO_INICIADO],
        "status_lab": lab.status_setor if lab else SETOR_STATUS_NAO_INICIADO,
        "status_lab_label": STATUS_LABELS[lab.status_setor] if lab else STATUS_LABELS[SETOR_STATUS_NAO_INICIADO],
        "responsavel_pted": pted.responsavel_nome if pted and pted.responsavel_nome else "-",
        "responsavel_lab": lab.responsavel_nome if lab and lab.responsavel_nome else "-",
        "desvios": total_flags,
        "detail_url": f"/{config.slug}/registros/{master.id}",
        "report_url": f"/{config.slug}/registros/{master.id}/relatorio",
        "report_pted_url": f"/{config.slug}/registros/{master.id}/relatorio?setor=PTED",
        "report_lab_url": f"/{config.slug}/registros/{master.id}/relatorio?setor=LABORATORIO",
        "sort_key": master.data_referencia.isoformat() + f"-{master.id:08d}",
    }


def build_history_rows(session: Session, config: ModuleConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for master in list_module_history(session, config):
        row = build_history_row(config, master)
        row["origin"] = "novo"
        rows.append(row)
    for legacy in config.legacy_history_builder(session):
        legacy["origin"] = "legado"
        rows.append(legacy)
    rows.sort(key=lambda item: item.get("sort_key"), reverse=True)
    return rows


def build_detail_context(
    session: Session,
    config: ModuleConfig,
    master: OperationalModuleRecord,
    *,
    report_setor: str | None = None,
) -> dict[str, Any]:
    if not operational_schema_available(session):
        raise OperationalModuleValidationError(MISSING_SCHEMA_MESSAGE)
    context = _deserialize_context(config, master.context_data)
    setor_views = [build_sector_view(session, config, context, master, setor) for setor in SETOR_SEQUENCE]
    if report_setor:
        setor_views = [view for view in setor_views if view["setor_tipo"] == report_setor]
    return {
        "master": master,
        "context_values": context_to_form_values(config, context),
        "context_label": context_label(config, master.context_data),
        "status_geral_label": STATUS_LABELS[master.status_geral],
        "setor_views": setor_views,
        "history_row": build_history_row(config, master),
    }


def build_dashboard_snapshot(session: Session, target_date: date, turno: str | None = None) -> dict[str, Any]:
    if not operational_schema_available(session):
        cards = []
        for config in MODULE_CONFIGS.values():
            cards.append(
                {
                    "title": config.title,
                    "url": f"/{config.slug}",
                    "history_url": f"/{config.slug}/historico",
                    "action_label": "Migrar banco",
                    "action_url": f"/{config.slug}",
                    "status_geral": "Estrutura pendente",
                    "status_pted": "-",
                    "status_lab": "-",
                    "responsavel_pted": "-",
                    "responsavel_lab": "-",
                    "desvios": 0,
                }
            )
        return {
            "cards": cards,
            "total_modulos": len(cards),
            "modulos_com_alerta": 0,
            "total_desvios": 0,
        }
    cards: list[dict[str, Any]] = []
    total_desvios = 0
    for config in MODULE_CONFIGS.values():
        statement = select(OperationalModuleRecord).options(joinedload(OperationalModuleRecord.setores)).where(
            OperationalModuleRecord.module_code == config.code,
            OperationalModuleRecord.data_referencia == target_date,
        )
        if turno and config.supports_turno:
            statement = statement.where(OperationalModuleRecord.turno == turno)
        records = list(session.scalars(statement).unique().all())
        total_desvios += sum(
            sum(int((sector.metricas or {}).get("flag_count", 0)) for sector in record.setores)
            for record in records
        )
        if records:
            latest = records[0]
            row = build_history_row(config, latest)
            action_label = "Visualizar" if latest.status_geral == MODULE_STATUS_CONCLUIDO else "Continuar"
            action_url = row["detail_url"]
        else:
            row = None
            action_label = "Iniciar"
            action_url = f"/{config.slug}"
        cards.append(
            {
                "title": config.title,
                "url": f"/{config.slug}",
                "history_url": f"/{config.slug}/historico",
                "action_label": action_label,
                "action_url": action_url,
                "status_geral": row["status_geral_label"] if row else STATUS_LABELS[MODULE_STATUS_NAO_INICIADO],
                "status_pted": row["status_pted_label"] if row else STATUS_LABELS[SETOR_STATUS_NAO_INICIADO],
                "status_lab": row["status_lab_label"] if row else STATUS_LABELS[SETOR_STATUS_NAO_INICIADO],
                "responsavel_pted": row["responsavel_pted"] if row else "-",
                "responsavel_lab": row["responsavel_lab"] if row else "-",
                "desvios": row["desvios"] if row else 0,
            }
        )
    return {
        "cards": cards,
        "total_modulos": len(cards),
        "modulos_com_alerta": sum(1 for card in cards if card["desvios"] > 0),
        "total_desvios": total_desvios,
    }


def _serialize_context(config: ModuleConfig, context: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in config.context_fields:
        value = context.get(field.name)
        values[field.name] = value.isoformat() if isinstance(value, date) else value
    return values


def _deserialize_context(config: ModuleConfig, raw: dict[str, Any]) -> dict[str, Any]:
    values = dict(raw)
    if "data_referencia" in values and isinstance(values["data_referencia"], str):
        values["data_referencia"] = date.fromisoformat(values["data_referencia"])
    return values


def _entry_map(sector_record: OperationalModuleSectorRecord | None) -> dict[str, dict[str, Any]]:
    if sector_record is None:
        return {}
    return {entry.referencia: dict(entry.dados or {}) for entry in sector_record.respostas}


def _hydrate_rows(rows: list[dict[str, Any]], stored: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for row in rows:
        current = dict(row)
        current.update(stored.get(str(row.get("reference")), {}))
        hydrated.append(current)
    return hydrated


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    preenchidos = sum(1 for row in rows if str(row.get("value") or "").strip())
    flags = sum(1 for row in rows if row.get("flag"))
    return {
        "total": total,
        "preenchidos": preenchidos,
        "flag_count": flags,
        "percentual": int(round((preenchidos / total) * 100)) if total else 0,
    }


def _find_sector(master: OperationalModuleRecord | None, setor_tipo: str) -> OperationalModuleSectorRecord | None:
    if master is None:
        return None
    for setor in master.setores:
        if setor.setor_tipo == setor_tipo:
            return setor
    return None


def _calculate_module_status(setores: list[OperationalModuleSectorRecord]) -> str:
    statuses = {setor.setor_tipo: setor.status_setor for setor in setores}
    if all(statuses.get(setor, SETOR_STATUS_NAO_INICIADO) == SETOR_STATUS_NAO_INICIADO for setor in SETOR_SEQUENCE):
        return MODULE_STATUS_NAO_INICIADO
    if all(statuses.get(setor) == SETOR_STATUS_CONCLUIDO for setor in SETOR_SEQUENCE):
        return MODULE_STATUS_CONCLUIDO
    if any(statuses.get(setor) == SETOR_STATUS_CONCLUIDO for setor in SETOR_SEQUENCE):
        return MODULE_STATUS_PARCIAL
    return MODULE_STATUS_EM_ANDAMENTO


def _first_option_value(options: list[Any]) -> str | None:
    if not options:
        return None
    first = options[0]
    if hasattr(first, "codigo"):
        return str(first.codigo)
    if hasattr(first, "nome"):
        return str(first.nome)
    if isinstance(first, dict):
        return str(first.get("value") or "")
    return str(first)


def _parse_decimal(raw_value: Any, message: str) -> float | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError as error:
        raise OperationalModuleValidationError(message.format(value=text)) from error


def _legacy_ed_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for item in ed_service.list_history(session):
        lancamento = item["lancamento"]
        rows.append(
            {
                "id": lancamento.id,
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} Â· Turno {lancamento.turno} Â· {lancamento.setor}",
                "data_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "status_geral": lancamento.status.upper(),
                "status_geral_label": lancamento.status.title(),
                "status_pted": SETOR_STATUS_NAO_INICIADO,
                "status_pted_label": "-",
                "status_lab": SETOR_STATUS_NAO_INICIADO,
                "status_lab_label": "-",
                "responsavel_pted": "-",
                "responsavel_lab": "-",
                "desvios": 0,
                "detail_url": f"/ed/legado/{lancamento.id}",
                "report_url": f"/ed/legado/{lancamento.id}",
                "report_pted_url": f"/ed/legado/{lancamento.id}",
                "report_lab_url": f"/ed/legado/{lancamento.id}",
                "sort_key": lancamento.data_referencia.isoformat() + f"-{lancamento.id:08d}",
            }
        )
    return rows


def _legacy_pressao_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for item in pressao_filtros_service.list_history(session):
        lancamento = item["lancamento"]
        rows.append(
            {
                "id": lancamento.id,
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} Â· Turno {lancamento.turno}",
                "data_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "status_geral": lancamento.status.upper(),
                "status_geral_label": lancamento.status.title(),
                "status_pted": SETOR_STATUS_NAO_INICIADO,
                "status_pted_label": "-",
                "status_lab": SETOR_STATUS_NAO_INICIADO,
                "status_lab_label": "-",
                "responsavel_pted": "-",
                "responsavel_lab": "-",
                "desvios": int(item.get("quantidade_alarmes") or 0),
                "detail_url": f"/pressao-filtros-ed/legado/{lancamento.id}",
                "report_url": f"/pressao-filtros-ed/legado/{lancamento.id}",
                "report_pted_url": f"/pressao-filtros-ed/legado/{lancamento.id}",
                "report_lab_url": f"/pressao-filtros-ed/legado/{lancamento.id}",
                "sort_key": lancamento.data_referencia.isoformat() + f"-{lancamento.id:08d}",
            }
        )
    return rows


def _legacy_temp_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for item in temperatura_forno_service.list_history(session):
        lancamento = item["lancamento"]
        rows.append(
            {
                "id": lancamento.id,
                "context_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "data_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "status_geral": lancamento.status.upper(),
                "status_geral_label": lancamento.status.title(),
                "status_pted": SETOR_STATUS_NAO_INICIADO,
                "status_pted_label": "-",
                "status_lab": SETOR_STATUS_NAO_INICIADO,
                "status_lab_label": "-",
                "responsavel_pted": "-",
                "responsavel_lab": "-",
                "desvios": int(item.get("quantidade_fora_padrao") or 0),
                "detail_url": f"/temperatura-forno-ed/legado/{lancamento.id}",
                "report_url": f"/temperatura-forno-ed/legado/{lancamento.id}",
                "report_pted_url": f"/temperatura-forno-ed/legado/{lancamento.id}",
                "report_lab_url": f"/temperatura-forno-ed/legado/{lancamento.id}",
                "sort_key": lancamento.data_referencia.isoformat() + f"-{lancamento.id:08d}",
            }
        )
    return rows


def _legacy_tensao_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for item in tensao_retificadores_service.list_history(session):
        lancamento = item["lancamento"]
        rows.append(
            {
                "id": lancamento.id,
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} Â· Turno {lancamento.turno} Â· {lancamento.modelo}",
                "data_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "status_geral": lancamento.status.upper(),
                "status_geral_label": lancamento.status.title(),
                "status_pted": SETOR_STATUS_NAO_INICIADO,
                "status_pted_label": "-",
                "status_lab": SETOR_STATUS_NAO_INICIADO,
                "status_lab_label": "-",
                "responsavel_pted": "-",
                "responsavel_lab": "-",
                "desvios": int(item.get("quantidade_fora_padrao") or 0),
                "detail_url": f"/tensao-retificadores-ed/legado/{lancamento.id}",
                "report_url": f"/tensao-retificadores-ed/legado/{lancamento.id}",
                "report_pted_url": f"/tensao-retificadores-ed/legado/{lancamento.id}",
                "report_lab_url": f"/tensao-retificadores-ed/legado/{lancamento.id}",
                "sort_key": lancamento.data_referencia.isoformat() + f"-{lancamento.id:08d}",
            }
        )
    return rows


def _legacy_poder_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for lancamento in poder_penetracao_service.list_history(session):
        rows.append(
            {
                "id": lancamento.id,
                "context_label": f"Semana {lancamento.semana_referencia} Â· {lancamento.modelo}",
                "data_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "status_geral": lancamento.status.upper(),
                "status_geral_label": lancamento.status.title(),
                "status_pted": SETOR_STATUS_NAO_INICIADO,
                "status_pted_label": "-",
                "status_lab": SETOR_STATUS_NAO_INICIADO,
                "status_lab_label": "-",
                "responsavel_pted": "-",
                "responsavel_lab": "-",
                "desvios": int(lancamento.total_reprovados or 0),
                "detail_url": f"/poder-penetracao/legado/{lancamento.id}",
                "report_url": f"/poder-penetracao/legado/{lancamento.id}",
                "report_pted_url": f"/poder-penetracao/legado/{lancamento.id}",
                "report_lab_url": f"/poder-penetracao/legado/{lancamento.id}",
                "sort_key": lancamento.data_referencia.isoformat() + f"-{lancamento.id:08d}",
            }
        )
    return rows


def _legacy_espessura_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for item in espessura_ed_service.list_history(session):
        lancamento = item["lancamento"]
        rows.append(
            {
                "id": lancamento.id,
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} Â· Turno {lancamento.turno} Â· {lancamento.modelo}",
                "data_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "status_geral": lancamento.status.upper(),
                "status_geral_label": lancamento.status.title(),
                "status_pted": SETOR_STATUS_NAO_INICIADO,
                "status_pted_label": "-",
                "status_lab": SETOR_STATUS_NAO_INICIADO,
                "status_lab_label": "-",
                "responsavel_pted": "-",
                "responsavel_lab": "-",
                "desvios": 0,
                "detail_url": f"/espessura-ed/legado/{lancamento.id}",
                "report_url": f"/espessura-ed/legado/{lancamento.id}",
                "report_pted_url": f"/espessura-ed/legado/{lancamento.id}",
                "report_lab_url": f"/espessura-ed/legado/{lancamento.id}",
                "sort_key": lancamento.data_referencia.isoformat() + f"-{lancamento.id:08d}",
            }
        )
    return rows


def _legacy_aspecto_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for lancamento in aspecto_service.list_history(session):
        rows.append(
            {
                "id": lancamento.id,
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} Â· Turno {lancamento.turno} Â· {lancamento.modelo}",
                "data_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "status_geral": MODULE_STATUS_CONCLUIDO,
                "status_geral_label": STATUS_LABELS[MODULE_STATUS_CONCLUIDO],
                "status_pted": SETOR_STATUS_NAO_INICIADO,
                "status_pted_label": "-",
                "status_lab": SETOR_STATUS_NAO_INICIADO,
                "status_lab_label": "-",
                "responsavel_pted": "-",
                "responsavel_lab": "-",
                "desvios": int(lancamento.total_registros or 0),
                "detail_url": f"/aspecto/legado/{lancamento.id}",
                "report_url": f"/aspecto/legado/{lancamento.id}",
                "report_pted_url": f"/aspecto/legado/{lancamento.id}",
                "report_lab_url": f"/aspecto/legado/{lancamento.id}",
                "sort_key": lancamento.data_referencia.isoformat() + f"-{lancamento.id:08d}",
            }
        )
    return rows


def _legacy_rugosidade_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for lancamento in rugosidade_service.list_history(session):
        rows.append(
            {
                "id": lancamento.id,
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} Â· {lancamento.sequencia}",
                "data_label": lancamento.data_referencia.strftime("%d/%m/%Y"),
                "status_geral": lancamento.status.upper(),
                "status_geral_label": lancamento.status.title(),
                "status_pted": SETOR_STATUS_NAO_INICIADO,
                "status_pted_label": "-",
                "status_lab": SETOR_STATUS_NAO_INICIADO,
                "status_lab_label": "-",
                "responsavel_pted": "-",
                "responsavel_lab": "-",
                "desvios": int(lancamento.total_modelos_fora_padrao or 0),
                "detail_url": f"/rugosidade/legado/{lancamento.id}",
                "report_url": f"/rugosidade/legado/{lancamento.id}",
                "report_pted_url": f"/rugosidade/legado/{lancamento.id}",
                "report_lab_url": f"/rugosidade/legado/{lancamento.id}",
                "sort_key": lancamento.data_referencia.isoformat() + f"-{lancamento.id:08d}",
            }
        )
    return rows


def _ed_rows(session: Session, context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    turno = str(context.get("turno") or "")
    items = ed_service.load_items_for_context(session, SETOR_SOURCE_LABELS[setor_tipo], turno)
    return [
        {
            "reference": str(item.id),
            "order": item.ordem_exibicao or item.id,
            "operacao": item.operacao_equipamento,
            "descricao": item.descricao_controle,
            "parametro": item.parametro or "-",
            "value": "",
            "row_observation": "",
            "status_label": ed_service.EVALUATION_LABELS["neutral"],
            "flag": False,
        }
        for item in items
    ]


def _ed_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _ed_rows(session, context, setor_tipo)
    flagged = 0
    for row in rows:
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        evaluation = ed_service.evaluate_parameter(row["parametro"] if row["parametro"] != "-" else None, value)
        if evaluation["fora_parametro"] is True and not observation:
            raise OperationalModuleValidationError(
                f"Informe observação para item fora do padrão no setor {SETOR_LABELS[setor_tipo]}."
            )
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "status_label": evaluation["label"],
                "flag": bool(evaluation["fora_parametro"]),
            }
        )
        flagged += int(bool(evaluation["fora_parametro"]))
    summary = _summarize_rows(rows)
    summary["flag_count"] = flagged
    return rows, summary


def _pressao_rows(_session: Session, _context: dict[str, Any], _setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": str(numero),
            "order": numero,
            "label": f"Filtro {numero}",
            "expected": "â‰¤ 1,0 bar",
            "value": "",
            "status_label": "Normal",
            "flag": False,
        }
        for numero in range(1, pressao_filtros_service.TOTAL_FILTROS + 1)
    ]


def _pressao_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _pressao_rows(session, context, setor_tipo)
    for row in rows:
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        parsed = _parse_decimal(value, "Valor de pressão inválido: '{value}'.")
        flag = pressao_filtros_service._compute_alarm(parsed)
        row.update({"value": value, "value_number": parsed, "status_label": "Em alarme" if flag else "Normal", "flag": flag})
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _temperatura_rows(_session: Session, _context: dict[str, Any], _setor_tipo: str) -> list[dict[str, Any]]:
    rows = []
    for spec in temperatura_forno_service.ZONA_SPECS:
        faixa_min = spec["nominal"] - spec["tolerancia"]
        faixa_max = spec["nominal"] + spec["tolerancia"]
        rows.append(
            {
                "reference": str(spec["zona_numero"]),
                "order": spec["zona_numero"],
                "label": f"Zona {spec['zona_numero']}",
                "expected": f"{int(faixa_min)} a {int(faixa_max)} °C",
                "faixa_min": faixa_min,
                "faixa_max": faixa_max,
                "value": "",
                "status_label": temperatura_forno_service.STATUS_LABELS["neutral"],
                "flag": False,
            }
        )
    return rows


def _temperatura_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _temperatura_rows(session, context, setor_tipo)
    for row in rows:
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        parsed = _parse_decimal(value, "Temperatura inválida: '{value}'.")
        status = temperatura_forno_service._evaluate_zone(parsed, row["faixa_min"], row["faixa_max"])
        row.update({"value": value, "value_number": parsed, "status_label": status["label"], "flag": bool(status["fora_padrao"])})
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _tensao_rows(_session: Session, _context: dict[str, Any], _setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": str(numero),
            "order": numero,
            "label": f"Zona {numero}",
            "expected": f"{int(tensao_retificadores_service.FAIXA_MINIMA)}V a {int(tensao_retificadores_service.FAIXA_MAXIMA)}V",
            "value": "",
            "status_label": tensao_retificadores_service.STATUS_LABELS["neutral"],
            "flag": False,
        }
        for numero in range(1, tensao_retificadores_service.TOTAL_ZONAS + 1)
    ]


def _tensao_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _tensao_rows(session, context, setor_tipo)
    for row in rows:
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        parsed = _parse_decimal(value, "Valor de tensão inválido: '{value}'.")
        status = tensao_retificadores_service._evaluate_tensao(parsed)
        row.update({"value": value, "value_number": parsed, "status_label": status["label"], "flag": bool(status["fora_padrao"])})
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _poder_rows(_session: Session, _context: dict[str, Any], _setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": str(numero),
            "order": numero,
            "label": f"Ponto {numero}",
            "expected": f"â‰¥ {poder_penetracao_service.VALOR_REFERENCIA}",
            "value": "",
            "status_label": poder_penetracao_service.STATUS_LABELS["empty"],
            "flag": False,
        }
        for numero in range(1, poder_penetracao_service.TOTAL_PONTOS + 1)
    ]


def _poder_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _poder_rows(session, context, setor_tipo)
    approved = 0
    filled = 0
    for row in rows:
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        parsed = _parse_decimal(value, "Valor inválido no ensaio: '{value}'.")
        status = poder_penetracao_service._evaluate_value(parsed)
        row.update({"value": value, "value_number": parsed, "status_label": status["label"], "flag": status["status"] == "reproved"})
        if parsed is not None:
            filled += 1
            if status["status"] == "approved":
                approved += 1
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    summary["aprovados"] = approved
    summary["percentual_aprovacao"] = int(round((approved / filled) * 100)) if filled else 0
    return rows, summary


def _espessura_rows(_session: Session, _context: dict[str, Any], _setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": str(numero),
            "order": numero,
            "label": f"Ponto {numero}",
            "expected": "Faixa de atenção: 10 a 60 µm",
            "value": "",
            "status_label": espessura_ed_service.STATUS_LABELS["empty"],
            "flag": False,
        }
        for numero in range(1, espessura_ed_service.TOTAL_PONTOS + 1)
    ]


def _espessura_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _espessura_rows(session, context, setor_tipo)
    for row in rows:
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        parsed = _parse_decimal(value, "Valor de espessura inválido: '{value}'.")
        status = espessura_ed_service._evaluate_value(parsed)
        row.update({"value": value, "value_number": parsed, "status_label": status["label"], "flag": status["status"] == "attention"})
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _rugosidade_rows(_session: Session, _context: dict[str, Any], _setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": codigo,
            "order": index,
            "label": f"Modelo {codigo}",
            "expected": f"â‰¤ {rugosidade_service.LIMITE_REFERENCIA}",
            "value": "",
            "status_label": rugosidade_service.STATUS_LABELS["empty"],
            "flag": False,
        }
        for index, codigo in enumerate(rugosidade_service.MODELOS_FIXOS, start=1)
    ]


def _rugosidade_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _rugosidade_rows(session, context, setor_tipo)
    for row in rows:
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        parsed = _parse_decimal(value, "Valor inválido de rugosidade: '{value}'.")
        status = rugosidade_service._evaluate_value(parsed)
        row.update({"value": value, "value_number": parsed, "status_label": status["label"], "flag": status["status"] == "outlier"})
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _aspecto_rows(_session: Session, _context: dict[str, Any], _setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": str(index),
            "order": index,
            "cis": "",
            "cod_posicao": "",
            "local": "",
            "anomalia": "",
            "lado": "",
            "geracao": "",
            "quantidade": "1",
            "value": "",
            "status_label": "Linha vazia",
            "flag": False,
        }
        for index in range(1, aspecto_service.MAX_REGISTROS_POR_LOTE + 1)
    ]


def _aspecto_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total_quantidade = 0
    for index in range(1, aspecto_service.MAX_REGISTROS_POR_LOTE + 1):
        cis = (form_data.get(f"cis_{setor_tipo}_{index}") or "").strip()
        cod_posicao = (form_data.get(f"cod_posicao_{setor_tipo}_{index}") or "").strip()
        local = (form_data.get(f"local_{setor_tipo}_{index}") or "").strip()
        anomalia = (form_data.get(f"anomalia_{setor_tipo}_{index}") or "").strip()
        lado = (form_data.get(f"lado_{setor_tipo}_{index}") or "").strip()
        geracao = (form_data.get(f"geracao_{setor_tipo}_{index}") or "").strip()
        quantidade = (form_data.get(f"quantidade_{setor_tipo}_{index}") or "").strip()
        if not any([cis, cod_posicao, local, anomalia, lado, geracao, quantidade]):
            if index <= 5:
                rows.append(_aspecto_rows(session, context, setor_tipo)[index - 1])
            continue
        missing = [
            label
            for key, label in {
                "cis": "CIS",
                "cod_posicao": "código da posição",
                "local": "local",
                "anomalia": "anomalia",
                "lado": "lado",
                "geracao": "geração",
                "quantidade": "quantidade",
            }.items()
            if not locals()[key]
        ]
        if missing:
            raise OperationalModuleValidationError(f"Complete a linha {index}: {', '.join(missing)}.")
        try:
            quantidade_int = int(quantidade)
        except ValueError as error:
            raise OperationalModuleValidationError(f"Quantidade inválida na linha {index}.") from error
        total_quantidade += quantidade_int
        rows.append(
            {
                "reference": str(index),
                "order": index,
                "cis": cis,
                "cod_posicao": cod_posicao,
                "local": local,
                "anomalia": anomalia,
                "lado": lado,
                "geracao": geracao,
                "quantidade": str(quantidade_int),
                "value": anomalia,
                "status_label": "Registrado",
                "flag": True,
            }
        )
    if not any(row.get("cis") for row in rows):
        raise OperationalModuleValidationError("Adicione ao menos uma linha para o lote do setor.")
    summary = _summarize_rows(rows)
    summary["flag_count"] = len([row for row in rows if row.get("cis")])
    summary["total_quantidade"] = total_quantidade
    return rows, summary


MODULE_CONFIGS: dict[str, ModuleConfig] = {
    "ed": ModuleConfig(
        code="ed",
        slug="ed",
        title="ED",
        description="Checklist operacional consolidado por contexto, com preenchimento independente por PTED e Laboratório.",
        history_title="Histórico consolidado · ED",
        report_title="Relatório consolidado · ED",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("tipo_dia", "Tipo do dia", "select", True, "tipo_dia"),
            ContextField("turno", "Turno", "select", True, "turnos"),
        ),
        columns=(
            TableColumn("operacao", "Operação"),
            TableColumn("descricao", "Controle"),
            TableColumn("parametro", "Parâmetro"),
            TableColumn("value", "Valor", "input"),
            TableColumn("row_observation", "Observação", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_ed_rows,
        parse_rows=_ed_parse,
        legacy_history_builder=_legacy_ed_history,
        legacy_detail_loader=ed_service.get_lancamento,
        legacy_detail_template="ed/detail.html",
        supports_turno=True,
    ),
    "temperatura-forno-ed": ModuleConfig(
        code="temperatura-forno-ed",
        slug="temperatura-forno-ed",
        title="Temperatura Forno",
        description="Doze zonas térmicas consolidadas por data com duas frentes operacionais independentes.",
        history_title="Histórico consolidado · Temperatura Forno",
        report_title="Relatório · Temperatura Forno",
        context_fields=(ContextField("data_referencia", "Data", "date", True),),
        columns=(
            TableColumn("label", "Zona"),
            TableColumn("expected", "Faixa"),
            TableColumn("value", "Temperatura (°C)", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_temperatura_rows,
        parse_rows=_temperatura_parse,
        legacy_history_builder=_legacy_temp_history,
        legacy_detail_loader=temperatura_forno_service.get_lancamento,
        legacy_detail_template="temperatura_forno_ed/detail.html",
    ),
    "pressao-filtros-ed": ModuleConfig(
        code="pressao-filtros-ed",
        slug="pressao-filtros-ed",
        title="Pressão dos Filtros ED",
        description="Leitura dos 24 filtros com alarmes calculados por setor e consolidado geral do contexto.",
        history_title="Histórico consolidado · Pressão dos Filtros ED",
        report_title="Relatório · Pressão dos Filtros ED",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("turno", "Turno", "select", True, "turnos"),
        ),
        columns=(
            TableColumn("label", "Filtro"),
            TableColumn("expected", "Limite"),
            TableColumn("value", "Pressão (bar)", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_pressao_rows,
        parse_rows=_pressao_parse,
        legacy_history_builder=_legacy_pressao_history,
        legacy_detail_loader=pressao_filtros_service.get_lancamento,
        legacy_detail_template="pressao_filtros_ed/detail.html",
        supports_turno=True,
    ),
    "tensao-retificadores-ed": ModuleConfig(
        code="tensao-retificadores-ed",
        slug="tensao-retificadores-ed",
        title="Tensão dos Retificadores ED",
        description="Controle das 29 zonas dos retificadores por data, turno e modelo em duas abas setoriais.",
        history_title="Histórico consolidado · Tensão dos Retificadores ED",
        report_title="Relatório · Tensão dos Retificadores ED",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("turno", "Turno", "select", True, "turnos"),
            ContextField("modelo", "Modelo", "select", True, "modelos"),
        ),
        columns=(
            TableColumn("label", "Zona"),
            TableColumn("expected", "Faixa"),
            TableColumn("value", "Tensão (V)", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_tensao_rows,
        parse_rows=_tensao_parse,
        legacy_history_builder=_legacy_tensao_history,
        legacy_detail_loader=tensao_retificadores_service.get_lancamento,
        legacy_detail_template="tensao_retificadores_ed/detail.html",
        supports_turno=True,
    ),
    "poder-penetracao": ModuleConfig(
        code="poder-penetracao",
        slug="poder-penetracao",
        title="Poder de Penetração",
        description="Matriz de 30 pontos com aprovação automática e consolidação setorial por semana e modelo.",
        history_title="Histórico consolidado · Poder de Penetração",
        report_title="Relatório · Poder de Penetração",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("semana_referencia", "Semana", "text", True),
            ContextField("modelo", "Modelo", "select", True, "modelos"),
            ContextField("cis", "CIS"),
            ContextField("velocidade", "Velocidade"),
            ContextField("tipo", "Tipo"),
        ),
        columns=(
            TableColumn("label", "Ponto"),
            TableColumn("expected", "Referência"),
            TableColumn("value", "Valor medido", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_poder_rows,
        parse_rows=_poder_parse,
        legacy_history_builder=_legacy_poder_history,
        legacy_detail_loader=poder_penetracao_service.get_lancamento,
        legacy_detail_template="poder_penetracao/detail.html",
    ),
    "espessura-ed": ModuleConfig(
        code="espessura-ed",
        slug="espessura-ed",
        title="Espessura ED",
        description="Rastreabilidade de 38 pontos por contexto, com salvamento independente por PTED e Laboratório.",
        history_title="Histórico consolidado · Espessura ED",
        report_title="Relatório · Espessura ED",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("turno", "Turno", "select", True, "turnos"),
            ContextField("modelo", "Modelo", "select", True, "modelos"),
            ContextField("cis", "CIS"),
        ),
        columns=(
            TableColumn("label", "Ponto"),
            TableColumn("expected", "Faixa"),
            TableColumn("value", "Espessura (µm)", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_espessura_rows,
        parse_rows=_espessura_parse,
        legacy_history_builder=_legacy_espessura_history,
        legacy_detail_loader=espessura_ed_service.get_lancamento,
        legacy_detail_template="espessura_ed/detail.html",
        supports_turno=True,
    ),
    "aspecto": ModuleConfig(
        code="aspecto",
        slug="aspecto",
        title="Aspecto",
        description="Registro operacional de lote com observações separadas por setor e visão consolidada do contexto.",
        history_title="Histórico consolidado · Aspecto",
        report_title="Relatório · Aspecto",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("turno", "Turno", "select", True, "turnos"),
            ContextField("modelo", "Modelo", "select", True, "modelos"),
        ),
        columns=(
            TableColumn("cis", "CIS", "input"),
            TableColumn("cod_posicao", "Posição", "input"),
            TableColumn("local", "Local", "input"),
            TableColumn("anomalia", "Anomalia", "input"),
            TableColumn("lado", "Lado", "input"),
            TableColumn("geracao", "Geração", "input"),
            TableColumn("quantidade", "Qtd.", "input"),
        ),
        default_rows_builder=_aspecto_rows,
        parse_rows=_aspecto_parse,
        legacy_history_builder=_legacy_aspecto_history,
        legacy_detail_loader=aspecto_service.get_lancamento,
        legacy_detail_template="aspecto/detail.html",
        supports_turno=True,
    ),
    "rugosidade": ModuleConfig(
        code="rugosidade",
        slug="rugosidade",
        title="Rugosidade",
        description="Matriz fixa por sequência com controle setorial independente e consolidação automática do módulo.",
        history_title="Histórico consolidado · Rugosidade",
        report_title="Relatório · Rugosidade",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("sequencia", "Sequência", "select", True, "sequencias_rugosidade"),
        ),
        columns=(
            TableColumn("label", "Modelo"),
            TableColumn("expected", "Limite"),
            TableColumn("value", "Rugosidade", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_rugosidade_rows,
        parse_rows=_rugosidade_parse,
        legacy_history_builder=_legacy_rugosidade_history,
        legacy_detail_loader=rugosidade_service.get_lancamento,
        legacy_detail_template="rugosidade/detail.html",
    ),
}


def get_module_config(module_key: str) -> ModuleConfig:
    config = MODULE_CONFIGS.get(module_key)
    if config is None:
        raise OperationalModuleValidationError(f"Módulo inválido: {module_key}.")
    return config

