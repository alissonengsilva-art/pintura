from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
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
from app.services import item_frequency_runtime_service
from app.services import module_parameter_validation
from app.services import operational_module_item_service
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

WEEKDAY_LABELS_SHORT = {
    0: "segunda",
    1: "terca",
    2: "quarta",
    3: "quinta",
    4: "sexta",
    5: "sabado",
    6: "domingo",
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
    sector_sequence: tuple[str, ...] = (SETOR_PTED, SETOR_LAB)
    supports_turno: bool = False
    frequency: str = "daily"  # "daily" | "weekly" | "conditional"


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
        "operational_module_items",
    )
    return all(inspector.has_table(table_name) for table_name in required_tables)

def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


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
            {"value": "1a coleta", "label": "1\u00aa coleta"},
            {"value": "2a coleta", "label": "2\u00aa coleta"},
            {"value": "3a coleta", "label": "3\u00aa coleta"},
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
    return " \u00b7 ".join(parts)


def build_context_key(config: ModuleConfig, context: dict[str, Any]) -> str:
    parts = [config.code]
    for field in config.context_fields:
        value = context.get(field.name)
        normalized = value.isoformat() if isinstance(value, date) else str(value or "").strip().lower()
        parts.append(f"{field.name}={normalized}")
    return "|".join(parts)


def get_or_create_master(
    session: Session,
    config: ModuleConfig,
    context: dict[str, Any],
    shift_id: int | None = None,
) -> OperationalModuleRecord:
    if not operational_schema_available(session):
        raise OperationalModuleValidationError(MISSING_SCHEMA_MESSAGE)
    key = build_context_key(config, context)
    by_shift_statement = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores).joinedload(OperationalModuleSectorRecord.respostas))
        .where(OperationalModuleRecord.module_code == config.code)
    )
    by_context_statement = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores).joinedload(OperationalModuleSectorRecord.respostas))
        .where(OperationalModuleRecord.module_code == config.code)
        .where(OperationalModuleRecord.context_key == key)
    )

    if shift_id is not None:
        master = session.scalars(by_shift_statement.where(OperationalModuleRecord.shift_id == shift_id)).unique().first()
        if master is None:
            master = session.scalars(by_context_statement).unique().first()
    else:
        master = session.scalars(by_context_statement).unique().first()
    if master is None:
        now = datetime.now(UTC).replace(tzinfo=None)
        master = OperationalModuleRecord(
            module_code=config.code,
            data_referencia=context["data_referencia"],
            turno=str(context.get("turno") or "") or None,
            context_key=key,
            context_data=_serialize_context(config, context),
            status_geral=MODULE_STATUS_NAO_INICIADO,
            shift_id=shift_id,  # Vínculo com turno operacional
            created_at=now,
            updated_at=now,
        )
        session.add(master)
        session.flush()
        for setor_tipo in config.sector_sequence:
            session.add(
                OperationalModuleSectorRecord(
                    registro_mestre_id=master.id,
                    setor_tipo=setor_tipo,
                    status_setor=SETOR_STATUS_NAO_INICIADO,
                    metricas={},
                )
            )
        session.flush()
        if shift_id is not None:
            master = session.scalars(by_shift_statement.where(OperationalModuleRecord.shift_id == shift_id)).unique().first()
        else:
            master = session.scalars(by_context_statement).unique().first()
    else:
        if shift_id is not None and master.shift_id not in (None, shift_id):
            raise OperationalModuleValidationError("O registro informado pertence a outro turno operacional.")
        master.data_referencia = context["data_referencia"]
        master.turno = str(context.get("turno") or "") or None
        master.context_key = key
        master.context_data = _serialize_context(config, context)
        if shift_id and not master.shift_id:
            master.shift_id = shift_id
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


