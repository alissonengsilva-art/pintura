from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import inspect, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CABINE_PINTURA_STATUS_CONCLUIDO,
    CABINE_PINTURA_STATUS_EM_ANDAMENTO,
    CabinePinturaItem,
    CabinePinturaRelatorio,
    OperationalModuleItem,
)
from app.services.cabine_pintura_seed import (
    CABINE_PINTURA_ABAS,
    CABINE_PINTURA_ABA_DATA_PAQ,
    CABINE_PINTURA_ABA_TEMPERATURA_FORNO,
    CABINE_PINTURA_ABA_TOP_COAT,
)


class CabinePinturaValidationError(ValueError):
    pass


ITEM_KEY_PATTERN = re.compile(r"^item_(-?\d+)_(.+)$")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def cabine_pintura_flow_schema_available(session: Session) -> bool:
    inspector = inspect(session.get_bind())
    return inspector.has_table("cabine_pintura_relatorios") and inspector.has_table("cabine_pintura_itens")


def _clean_text(value: Any, *, max_len: int | None = None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if max_len is not None:
        return text[:max_len]
    return text


def _parse_date(value: Any) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise CabinePinturaValidationError("Informe a data.")
    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise CabinePinturaValidationError("Data invalida.") from error


def _week_label(value: date) -> str:
    return f"Semana {value.isocalendar().week:02d}"


def _month_label(value: date) -> str:
    return value.strftime("%m/%Y")


def _status_label(status: str) -> str:
    return "Concluido" if status == CABINE_PINTURA_STATUS_CONCLUIDO else "Em andamento"


def _item_status_label(status: str | None) -> str:
    return "Preenchido" if str(status or "").strip().upper() == "PREENCHIDO" else "Pendente"


def _progress_status(total: int, filled: int) -> tuple[str, str]:
    if total <= 0:
        return ("nao-iniciado", "Nao iniciado")
    if filled >= total:
        return ("concluido", "Concluido")
    if filled > 0:
        return ("em-andamento", "Em andamento")
    return ("nao-iniciado", "Nao iniciado")


def _catalog_items(session: Session, turno: str | None = None) -> list[OperationalModuleItem]:
    statement = (
        select(OperationalModuleItem)
        .where(OperationalModuleItem.ativo.is_(True))
        .where(
            (OperationalModuleItem.module_code == "cabine-pintura")
            | (
                (OperationalModuleItem.escopo == "cabine_pintura")
                & (OperationalModuleItem.modulo == "cabine-pintura")
            )
        )
    )
    if turno:
        statement = statement.where(
            or_(
                OperationalModuleItem.turno_padrao.is_(None),
                OperationalModuleItem.turno_padrao == "",
                OperationalModuleItem.turno_padrao == "TODOS",
                OperationalModuleItem.turno_padrao == turno,
            )
        )
    return list(session.scalars(statement.order_by(OperationalModuleItem.aba, OperationalModuleItem.ordem, OperationalModuleItem.id)).all())


def _load_relatorio(session: Session, relatorio_id: int) -> CabinePinturaRelatorio | None:
    return session.scalars(
        select(CabinePinturaRelatorio)
        .options(joinedload(CabinePinturaRelatorio.itens))
        .where(CabinePinturaRelatorio.id == relatorio_id)
    ).unique().first()


def get_relatorio(session: Session, relatorio_id: int) -> CabinePinturaRelatorio | None:
    if not cabine_pintura_flow_schema_available(session):
        return None
    return _load_relatorio(session, relatorio_id)


def list_relatorios(session: Session) -> list[dict[str, Any]]:
    if not cabine_pintura_flow_schema_available(session):
        return []
    rows = list(
        session.scalars(
            select(CabinePinturaRelatorio)
            .options(joinedload(CabinePinturaRelatorio.itens))
            .order_by(
                CabinePinturaRelatorio.status.asc(),
                CabinePinturaRelatorio.data_controle.desc(),
                CabinePinturaRelatorio.updated_at.desc(),
            )
        ).unique().all()
    )
    return [
        {
            "id": row.id,
            "data_label": row.data_controle.strftime("%d/%m/%Y"),
            "turno": row.turno,
            "responsavel": row.responsavel,
            "status": row.status,
            "status_label": _status_label(row.status),
            "itens_count": len(row.itens),
            "updated_label": row.updated_at.strftime("%d/%m/%Y %H:%M") if row.updated_at else "-",
        }
        for row in rows
    ]


def create_relatorio(session: Session, payload: dict[str, Any]) -> CabinePinturaRelatorio:
    if not cabine_pintura_flow_schema_available(session):
        raise CabinePinturaValidationError("Estrutura do fluxo da Cabine de Pintura nao instalada. Execute as migrations.")

    data_referencia = _parse_date(payload.get("data_referencia"))
    turno = _clean_text(payload.get("turno"), max_len=20)
    responsavel = _clean_text(payload.get("responsavel"), max_len=120)
    if not turno:
        raise CabinePinturaValidationError("Selecione o turno.")
    if not responsavel:
        raise CabinePinturaValidationError("Selecione o responsavel.")

    existing = session.scalars(
        select(CabinePinturaRelatorio)
        .where(CabinePinturaRelatorio.data_controle == data_referencia)
        .where(CabinePinturaRelatorio.turno == turno)
    ).first()
    if existing is not None:
        raise CabinePinturaValidationError("Ja existe um turno da Cabine de Pintura para esta data e turno.")

    relatorio = CabinePinturaRelatorio(
        data_controle=data_referencia,
        semana=_week_label(data_referencia),
        mes=_month_label(data_referencia),
        responsavel=responsavel,
        turno=turno,
        status=CABINE_PINTURA_STATUS_EM_ANDAMENTO,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(relatorio)
    session.flush()

    catalog_items = _catalog_items(session, turno)
    if not catalog_items:
        raise CabinePinturaValidationError("Nenhum item ativo foi configurado para a Cabine de Pintura.")

    for catalog_item in catalog_items:
        session.add(
            CabinePinturaItem(
                cabine_pintura_id=relatorio.id,
                operational_module_item_id=catalog_item.id,
                modulo=catalog_item.aba or CABINE_PINTURA_ABA_TOP_COAT,
                operacao_equipamento=catalog_item.operacao,
                descricao_controle=catalog_item.controle,
                norma=catalog_item.norma,
                parametro=catalog_item.parametro_exibicao or catalog_item.parametro,
                status="NAO_AVALIADO",
                created_at=_now(),
                updated_at=_now(),
            )
        )

    session.commit()
    return _load_relatorio(session, relatorio.id) or relatorio


def build_relatorio_context(session: Session, relatorio: CabinePinturaRelatorio) -> dict[str, Any]:
    catalog_item_map: dict[int, OperationalModuleItem] = {}
    item_ids = [item.operational_module_item_id for item in relatorio.itens if item.operational_module_item_id]
    if item_ids:
        catalog_item_map = {
            item.id: item
            for item in session.scalars(select(OperationalModuleItem).where(OperationalModuleItem.id.in_(item_ids))).all()
        }

    rendered_items: list[dict[str, Any]] = []
    grouped_rows: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    preenchidos = 0
    total_items = len(relatorio.itens)

    for item in relatorio.itens:
        catalog_item = catalog_item_map.get(item.operational_module_item_id or 0)
        modulo = str(item.modulo or (catalog_item.aba if catalog_item else "") or CABINE_PINTURA_ABA_TOP_COAT).strip()
        operacao = str(item.operacao_equipamento or (catalog_item.operacao if catalog_item else "") or "Sem agrupamento").strip()
        valor = _clean_text(item.valor)
        status = "PREENCHIDO" if valor else "NAO_AVALIADO"
        if valor:
            preenchidos += 1
        row = {
            "id": item.id,
            "modulo": modulo,
            "operacao": operacao,
            "controle": item.descricao_controle,
            "norma": item.norma,
            "parametro": item.parametro,
            "valor": item.valor,
            "observacao": item.observacao,
            "status": status,
            "status_label": _item_status_label(status),
        }
        rendered_items.append(row)
        grouped_rows[modulo][operacao].append(row)

    aba_views: list[dict[str, Any]] = []
    for aba in CABINE_PINTURA_ABAS:
        groups = grouped_rows.get(aba, {})
        aba_items = [group_item for items in groups.values() for group_item in items]
        aba_total = len(aba_items)
        aba_filled = sum(1 for group_item in aba_items if str(group_item.get("valor") or "").strip())
        aba_percent = int(round((aba_filled / aba_total) * 100)) if aba_total > 0 else 0
        status_key, status_label = _progress_status(aba_total, aba_filled)
        aba_views.append(
            {
                "code": _aba_code(aba),
                "label": aba,
                "groups": [{"operacao": operacao, "items": items} for operacao, items in groups.items()],
                "items_count": aba_total,
                "filled": aba_filled,
                "percent": aba_percent,
                "status_key": status_key,
                "status_label": status_label,
            }
        )

    percentual = int(round((preenchidos / total_items) * 100)) if total_items > 0 else 0
    return {
        "id": relatorio.id,
        "data_label": relatorio.data_controle.strftime("%d/%m/%Y"),
        "data_referencia": relatorio.data_controle.isoformat(),
        "semana": relatorio.semana,
        "mes": relatorio.mes,
        "responsavel": relatorio.responsavel,
        "turno": relatorio.turno,
        "status": relatorio.status,
        "status_label": _status_label(relatorio.status),
        "abas": aba_views,
        "itens": rendered_items,
        "summary": {
            "total": total_items,
            "preenchidos": preenchidos,
            "pendentes": max(total_items - preenchidos, 0),
            "percentual": percentual,
            "progress_label": f"{preenchidos}/{total_items} itens preenchidos",
        },
    }


def save_relatorio(session: Session, relatorio_id: int, form_data: Any, submit_action: str) -> CabinePinturaRelatorio:
    relatorio = _load_relatorio(session, relatorio_id)
    if relatorio is None:
        raise CabinePinturaValidationError("Relatorio nao encontrado.")

    grouped_fields: dict[int, dict[str, Any]] = defaultdict(dict)
    for key, value in form_data.items():
        match = ITEM_KEY_PATTERN.match(str(key))
        if not match:
            continue
        grouped_fields[int(match.group(1))][match.group(2)] = value

    existing_items = {item.id: item for item in relatorio.itens}
    if not existing_items:
        raise CabinePinturaValidationError("Nenhum item de catalogo foi encontrado para este turno.")

    for item_id, item in existing_items.items():
        payload = grouped_fields.get(item_id, {})
        item.valor = _clean_text(payload.get("valor"), max_len=120)
        item.observacao = _clean_text(payload.get("observacao"))
        item.status = "PREENCHIDO" if item.valor else "NAO_AVALIADO"
        item.updated_at = _now()

    if submit_action == "concluir":
        pendentes = [item for item in existing_items.values() if not _clean_text(item.valor)]
        if pendentes:
            raise CabinePinturaValidationError("Existem itens pendentes. Preencha todos os valores antes de concluir.")

    relatorio.updated_at = _now()
    if submit_action == "concluir":
        relatorio.status = CABINE_PINTURA_STATUS_CONCLUIDO
        relatorio.concluded_at = _now()
    else:
        relatorio.status = CABINE_PINTURA_STATUS_EM_ANDAMENTO
    session.commit()
    return _load_relatorio(session, relatorio.id) or relatorio


def _aba_code(value: str) -> str:
    if value == CABINE_PINTURA_ABA_TEMPERATURA_FORNO:
        return "temperatura-forno"
    if value == CABINE_PINTURA_ABA_DATA_PAQ:
        return "data-paq"
    return "top-coat"
