from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import ItemED, Modelo, Responsavel, Setor, Turno


@dataclass(frozen=True)
class FieldConfig:
    name: str
    label: str
    required: bool = False
    input_type: str = "text"
    placeholder: str = ""
    rows: int | None = None


@dataclass(frozen=True)
class EntityConfig:
    key: str
    title: str
    model: type
    fields: tuple[FieldConfig, ...]
    list_fields: tuple[str, ...]
    default_sort: tuple[str, ...]


ADMIN_ENTITIES: dict[str, EntityConfig] = {
    "responsaveis": EntityConfig(
        key="responsaveis",
        title="Responsáveis",
        model=Responsavel,
        fields=(
            FieldConfig("nome", "Nome", required=True, placeholder="Ex.: Laboratório"),
            FieldConfig("descricao", "Descrição", input_type="textarea", placeholder="Detalhes do papel operacional.", rows=3),
            FieldConfig("ativo", "Ativo", input_type="checkbox"),
        ),
        list_fields=("nome", "descricao", "ativo"),
        default_sort=("nome",),
    ),
    "modelos": EntityConfig(
        key="modelos",
        title="Modelos",
        model=Modelo,
        fields=(
            FieldConfig("nome", "Nome", required=True, placeholder="Ex.: Capô H1"),
            FieldConfig("codigo", "Código", placeholder="Ex.: H1"),
            FieldConfig("ativo", "Ativo", input_type="checkbox"),
        ),
        list_fields=("nome", "codigo", "ativo"),
        default_sort=("nome",),
    ),
    "setores": EntityConfig(
        key="setores",
        title="Setores",
        model=Setor,
        fields=(
            FieldConfig("nome", "Nome", required=True, placeholder="Ex.: PT/ED"),
            FieldConfig("sigla", "Sigla", placeholder="Ex.: PTED"),
            FieldConfig("ativo", "Ativo", input_type="checkbox"),
        ),
        list_fields=("nome", "sigla", "ativo"),
        default_sort=("nome",),
    ),
    "turnos": EntityConfig(
        key="turnos",
        title="Turnos",
        model=Turno,
        fields=(
            FieldConfig("nome", "Nome", required=True, placeholder="Ex.: Turno 1"),
            FieldConfig("codigo", "Código", placeholder="Ex.: 1"),
            FieldConfig("ativo", "Ativo", input_type="checkbox"),
        ),
        list_fields=("nome", "codigo", "ativo"),
        default_sort=("nome",),
    ),
    "itens-ed": EntityConfig(
        key="itens-ed",
        title="Itens ED",
        model=ItemED,
        fields=(
            FieldConfig("operacao_equipamento", "Operação / equipamento", required=True),
            FieldConfig("descricao_controle", "Descrição do controle", required=True),
            FieldConfig("norma", "Norma"),
            FieldConfig("parametro", "Parâmetro"),
            FieldConfig("frequencia", "Frequência"),
            FieldConfig("responsavel_padrao", "Responsável padrão"),
            FieldConfig("setor_padrao", "Setor padrão"),
            FieldConfig("turno_padrao", "Turno padrão"),
            FieldConfig("numero_coleta", "Número da coleta", input_type="number"),
            FieldConfig("ordem_exibicao", "Ordem de exibição", input_type="number"),
            FieldConfig("observacao", "Observação", input_type="textarea", rows=3),
            FieldConfig("ativo", "Ativo", input_type="checkbox"),
        ),
        list_fields=(
            "operacao_equipamento",
            "descricao_controle",
            "frequencia",
            "turno_padrao",
            "numero_coleta",
            "ativo",
        ),
        default_sort=("ordem_exibicao", "operacao_equipamento"),
    ),
}


def get_entity_config(entity: str) -> EntityConfig:
    config = ADMIN_ENTITIES.get(entity)
    if config is None:
        raise KeyError(entity)
    return config


def list_records(session: Session, entity: str) -> list:
    config = get_entity_config(entity)
    model = config.model
    statement: Select = select(model)
    for field_name in config.default_sort:
        statement = statement.order_by(getattr(model, field_name))
    return list(session.scalars(statement).all())


def get_record(session: Session, entity: str, record_id: int):
    config = get_entity_config(entity)
    return session.get(config.model, record_id)


def _normalize_value(field: FieldConfig, raw_value: str | None):
    if field.input_type == "checkbox":
        return raw_value == "on"
    if raw_value is None:
        return None
    value = raw_value.strip()
    if value == "":
        return None if field.input_type != "number" else None
    if field.input_type == "number":
        return int(value)
    return value


def payload_from_form(config: EntityConfig, form_data) -> dict:
    payload = {}
    for field in config.fields:
        if field.input_type == "checkbox":
            payload[field.name] = form_data.get(field.name)
        else:
            payload[field.name] = form_data.get(field.name)
    normalized = {field.name: _normalize_value(field, payload.get(field.name)) for field in config.fields}
    if "ativo" in normalized and normalized["ativo"] is None:
        normalized["ativo"] = False
    if config.key == "itens-ed" and normalized.get("ordem_exibicao") is None:
        normalized["ordem_exibicao"] = 0
    return normalized


def create_record(session: Session, entity: str, payload: dict):
    config = get_entity_config(entity)
    record = config.model(**payload)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def update_record(session: Session, entity: str, record_id: int, payload: dict):
    record = get_record(session, entity, record_id)
    if record is None:
        return None
    for key, value in payload.items():
        setattr(record, key, value)
    session.commit()
    session.refresh(record)
    return record


def delete_record(session: Session, entity: str, record_id: int) -> bool:
    record = get_record(session, entity, record_id)
    if record is None:
        return False
    session.delete(record)
    session.commit()
    return True


def field_labels(fields: Iterable[str], config: EntityConfig) -> dict[str, str]:
    mapping = {field.name: field.label for field in config.fields}
    return {field: mapping.get(field, field.replace("_", " ").title()) for field in fields}