def get_master_by_shift(session: Session, shift_id: int, module_code: str) -> OperationalModuleRecord | None:
    if not operational_schema_available(session):
        return None
    statement = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores).joinedload(OperationalModuleSectorRecord.respostas))
        .where(OperationalModuleRecord.shift_id == shift_id)
        .where(OperationalModuleRecord.module_code == module_code)
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
    if config.code == "aspecto" and entry_map:
        known_refs = {str(row.get("reference")) for row in hydrated_rows}
        extra_rows: list[dict[str, Any]] = []
        for reference, stored_row in entry_map.items():
            if str(reference) in known_refs:
                continue
            extra_row = {
                "reference": str(reference),
                "order": int(stored_row.get("order") or 9999),
                "item_id": stored_row.get("item_id"),
                "item_observation": stored_row.get("item_observation", ""),
                "cis": "",
                "cod_posicao": "",
                "local": "",
                "anomalia": "",
                "lado": "",
                "geracao": "",
                "quantidade": "",
                "row_observation": "",
                "value": "",
                "status_label": "Linha vazia",
                "flag": False,
                "is_applicable": True,
                "applicability_label": "Aplicável",
            }
            extra_row.update(stored_row)
            extra_rows.append(extra_row)
        if extra_rows:
            extra_rows.sort(key=lambda row: (int(row.get("order") or 9999), str(row.get("reference") or "")))
            hydrated_rows.extend(extra_rows)
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
    shift_id: int | None = None,
) -> OperationalModuleRecord:
    if not operational_schema_available(session):
        raise OperationalModuleValidationError(MISSING_SCHEMA_MESSAGE)
    if setor_tipo not in config.sector_sequence:
        raise OperationalModuleValidationError(f"Setor inválido para o módulo {config.title}.")
    if shift_id is not None:
        master = get_or_create_master(session, config, context, shift_id=shift_id)
    else:
        master = get_master_by_context(session, config, context)
        if master is None or master.shift_id is None:
            raise OperationalModuleValidationError("Este modulo so pode ser executado pela tela principal do turno.")
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
    sector.metricas = _json_safe(metricas)
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
                dados=_json_safe(row),
                created_at=now,
                updated_at=now,
            )
        )

    master.status_geral = _calculate_module_status(master.setores, config.sector_sequence)
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
    turno_url = f"/turnos/{master.shift_id}?modulo={config.code}" if master.shift_id else None
    lab_enabled = SETOR_LAB in config.sector_sequence
    return {
        "id": master.id,
        "context_label": context_label(config, master.context_data),
        "data_label": master.data_referencia.strftime("%d/%m/%Y"),
        "status_geral": master.status_geral,
        "status_geral_label": STATUS_LABELS[master.status_geral],
        "status_pted": pted.status_setor if pted else SETOR_STATUS_NAO_INICIADO,
        "status_pted_label": STATUS_LABELS[pted.status_setor] if pted else STATUS_LABELS[SETOR_STATUS_NAO_INICIADO],
        "status_lab": lab.status_setor if lab and lab_enabled else SETOR_STATUS_NAO_INICIADO,
        "status_lab_label": STATUS_LABELS[lab.status_setor] if lab and lab_enabled else "-",
        "responsavel_pted": pted.responsavel_nome if pted and pted.responsavel_nome else "-",
        "responsavel_lab": lab.responsavel_nome if lab and lab.responsavel_nome and lab_enabled else "-",
        "desvios": total_flags,
        "detail_url": f"/{config.slug}/registros/{master.id}",
        "report_url": f"/relatorios/visualizar/modulos/{config.code}/{master.id}",
        "report_pted_url": f"/relatorios/visualizar/modulos/{config.code}/{master.id}?setor=PTED",
        "report_lab_url": f"/relatorios/visualizar/modulos/{config.code}/{master.id}?setor=LABORATORIO",
        "shift_id": master.shift_id,
        "turno_url": turno_url,
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
    setor_views = [build_sector_view(session, config, context, master, setor) for setor in config.sector_sequence]
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


def _override_map_for_context(session: Session, context: dict[str, Any]) -> dict[int, Any]:
    override_map = context.get("_override_map")
    if isinstance(override_map, dict):
        return override_map
    override_map = item_frequency_runtime_service.get_override_map(session, int(context.get("shift_id") or 0) or None)
    context["_override_map"] = override_map
    return override_map


def _runtime_item_state(session: Session, context: dict[str, Any], item: Any) -> dict[str, Any]:
    override = _override_map_for_context(session, context).get(int(item.id))
    state = item_frequency_runtime_service.resolve_item_applicability(
        item,
        context["data_referencia"],
        override.override_status if override else None,
        override.reason if override else None,
    )
    weekday = getattr(item, "dia_semana", None)
    if weekday == 7:
        weekday = 6
    weekday_label = WEEKDAY_LABELS_SHORT.get(int(weekday)) if isinstance(weekday, int) else None
    day_of_month = getattr(item, "dia_mes", None)
    scheduled_short = state.get("applicability_label", "")
    scheduled_tooltip = None
    if not state.get("is_applicable", True):
        frequency_type = state.get("frequency_type")
        if frequency_type == item_frequency_runtime_service.FREQUENCY_SEMANAL and weekday_label:
            scheduled_short = f"Agendado {weekday_label}"
            scheduled_tooltip = f"Este item e semanal e so pode ser preenchido na {weekday_label}."
        elif frequency_type == item_frequency_runtime_service.FREQUENCY_MENSAL and day_of_month:
            scheduled_short = f"Agendado dia {int(day_of_month)}"
            scheduled_tooltip = f"Este item e mensal e so pode ser preenchido no dia {int(day_of_month)}."
        elif frequency_type == item_frequency_runtime_service.FREQUENCY_SOB_DEMANDA:
            scheduled_short = "Sob demanda"
            scheduled_tooltip = "Este item so deve ser preenchido quando houver demanda no turno."
    state["scheduled_weekday_label"] = weekday_label
    state["scheduled_day_of_month"] = int(day_of_month) if isinstance(day_of_month, int) else None
    state["scheduled_label_short"] = scheduled_short
    state["scheduled_tooltip"] = scheduled_tooltip
    return state


def _hydrate_rows(rows: list[dict[str, Any]], stored: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for row in rows:
        current = dict(row)
        current.update(stored.get(str(row.get("reference")), {}))
        if not current.get("is_applicable", True):
            current["status_label"] = current.get("applicability_label", current.get("status_label"))
            current["flag"] = False
        hydrated.append(current)
    return hydrated


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return item_frequency_runtime_service.calculate_row_progress(rows)


def _find_sector(master: OperationalModuleRecord | None, setor_tipo: str) -> OperationalModuleSectorRecord | None:
    if master is None:
        return None
    for setor in master.setores:
        if setor.setor_tipo == setor_tipo:
            return setor
    return None


def _calculate_module_status(
    setores: list[OperationalModuleSectorRecord],
    setor_sequence: tuple[str, ...] = tuple(SETOR_SEQUENCE),
) -> str:
    statuses = {setor.setor_tipo: setor.status_setor for setor in setores}
    if all(statuses.get(setor, SETOR_STATUS_NAO_INICIADO) == SETOR_STATUS_NAO_INICIADO for setor in setor_sequence):
        return MODULE_STATUS_NAO_INICIADO
    if all(statuses.get(setor) == SETOR_STATUS_CONCLUIDO for setor in setor_sequence):
        return MODULE_STATUS_CONCLUIDO
    if any(statuses.get(setor) == SETOR_STATUS_CONCLUIDO for setor in setor_sequence):
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
    parsed = module_parameter_validation.parse_numeric_value(str(raw_value or ""))
    if str(raw_value or "").strip() and parsed is None:
        text = str(raw_value or "").strip()
        raise OperationalModuleValidationError(message.format(value=text))
    return parsed


def _item_validation_meta(item: Any) -> dict[str, Any]:
    return {
        "tipo_validacao": module_parameter_validation.normalize_validation_type(getattr(item, "tipo_validacao", None)),
        "limite_minimo": getattr(item, "limite_minimo", None),
        "limite_maximo": getattr(item, "limite_maximo", None),
        "unidade": getattr(item, "unidade", None),
        "parametro_exibicao": module_parameter_validation.display_parameter(item),
    }


def _evaluate_item_input(row: dict[str, Any], value: str) -> module_parameter_validation.ValidationResult:
    return module_parameter_validation.evaluate(
        value,
        tipo_validacao=row.get("tipo_validacao"),
        limite_minimo=row.get("limite_minimo"),
        limite_maximo=row.get("limite_maximo"),
    )


def _is_conclude_action(form_data: Any) -> bool:
    return str(form_data.get("submit_action") or "").strip().lower() == "concluir"


def _enforce_required_fields_on_conclude(
    rows: list[dict[str, Any]],
    *,
    setor_tipo: str,
) -> None:
    for row in rows:
        if not row.get("is_applicable"):
            continue
        value = str(row.get("value") or "").strip()
        if not value:
            label = row.get("label") or row.get("descricao") or row.get("reference") or "item"
            raise OperationalModuleValidationError(
                f"Preencha o valor do item '{label}' antes de concluir o setor {SETOR_LABELS[setor_tipo]}."
            )
        if bool(row.get("flag")) and not str(row.get("row_observation") or "").strip():
            label = row.get("label") or row.get("descricao") or row.get("reference") or "item"
            expected = row.get("expected") or row.get("parametro") or row.get("parametro_exibicao") or "-"
            raise OperationalModuleValidationError(
                f"Informe observação para item fora do padrão no setor {SETOR_LABELS[setor_tipo]}: "
                f"{label} (valor: {value}, regra: {expected})."
            )


def _legacy_ed_history(session: Session) -> list[dict[str, Any]]:
    rows = []
    for item in ed_service.list_history(session):
        lancamento = item["lancamento"]
        rows.append(
            {
                "id": lancamento.id,
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} \u00b7 Turno {lancamento.turno} \u00b7 {lancamento.setor}",
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
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} \u00b7 Turno {lancamento.turno}",
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
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} \u00b7 Turno {lancamento.turno} \u00b7 {lancamento.modelo}",
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
                "context_label": f"Semana {lancamento.semana_referencia} \u00b7 {lancamento.modelo}",
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
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} \u00b7 Turno {lancamento.turno} \u00b7 {lancamento.modelo}",
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
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} \u00b7 Turno {lancamento.turno} \u00b7 {lancamento.modelo}",
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
                "context_label": f"{lancamento.data_referencia.strftime('%d/%m/%Y')} \u00b7 {lancamento.sequencia}",
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
            "order": item.ordem or item.id,
            "operacao": item.operacao or "-",
            "descricao": item.controle,
            "item_observation": (item.observacao or "").strip() if item.observacao else "",
            "parametro": module_parameter_validation.display_parameter(item),
            "value": "",
            "row_observation": "",
            "status_label": _runtime_item_state(session, context, item)["applicability_label"]
            if not _runtime_item_state(session, context, item)["is_applicable"]
            else ed_service.EVALUATION_LABELS["neutral"],
            "flag": False,
            "item_id": item.id,
            **_item_validation_meta(item),
            **_runtime_item_state(session, context, item),
        }
        for item in items
    ]


