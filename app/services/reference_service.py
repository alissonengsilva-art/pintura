from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models import Modelo, OperationalModuleItem, Responsavel, Setor, Turno


@dataclass(frozen=True)
class FieldConfig:
    name: str
    label: str
    required: bool = False
    input_type: str = "text"
    placeholder: str = ""
    rows: int | None = None
    options_key: str | None = None


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
        title="Responsaveis",
        model=Responsavel,
        fields=(
            FieldConfig("nome", "Nome", required=True, placeholder="Ex.: Joao da Silva"),
            FieldConfig("setor_id", "Setor", required=True, input_type="select", options_key="setores"),
        ),
        list_fields=("nome", "setor_nome"),
        default_sort=("nome",),
    ),
    "modelos": EntityConfig(
        key="modelos",
        title="Modelos",
        model=Modelo,
        fields=(
            FieldConfig("nome", "Nome", required=True, placeholder="Ex.: Capo H1"),
            FieldConfig("codigo", "Codigo", placeholder="Ex.: H1"),
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
            FieldConfig("codigo", "Codigo", placeholder="Ex.: 1"),
            FieldConfig("ativo", "Ativo", input_type="checkbox"),
        ),
        list_fields=("nome", "codigo", "ativo"),
        default_sort=("nome",),
    ),
    "modulos-itens": EntityConfig(
        key="modulos-itens",
        title="Itens dos modulos",
        model=OperationalModuleItem,
        fields=(
            FieldConfig("escopo", "Escopo", placeholder="Ex.: ed, sigilatura, central_tintas"),
            FieldConfig("modulo", "Modulo", placeholder="Ex.: temperatura-forno-ed"),
            FieldConfig("aba", "Aba", placeholder="Ex.: PTED, Laboratorio, Manual"),
            FieldConfig("module_code", "Modulo", required=True, placeholder="Ex.: ed"),
            FieldConfig("setor_tipo", "Setor", required=True, placeholder="PTED, LABORATORIO ou AMBOS"),
            FieldConfig("operacao", "Operacao"),
            FieldConfig("controle", "Controle", required=True),
            FieldConfig("norma", "Norma"),
            FieldConfig("parametro", "Parametro"),
            FieldConfig("parametro_exibicao", "Parametro exibicao"),
            FieldConfig("referencia_visual", "Referencia visual"),
            FieldConfig("unidade", "Unidade"),
            FieldConfig("tipo_validacao", "Tipo validacao"),
            FieldConfig("limite_minimo", "Limite minimo", input_type="number"),
            FieldConfig("limite_maximo", "Limite maximo", input_type="number"),
            FieldConfig("valor_min", "Valor minimo", input_type="number"),
            FieldConfig("valor_max", "Valor maximo", input_type="number"),
            FieldConfig("ordem", "Ordem", input_type="number"),
            FieldConfig("frequencia", "Frequencia"),
            FieldConfig("responsavel_padrao", "Responsavel padrao"),
            FieldConfig("turno_padrao", "Turno padrao"),
            FieldConfig("numero_coleta", "Numero da coleta", input_type="number"),
            FieldConfig("observacao", "Observacao", input_type="textarea", rows=3),
            FieldConfig("obrigatorio", "Obrigatorio", input_type="checkbox"),
            FieldConfig("ativo", "Ativo", input_type="checkbox"),
        ),
        list_fields=("escopo", "modulo", "aba", "controle", "parametro_exibicao", "tipo_validacao", "ordem", "ativo"),
        default_sort=("module_code", "ordem"),
    ),
}


def get_entity_config(entity: str) -> EntityConfig:
    config = ADMIN_ENTITIES.get(entity)
    if config is None:
        raise KeyError(entity)
    return config


def list_records(session: Session, entity: str, filters: dict | None = None) -> list:
    config = get_entity_config(entity)
    model = config.model
    statement: Select = select(model)
    filters = filters or {}
    if entity == "responsaveis":
        statement = statement.options(selectinload(Responsavel.setor))
    if entity == "modulos-itens":
        module_code = str(filters.get("module_code") or "").strip()
        if module_code:
            statement = statement.where(model.module_code == module_code)
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
    if field.input_type == "select":
        return int(value)
    if field.input_type == "number":
        if any(marker in value for marker in [".", ","]):
            return float(value.replace(",", "."))
        return int(value)
    return value


def payload_from_form(config: EntityConfig, form_data) -> dict:
    payload = {}
    for field in config.fields:
        payload[field.name] = form_data.get(field.name)
    normalized = {field.name: _normalize_value(field, payload.get(field.name)) for field in config.fields}
    if config.key == "responsaveis":
        normalized["ativo"] = True
        normalized["descricao"] = None
    elif "ativo" in normalized and normalized["ativo"] is None:
        normalized["ativo"] = False
    if "obrigatorio" in normalized and normalized["obrigatorio"] is None:
        normalized["obrigatorio"] = False
    if config.key == "modulos-itens" and normalized.get("ordem") is None:
        normalized["ordem"] = 0
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
    if config.key == "responsaveis":
        mapping["setor_nome"] = "Setor"
    return {field: mapping.get(field, field.replace("_", " ").title()) for field in fields}