def _ed_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _ed_rows(session, context, setor_tipo)
    flagged = 0
    require_observation_on_out = _is_conclude_action(form_data)
    for row in rows:
        if not row.get("is_applicable"):
            row.update({"value": "", "row_observation": "", "flag": False})
            continue
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        evaluation = _evaluate_item_input(row, value)
        if require_observation_on_out and evaluation.fora_padrao is True and not observation:
            item_label = f"{row.get('operacao') or '-'} / {row.get('descricao') or '-'}"
            regra = str(row.get("parametro_exibicao") or row.get("parametro") or "-")
            raise OperationalModuleValidationError(
                "Informe observação para item fora do padrão no setor "
                f"{SETOR_LABELS[setor_tipo]}: {item_label} (valor: {value or '-'}, regra: {regra})."
            )
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "value_number": evaluation.value_number,
                "status_label": evaluation.label,
                "flag": bool(evaluation.fora_padrao),
            }
        )
        flagged += int(bool(evaluation.fora_padrao))
    summary = _summarize_rows(rows)
    summary["flag_count"] = flagged
    return rows, summary


def _pt_rows(session: Session, context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    items = _module_items(session, "pt", setor_tipo)
    return [
        {
            "reference": str(item.id),
            "order": item.ordem or item.id,
            "operacao": item.operacao or "-",
            "descricao": item.controle,
            "norma": item.norma or "-",
            "parametro": module_parameter_validation.display_parameter(item),
            "numero_coleta": str(item.numero_coleta or "-"),
            "value": "",
            "row_observation": "",
            "status_label": _runtime_item_state(session, context, item)["applicability_label"]
            if not _runtime_item_state(session, context, item)["is_applicable"]
            else "NÃO AVALIADO",
            "flag": False,
            "item_id": item.id,
            **_item_validation_meta(item),
            **_runtime_item_state(session, context, item),
        }
        for item in items
    ]


def _pt_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _pt_rows(session, context, setor_tipo)
    flagged = 0
    has_ko_without_observation = False
    for row in rows:
        if not row.get("is_applicable"):
            row.update({"value": "", "row_observation": "", "flag": False})
            continue
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        evaluation = _evaluate_item_input(row, value)
        if not value:
            status_label = "NÃO AVALIADO"
            is_ko = False
        else:
            is_ko = bool(evaluation.fora_padrao)
            status_label = "KO" if is_ko else "OK"
        if is_ko and not observation:
            has_ko_without_observation = True
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "value_number": evaluation.value_number,
                "status_label": status_label,
                "flag": is_ko,
            }
        )
        flagged += int(is_ko)
    if _is_conclude_action(form_data) and has_ko_without_observation:
        raise OperationalModuleValidationError(
            "Existem itens KO sem observação. Preencha a observação antes de concluir o turno."
        )
    summary = _summarize_rows(rows)
    summary["flag_count"] = flagged
    return rows, summary


def _pt_pressao_rows(session: Session, context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    items = _module_items(session, "pressao-filtros-pt", setor_tipo)
    return [
        {
            "reference": str(item.id),
            "order": item.ordem or item.id,
            "label": item.controle or f"FILTRO {item.ordem or item.id}",
            "value": "",
            "row_observation": "",
            "status_label": _runtime_item_state(session, context, item)["applicability_label"]
            if not _runtime_item_state(session, context, item)["is_applicable"]
            else "NÃO AVALIADO",
            "flag": False,
            "item_id": item.id,
            **_item_validation_meta(item),
            **_runtime_item_state(session, context, item),
        }
        for item in items
    ]


def _pt_pressao_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _pt_pressao_rows(session, context, setor_tipo)
    for row in rows:
        if not row.get("is_applicable"):
            row.update({"value": "", "row_observation": "", "flag": False})
            continue
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "value_number": module_parameter_validation.parse_numeric_value(value),
                "status_label": "NÃO AVALIADO" if not value else "OK",
                "flag": False,
            }
        )
    if _is_conclude_action(form_data):
        _enforce_required_fields_on_conclude(rows, setor_tipo=setor_tipo)
    summary = _summarize_rows(rows)
    summary["flag_count"] = 0
    return rows, summary


def _module_items(session: Session, module_code: str, setor_tipo: str):
    return operational_module_item_service.get_items_by_module_and_setor(session, module_code, setor_tipo)


def _module_reference(module_code: str, item) -> str:
    if module_code == "rugosidade" and item.operacao:
        return str(item.operacao)
    return str(item.ordem)


def _build_pressao_item_rows(session: Session, _context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": _module_reference("pressao-filtros-ed", item),
            "order": item.ordem,
            "label": item.controle,
            "item_observation": (item.observacao or "").strip() if item.observacao else "",
            "expected": module_parameter_validation.display_parameter(item),
            "value": "",
            "row_observation": "",
            "status_label": _runtime_item_state(session, _context, item)["applicability_label"]
            if not _runtime_item_state(session, _context, item)["is_applicable"]
            else "Normal",
            "flag": False,
            "item_id": item.id,
            **_item_validation_meta(item),
            **_runtime_item_state(session, _context, item),
        }
        for item in _module_items(session, "pressao-filtros-ed", setor_tipo)
    ]


def _pressao_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _build_pressao_item_rows(session, context, setor_tipo)
    for row in rows:
        if not row.get("is_applicable"):
            row.update({"value": "", "row_observation": "", "value_number": None, "flag": False})
            continue
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        evaluation = _evaluate_item_input(row, value)
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "value_number": evaluation.value_number,
                "status_label": evaluation.label,
                "flag": bool(evaluation.fora_padrao),
            }
        )
    if _is_conclude_action(form_data):
        _enforce_required_fields_on_conclude(rows, setor_tipo=setor_tipo)
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _build_temperatura_item_rows(session: Session, _context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    rows = []
    for item in _module_items(session, "temperatura-forno-ed", setor_tipo):
        applicability = _runtime_item_state(session, _context, item)
        rows.append(
            {
                "reference": _module_reference("temperatura-forno-ed", item),
                "order": item.ordem,
                "item_id": item.id,
                "label": item.controle,
                "item_observation": (item.observacao or "").strip() if item.observacao else "",
                "expected": module_parameter_validation.display_parameter(item),
                "value": "",
                "row_observation": "",
                "status_label": applicability["applicability_label"]
                if not applicability["is_applicable"]
                else temperatura_forno_service.STATUS_LABELS["neutral"],
                "flag": False,
                **_item_validation_meta(item),
                **applicability,
            }
        )
    return rows


def _temperatura_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _build_temperatura_item_rows(session, context, setor_tipo)
    for row in rows:
        if not row.get("is_applicable"):
            row.update({"value": "", "row_observation": "", "value_number": None, "flag": False})
            continue
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        evaluation = _evaluate_item_input(row, value)
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "value_number": evaluation.value_number,
                "status_label": evaluation.label,
                "flag": bool(evaluation.fora_padrao),
            }
        )
    if _is_conclude_action(form_data):
        _enforce_required_fields_on_conclude(rows, setor_tipo=setor_tipo)
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _build_tensao_item_rows(session: Session, _context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": _module_reference("tensao-retificadores-ed", item),
            "order": item.ordem,
            "label": item.controle,
            "item_observation": (item.observacao or "").strip() if item.observacao else "",
            "expected": module_parameter_validation.display_parameter(item),
            "value": "",
            "row_observation": "",
            "status_label": _runtime_item_state(session, _context, item)["applicability_label"]
            if not _runtime_item_state(session, _context, item)["is_applicable"]
            else tensao_retificadores_service.STATUS_LABELS["neutral"],
            "flag": False,
            "item_id": item.id,
            **_item_validation_meta(item),
            **_runtime_item_state(session, _context, item),
        }
        for item in _module_items(session, "tensao-retificadores-ed", setor_tipo)
    ]


def _tensao_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _build_tensao_item_rows(session, context, setor_tipo)
    for row in rows:
        if not row.get("is_applicable"):
            row.update({"value": "", "row_observation": "", "value_number": None, "flag": False})
            continue
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        evaluation = _evaluate_item_input(row, value)
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "value_number": evaluation.value_number,
                "status_label": evaluation.label,
                "flag": bool(evaluation.fora_padrao),
            }
        )
    if _is_conclude_action(form_data):
        _enforce_required_fields_on_conclude(rows, setor_tipo=setor_tipo)
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _build_poder_item_rows(session: Session, _context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": _module_reference("poder-penetracao", item),
            "order": item.ordem,
            "label": item.controle,
            "item_observation": (item.observacao or "").strip() if item.observacao else "",
            "expected": module_parameter_validation.display_parameter(item),
            "value": "",
            "zinco": "",
            "total": "",
            "row_observation": "",
            "status_label": _runtime_item_state(session, _context, item)["applicability_label"]
            if not _runtime_item_state(session, _context, item)["is_applicable"]
            else poder_penetracao_service.STATUS_LABELS["empty"],
            "flag": False,
            "item_id": item.id,
            **_item_validation_meta(item),
            **_runtime_item_state(session, _context, item),
        }
        for item in _module_items(session, "poder-penetracao", setor_tipo)
    ]


def _poder_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _build_poder_item_rows(session, context, setor_tipo)
    approved = 0
    filled = 0
    min_ecoat: float | None = None
    for row in rows:
        if not row.get("is_applicable"):
            row.update(
                {
                    "value": "",
                    "zinco": "",
                    "total": "",
                    "row_observation": "",
                    "value_number": None,
                    "flag": False,
                }
            )
            continue
        reference = row["reference"]
        zinco = (form_data.get(f"zinc_{setor_tipo}_{reference}") or "").strip()
        total = (form_data.get(f"total_{setor_tipo}_{reference}") or "").strip()
        value_input = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        ecoat_value = value_input
        try:
            if zinco and total:
                zinc_num = float(zinco.replace(",", "."))
                total_num = float(total.replace(",", "."))
                ecoat_value = f"{(total_num - zinc_num):.2f}".rstrip("0").rstrip(".")
        except ValueError:
            ecoat_value = value_input

        evaluation = _evaluate_item_input(row, ecoat_value)
        row.update(
            {
                "value": ecoat_value,
                "zinco": zinco,
                "total": total,
                "row_observation": observation,
                "value_number": evaluation.value_number,
                "status_label": evaluation.label,
                "flag": bool(evaluation.fora_padrao),
            }
        )
        if evaluation.value_number is not None:
            filled += 1
            if not bool(evaluation.fora_padrao):
                approved += 1
            if min_ecoat is None or evaluation.value_number < min_ecoat:
                min_ecoat = evaluation.value_number
    if _is_conclude_action(form_data):
        _enforce_required_fields_on_conclude(rows, setor_tipo=setor_tipo)
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    summary["aprovados"] = approved
    summary["percentual_aprovacao"] = int(round((approved / filled) * 100)) if filled else 0
    summary["resultado"] = min_ecoat
    summary["resultado_label"] = "-" if min_ecoat is None else f"{min_ecoat:.2f}".rstrip("0").rstrip(".")
    return rows, summary


def _build_espessura_item_rows(session: Session, _context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": _module_reference("espessura-ed", item),
            "order": item.ordem,
            "label": item.controle,
            "item_observation": (item.observacao or "").strip() if item.observacao else "",
            "expected": module_parameter_validation.display_parameter(item),
            "value": "",
            "row_observation": "",
            "status_label": _runtime_item_state(session, _context, item)["applicability_label"]
            if not _runtime_item_state(session, _context, item)["is_applicable"]
            else espessura_ed_service.STATUS_LABELS["empty"],
            "flag": False,
            "item_id": item.id,
            **_item_validation_meta(item),
            **_runtime_item_state(session, _context, item),
        }
        for item in _module_items(session, "espessura-ed", setor_tipo)
    ]


def _espessura_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _build_espessura_item_rows(session, context, setor_tipo)
    for row in rows:
        if not row.get("is_applicable"):
            row.update({"value": "", "row_observation": "", "value_number": None, "flag": False})
            continue
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        evaluation = _evaluate_item_input(row, value)
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "value_number": evaluation.value_number,
                "status_label": evaluation.label,
                "flag": bool(evaluation.fora_padrao),
            }
        )
    if _is_conclude_action(form_data):
        _enforce_required_fields_on_conclude(rows, setor_tipo=setor_tipo)
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _build_rugosidade_item_rows(session: Session, _context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": _module_reference("rugosidade", item),
            "order": item.ordem,
            "label": item.controle,
            "item_observation": (item.observacao or "").strip() if item.observacao else "",
            "expected": module_parameter_validation.display_parameter(item),
            "value": "",
            "row_observation": "",
            "status_label": _runtime_item_state(session, _context, item)["applicability_label"]
            if not _runtime_item_state(session, _context, item)["is_applicable"]
            else rugosidade_service.STATUS_LABELS["empty"],
            "flag": False,
            "item_id": item.id,
            **_item_validation_meta(item),
            **_runtime_item_state(session, _context, item),
        }
        for item in _module_items(session, "rugosidade", setor_tipo)
    ]


def _rugosidade_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _build_rugosidade_item_rows(session, context, setor_tipo)
    for row in rows:
        if not row.get("is_applicable"):
            row.update({"value": "", "row_observation": "", "value_number": None, "flag": False})
            continue
        reference = row["reference"]
        value = (form_data.get(f"value_{setor_tipo}_{reference}") or "").strip()
        observation = (form_data.get(f"obs_{setor_tipo}_{reference}") or "").strip()
        evaluation = _evaluate_item_input(row, value)
        row.update(
            {
                "value": value,
                "row_observation": observation,
                "value_number": evaluation.value_number,
                "status_label": evaluation.label,
                "flag": bool(evaluation.fora_padrao),
            }
        )
    if _is_conclude_action(form_data):
        _enforce_required_fields_on_conclude(rows, setor_tipo=setor_tipo)
    summary = _summarize_rows(rows)
    summary["flag_count"] = sum(1 for row in rows if row["flag"])
    return rows, summary


def _build_aspecto_item_rows(session: Session, _context: dict[str, Any], setor_tipo: str) -> list[dict[str, Any]]:
    return [
        {
            "reference": _module_reference("aspecto", item),
            "order": item.ordem,
            "item_id": item.id,
            "item_observation": (item.observacao or "").strip() if item.observacao else "",
            "cis": "",
            "cod_posicao": "",
            "local": "",
            "anomalia": "",
            "lado": "",
            "geracao": "",
            "quantidade": "",
            "row_observation": "",
            "value": "",
            "status_label": _runtime_item_state(session, _context, item)["applicability_label"]
            if not _runtime_item_state(session, _context, item)["is_applicable"]
            else "Linha vazia",
            "flag": False,
            **_runtime_item_state(session, _context, item),
        }
        for item in _module_items(session, "aspecto", setor_tipo)
    ]


def _aspecto_parse(session: Session, context: dict[str, Any], setor_tipo: str, form_data: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_rows = _build_aspecto_item_rows(session, context, setor_tipo)
    base_rows_by_reference = {row["reference"]: row for row in base_rows}
    max_order = max((int(row.get("order") or 0) for row in base_rows), default=0)
    dynamic_references: set[str] = set()
    for field_key in ("cis", "cod_posicao", "local", "anomalia", "lado", "geracao", "quantidade", "row_observation"):
        prefix = f"{field_key}_{setor_tipo}_"
        for form_key in form_data.keys():
            if str(form_key).startswith(prefix):
                dynamic_references.add(str(form_key)[len(prefix):])
    for reference in sorted(dynamic_references):
        if reference in base_rows_by_reference:
            continue
        max_order += 1
        base_rows.append(
            {
                "reference": reference,
                "order": max_order,
                "item_id": None,
                "item_observation": "",
                "cis": "",
                "cod_posicao": "",
                "local": "",
                "anomalia": "",
                "lado": "",
                "geracao": "",
                "quantidade": "",
                "row_observation": "",
                "value": "",
                "status_label": "Linha vazia",
                "flag": False,
                "is_applicable": True,
                "applicability_label": "Aplicável",
            }
        )
    base_rows_by_reference = {row["reference"]: row for row in base_rows}
    rows: list[dict[str, Any]] = []
    total_quantidade = 0
    for base_row in base_rows:
        if not base_row.get("is_applicable"):
            rows.append(dict(base_row))
            continue
        reference = base_row["reference"]
        cis = (form_data.get(f"cis_{setor_tipo}_{reference}") or "").strip()
        cod_posicao = (form_data.get(f"cod_posicao_{setor_tipo}_{reference}") or "").strip()
        local = (form_data.get(f"local_{setor_tipo}_{reference}") or "").strip()
        anomalia = (form_data.get(f"anomalia_{setor_tipo}_{reference}") or "").strip()
        lado = (form_data.get(f"lado_{setor_tipo}_{reference}") or "").strip()
        geracao = (form_data.get(f"geracao_{setor_tipo}_{reference}") or "").strip()
        quantidade = (form_data.get(f"quantidade_{setor_tipo}_{reference}") or "").strip()
        row_observation = (form_data.get(f"row_observation_{setor_tipo}_{reference}") or "").strip()
        if not any([cis, cod_posicao, local, anomalia, lado, geracao, quantidade]):
            required_base_row = reference in base_rows_by_reference and int(base_row.get("order") or 0) <= 5
            if required_base_row:
                rows.append(dict(base_rows_by_reference[reference]))
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
            raise OperationalModuleValidationError(f"Complete a linha {reference}: {', '.join(missing)}.")
        try:
            quantidade_int = int(quantidade)
        except ValueError as error:
            raise OperationalModuleValidationError(f"Quantidade inválida na linha {reference}.") from error
        total_quantidade += quantidade_int
        rows.append(
            {
                "reference": reference,
                "order": base_row["order"],
                "cis": cis,
                "cod_posicao": cod_posicao,
                "local": local,
                "anomalia": anomalia,
                "lado": lado,
                "geracao": geracao,
                "quantidade": str(quantidade_int),
                "row_observation": row_observation,
                "value": anomalia,
                "status_label": "Registrado",
                "flag": False,
            }
        )
    if not any(row.get("cis") for row in rows) and any(row.get("is_applicable") for row in rows):
        raise OperationalModuleValidationError("Adicione ao menos uma linha para o lote do setor.")
    summary = _summarize_rows(rows)
    summary["flag_count"] = 0
    summary["total_quantidade"] = total_quantidade
    return rows, summary


MODULE_CONFIGS: dict[str, ModuleConfig] = {
    "pt": ModuleConfig(
        code="pt",
        slug="pt",
        title="PT",
        description="Controle operacional de Pré-Tratamento em turno dedicado.",
        history_title="Histórico consolidado · PT",
        report_title="Relatório consolidado · PT",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("turno", "Turno", "select", True, "turnos"),
        ),
        columns=(
            TableColumn("operacao", "Operação / Equipamento"),
            TableColumn("descricao", "Descrição do controle"),
            TableColumn("norma", "Norma"),
            TableColumn("parametro", "Parâmetro"),
            TableColumn("numero_coleta", "Nr da Coleta"),
            TableColumn("value", "Valor", "input"),
            TableColumn("row_observation", "Observação", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_pt_rows,
        parse_rows=_pt_parse,
        legacy_history_builder=lambda _session: [],
        legacy_detail_loader=lambda _session, _legacy_id: None,
        legacy_detail_template="modules/legacy_detail.html",
        sector_sequence=(SETOR_PTED,),
        supports_turno=True,
    ),
    "pressao-filtros-pt": ModuleConfig(
        code="pressao-filtros-pt",
        slug="pressao-filtros-pt",
        title="Pressão nos Filtros",
        description="Leitura dos filtros do processo PT.",
        history_title="Histórico consolidado · Pressão nos Filtros PT",
        report_title="Relatório consolidado · Pressão nos Filtros PT",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("turno", "Turno", "select", True, "turnos"),
        ),
        columns=(
            TableColumn("label", "ITEM"),
            TableColumn("value", "VALOR", "input"),
            TableColumn("row_observation", "OBSERVAÇÃO", "input"),
        ),
        default_rows_builder=_pt_pressao_rows,
        parse_rows=_pt_pressao_parse,
        legacy_history_builder=lambda _session: [],
        legacy_detail_loader=lambda _session, _legacy_id: None,
        legacy_detail_template="modules/legacy_detail.html",
        sector_sequence=(SETOR_PTED,),
        supports_turno=True,
    ),
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
            TableColumn("row_observation", "Observação", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_build_temperatura_item_rows,
        parse_rows=_temperatura_parse,
        legacy_history_builder=_legacy_temp_history,
        legacy_detail_loader=temperatura_forno_service.get_lancamento,
        legacy_detail_template="temperatura_forno_ed/detail.html",
        sector_sequence=(SETOR_PTED,),
    ),
    "pressao-filtros-ed": ModuleConfig(
        code="pressao-filtros-ed",
        slug="pressao-filtros-ed",
        title="Pressão dos Filtros",
        description="Leitura dos 24 filtros com alarmes calculados por setor e consolidado geral do contexto.",
        history_title="Histórico consolidado · Pressão dos Filtros",
        report_title="Relatório · Pressão dos Filtros",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("turno", "Turno", "select", True, "turnos"),
        ),
        columns=(
            TableColumn("label", "Filtro"),
            TableColumn("expected", "Limite"),
            TableColumn("value", "Pressão (bar)", "input"),
            TableColumn("row_observation", "Observação", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_build_pressao_item_rows,
        parse_rows=_pressao_parse,
        legacy_history_builder=_legacy_pressao_history,
        legacy_detail_loader=pressao_filtros_service.get_lancamento,
        legacy_detail_template="pressao_filtros_ed/detail.html",
        sector_sequence=(SETOR_PTED,),
        supports_turno=True,
    ),
    "tensao-retificadores-ed": ModuleConfig(
        code="tensao-retificadores-ed",
        slug="tensao-retificadores-ed",
        title="Tensão dos Retificadores",
        description="Controle das 29 zonas dos retificadores por data, turno e modelo em duas abas setoriais.",
        history_title="Histórico consolidado · Tensão dos Retificadores",
        report_title="Relatório · Tensão dos Retificadores",
        context_fields=(
            ContextField("data_referencia", "Data", "date", True),
            ContextField("turno", "Turno", "select", True, "turnos"),
            ContextField("modelo", "Modelo", "select", True, "modelos"),
        ),
        columns=(
            TableColumn("label", "Zona"),
            TableColumn("expected", "Faixa"),
            TableColumn("value", "Tensão (V)", "input"),
            TableColumn("row_observation", "Observação", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_build_tensao_item_rows,
        parse_rows=_tensao_parse,
        legacy_history_builder=_legacy_tensao_history,
        legacy_detail_loader=tensao_retificadores_service.get_lancamento,
        legacy_detail_template="tensao_retificadores_ed/detail.html",
        sector_sequence=(SETOR_PTED,),
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
            TableColumn("value", "ECOAT"),
            TableColumn("zinco", "Zinco", "input"),
            TableColumn("total", "Total", "input"),
            TableColumn("row_observation", "Observação", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_build_poder_item_rows,
        parse_rows=_poder_parse,
        legacy_history_builder=_legacy_poder_history,
        legacy_detail_loader=poder_penetracao_service.get_lancamento,
        legacy_detail_template="poder_penetracao/detail.html",
        sector_sequence=(SETOR_PTED,),
        frequency="weekly",
    ),
    "espessura-ed": ModuleConfig(
        code="espessura-ed",
        slug="espessura-ed",
        title="Espessura",
        description="Rastreabilidade de 38 pontos por contexto, com salvamento independente por PTED e Laboratório.",
        history_title="Histórico consolidado · Espessura",
        report_title="Relatório · Espessura",
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
            TableColumn("row_observation", "Observação", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_build_espessura_item_rows,
        parse_rows=_espessura_parse,
        legacy_history_builder=_legacy_espessura_history,
        legacy_detail_loader=espessura_ed_service.get_lancamento,
        legacy_detail_template="espessura_ed/detail.html",
        sector_sequence=(SETOR_PTED,),
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
            TableColumn("row_observation", "Observação", "input"),
        ),
        default_rows_builder=_build_aspecto_item_rows,
        parse_rows=_aspecto_parse,
        legacy_history_builder=_legacy_aspecto_history,
        legacy_detail_loader=aspecto_service.get_lancamento,
        legacy_detail_template="aspecto/detail.html",
        sector_sequence=(SETOR_PTED,),
        supports_turno=True,
    ),
    "rugosidade": ModuleConfig(
        code="rugosidade",
        slug="rugosidade",
        title="Rugosidade",
        description="Matriz fixa por sequência com controle do Laboratório e consolidação automática do módulo.",
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
            TableColumn("row_observation", "Observação", "input"),
            TableColumn("status_label", "Status", "status"),
        ),
        default_rows_builder=_build_rugosidade_item_rows,
        parse_rows=_rugosidade_parse,
        legacy_history_builder=_legacy_rugosidade_history,
        legacy_detail_loader=rugosidade_service.get_lancamento,
        legacy_detail_template="rugosidade/detail.html",
        sector_sequence=(SETOR_LAB,),
    ),
}


def get_module_config(module_key: str) -> ModuleConfig:
    config = MODULE_CONFIGS.get(module_key)
    if config is None:
        raise OperationalModuleValidationError(f"Módulo inválido: {module_key}.")
    return config


# =============================================================================
# TURNO OPERACIONAL - Visão consolidada dos 8 módulos
# =============================================================================

FREQUENCY_LABELS = {
    "daily": "Diário",
    "weekly": "Semanal",
    "conditional": "Condicional",
}


def build_shift_overview(
    session: Session,
    data_referencia: date,
    turno: str | None = None,
) -> dict[str, Any]:
    """
    Monta visão consolidada de todos os módulos para um turno/dia específico.
    Retorna status de cada módulo sem criar registros.
    """
    if not operational_schema_available(session):
        return {"modules": [], "data": data_referencia, "turno": turno}

    modules_overview = []
    for code, config in MODULE_CONFIGS.items():
        # Busca registro existente para este módulo no contexto
        context = {"data_referencia": data_referencia}
        if config.supports_turno and turno:
            context["turno"] = turno

        master = get_master_by_context(session, config, context)

        pted = _find_sector(master, SETOR_PTED) if master else None
        lab = _find_sector(master, SETOR_LAB) if master else None

        # Determina ação principal
        if master is None:
            action = "iniciar"
            action_label = "Iniciar"
        elif master.status_geral == MODULE_STATUS_CONCLUIDO:
            action = "visualizar"
            action_label = "Visualizar"
        else:
            action = "continuar"
            action_label = "Continuar"

        modules_overview.append({
            "code": code,
            "slug": config.slug,
            "title": config.title,
            "description": config.description,
            "frequency": config.frequency,
            "frequency_label": FREQUENCY_LABELS.get(config.frequency, config.frequency),
            "supports_turno": config.supports_turno,
            "record_id": master.id if master else None,
            "status_geral": master.status_geral if master else MODULE_STATUS_NAO_INICIADO,
            "status_geral_label": STATUS_LABELS.get(
                master.status_geral if master else MODULE_STATUS_NAO_INICIADO,
                "Não iniciado"
            ),
            "status_pted": pted.status_setor if pted else SETOR_STATUS_NAO_INICIADO,
            "status_pted_label": STATUS_LABELS.get(
                pted.status_setor if pted else SETOR_STATUS_NAO_INICIADO,
                "Não iniciado"
            ),
            "status_lab": lab.status_setor if lab else SETOR_STATUS_NAO_INICIADO,
            "status_lab_label": STATUS_LABELS.get(
                lab.status_setor if lab else SETOR_STATUS_NAO_INICIADO,
                "Não iniciado"
            ),
            "action": action,
            "action_label": action_label,
            "desvios": sum(
                int((s.metricas or {}).get("flag_count", 0))
                for s in (master.setores if master else [])
            ),
        })

    # Calcula status geral do turno
    total = len(modules_overview)
    concluidos = sum(1 for m in modules_overview if m["status_geral"] == MODULE_STATUS_CONCLUIDO)
    em_andamento = sum(1 for m in modules_overview if m["status_geral"] in (MODULE_STATUS_EM_ANDAMENTO, MODULE_STATUS_PARCIAL))

    if concluidos == total:
        shift_status = MODULE_STATUS_CONCLUIDO
    elif concluidos > 0 or em_andamento > 0:
        shift_status = MODULE_STATUS_EM_ANDAMENTO
    else:
        shift_status = MODULE_STATUS_NAO_INICIADO

    return {
        "data": data_referencia,
        "data_label": data_referencia.strftime("%d/%m/%Y"),
        "turno": turno,
        "modules": modules_overview,
        "status_geral": shift_status,
        "status_geral_label": STATUS_LABELS.get(shift_status, "Não iniciado"),
        "total_modules": total,
        "concluidos": concluidos,
        "em_andamento": em_andamento,
        "nao_iniciados": total - concluidos - em_andamento,
    }


def build_general_history(
    session: Session,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    turno: str | None = None,
    module_code: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Histórico geral agrupado por data/turno, mostrando status de cada módulo.
    """
    if not operational_schema_available(session):
        return []

    # Busca todos os registros com filtros
    statement: Select[tuple[OperationalModuleRecord]] = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores))
        .order_by(
            OperationalModuleRecord.data_referencia.desc(),
            OperationalModuleRecord.turno.desc(),
            OperationalModuleRecord.updated_at.desc(),
        )
    )

    if data_inicio:
        statement = statement.where(OperationalModuleRecord.data_referencia >= data_inicio)
    if data_fim:
        statement = statement.where(OperationalModuleRecord.data_referencia <= data_fim)
    if turno:
        statement = statement.where(OperationalModuleRecord.turno == turno)
    if module_code:
        statement = statement.where(OperationalModuleRecord.module_code == module_code)
    if status:
        statement = statement.where(OperationalModuleRecord.status_geral == status)

    records = list(session.scalars(statement.limit(limit * 10)).unique().all())

    # Agrupa por data/turno
    shifts: dict[str, dict[str, Any]] = {}
    for record in records:
        shift_key = f"{record.data_referencia.isoformat()}|{record.turno or 'geral'}"
        if shift_key not in shifts:
            shifts[shift_key] = {
                "data": record.data_referencia,
                "data_label": record.data_referencia.strftime("%d/%m/%Y"),
                "turno": record.turno,
                "modules": {},
                "records": [],
            }

        config = MODULE_CONFIGS.get(record.module_code)
        if config:
            pted = _find_sector(record, SETOR_PTED)
            lab = _find_sector(record, SETOR_LAB)
            shifts[shift_key]["modules"][record.module_code] = {
                "id": record.id,
                "title": config.title,
                "slug": config.slug,
                "status_geral": record.status_geral,
                "status_geral_label": STATUS_LABELS.get(record.status_geral, record.status_geral),
                "status_pted": pted.status_setor if pted else SETOR_STATUS_NAO_INICIADO,
                "status_lab": lab.status_setor if lab else SETOR_STATUS_NAO_INICIADO,
                "context_label": context_label(config, record.context_data),
            }
            shifts[shift_key]["records"].append(record)

    # Converte para lista ordenada
    result = []
    for shift_key in sorted(shifts.keys(), reverse=True):
        shift = shifts[shift_key]
        total = len(shift["modules"])
        concluidos = sum(
            1 for m in shift["modules"].values()
            if m["status_geral"] == MODULE_STATUS_CONCLUIDO
        )
        shift["total_modules"] = total
        shift["concluidos"] = concluidos
        shift["status_geral"] = MODULE_STATUS_CONCLUIDO if concluidos == total and total > 0 else (
            MODULE_STATUS_EM_ANDAMENTO if total > 0 else MODULE_STATUS_NAO_INICIADO
        )
        shift["status_geral_label"] = STATUS_LABELS.get(shift["status_geral"], "")
        result.append(shift)
        if len(result) >= limit:
            break

    return result


def list_all_modules() -> list[dict[str, Any]]:
    """Retorna lista de todos os módulos configurados."""
    return [
        {
            "code": config.code,
            "slug": config.slug,
            "title": config.title,
            "description": config.description,
            "frequency": config.frequency,
            "frequency_label": FREQUENCY_LABELS.get(config.frequency, config.frequency),
            "supports_turno": config.supports_turno,
        }
        for config in MODULE_CONFIGS.values()
    ]



