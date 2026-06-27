from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CENTRAL_TINTAS_STATUS_CONCLUIDO,
    CENTRAL_TINTAS_STATUS_EM_ANDAMENTO,
    CentralTintasItem,
    CentralTintasRelatorio,
    OperationalModuleItem,
)


class CentralTintasValidationError(ValueError):
    pass


ITEM_KEY_PATTERN = re.compile(r"^item_(-?\d+)_(.+)$")
GENERIC_FIELDS = ("tinta", "lote", "ph", "viscosidade", "sujidade", "acoes_corretivas")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def central_tintas_schema_available(session: Session) -> bool:
    inspector = inspect(session.get_bind())
    return inspector.has_table("central_tintas_registros")


def central_tintas_flow_schema_available(session: Session) -> bool:
    inspector = inspect(session.get_bind())
    return inspector.has_table("central_tintas_relatorios") and inspector.has_table("central_tintas_itens")


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
        raise CentralTintasValidationError("Informe a data.")
    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise CentralTintasValidationError("Data invalida.") from error


def _week_label(value: date) -> str:
    week = value.isocalendar().week
    return f"Semana {week:02d}"


def _month_label(value: date) -> str:
    return value.strftime("%m/%Y")


def _status_label(status: str) -> str:
    return "Concluido" if status == CENTRAL_TINTAS_STATUS_CONCLUIDO else "Em andamento"


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


def _catalog_items(session: Session) -> list[OperationalModuleItem]:
    return list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.ativo.is_(True))
            .where(
                (OperationalModuleItem.module_code == "central-tintas")
                | (
                    (OperationalModuleItem.escopo == "central_tintas")
                    & (OperationalModuleItem.modulo == "central-tintas")
                )
            )
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )


def _load_relatorio(session: Session, relatorio_id: int) -> CentralTintasRelatorio | None:
    return session.scalars(
        select(CentralTintasRelatorio)
        .options(joinedload(CentralTintasRelatorio.itens))
        .where(CentralTintasRelatorio.id == relatorio_id)
    ).unique().first()


def get_relatorio(session: Session, relatorio_id: int) -> CentralTintasRelatorio | None:
    if not central_tintas_flow_schema_available(session):
        return None
    return _load_relatorio(session, relatorio_id)


def delete_relatorio(session: Session, relatorio: CentralTintasRelatorio) -> None:
    try:
        session.execute(delete(CentralTintasItem).where(CentralTintasItem.central_tintas_id == relatorio.id))
        session.execute(delete(CentralTintasRelatorio).where(CentralTintasRelatorio.id == relatorio.id))
        session.commit()
    except Exception:
        session.rollback()
        raise


def list_relatorios(session: Session) -> list[dict[str, Any]]:
    if not central_tintas_flow_schema_available(session):
        return []

    rows = list(
        session.scalars(
            select(CentralTintasRelatorio)
            .options(joinedload(CentralTintasRelatorio.itens))
            .order_by(
                CentralTintasRelatorio.status.asc(),
                CentralTintasRelatorio.data_controle.desc(),
                CentralTintasRelatorio.updated_at.desc(),
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


def create_relatorio(session: Session, payload: dict[str, Any]) -> CentralTintasRelatorio:
    if not central_tintas_flow_schema_available(session):
        raise CentralTintasValidationError("Estrutura do fluxo da Central de Tintas nao instalada. Execute as migrations.")

    data_referencia = _parse_date(payload.get("data_referencia"))
    turno = _clean_text(payload.get("turno"), max_len=20)
    responsavel = _clean_text(payload.get("responsavel"), max_len=120)
    if not turno:
        raise CentralTintasValidationError("Selecione o turno.")
    if not responsavel:
        raise CentralTintasValidationError("Selecione o responsavel.")

    existing = session.scalars(
        select(CentralTintasRelatorio)
        .where(CentralTintasRelatorio.data_controle == data_referencia)
        .where(CentralTintasRelatorio.turno == turno)
    ).first()
    if existing is not None:
        raise CentralTintasValidationError("Ja existe um turno da Central de Tintas para esta data e turno.")

    relatorio = CentralTintasRelatorio(
        data_controle=data_referencia,
        semana=_week_label(data_referencia),
        mes=_month_label(data_referencia),
        responsavel=responsavel,
        turno=turno,
        status=CENTRAL_TINTAS_STATUS_EM_ANDAMENTO,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(relatorio)
    session.flush()

    catalog_items = _catalog_items(session)
    if catalog_items:
        for catalog_item in catalog_items:
            session.add(
                CentralTintasItem(
                    central_tintas_id=relatorio.id,
                    operational_module_item_id=catalog_item.id,
                    controle=catalog_item.controle,
                    parametro=catalog_item.parametro_exibicao or catalog_item.parametro,
                    status="NAO_AVALIADO",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
    else:
        session.add(
            CentralTintasItem(
                central_tintas_id=relatorio.id,
                created_at=_now(),
                updated_at=_now(),
            )
        )

    session.commit()
    return _load_relatorio(session, relatorio.id) or relatorio


def build_relatorio_context(session: Session, relatorio: CentralTintasRelatorio) -> dict[str, Any]:
    catalog_mode = any(item.operational_module_item_id for item in relatorio.itens)
    catalog_item_map: dict[int, OperationalModuleItem] = {}
    if catalog_mode:
        item_ids = [item.operational_module_item_id for item in relatorio.itens if item.operational_module_item_id]
        if item_ids:
            catalog_item_map = {
                item.id: item
                for item in session.scalars(
                    select(OperationalModuleItem).where(OperationalModuleItem.id.in_(item_ids))
                ).all()
            }

    rendered_items = []
    preenchidos = 0
    pendentes = 0
    grouped_catalog_items: list[dict[str, Any]] = []
    tab_views: list[dict[str, Any]] = []
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ordered_groups: list[str] = []

    for item in relatorio.itens:
        catalog_item = catalog_item_map.get(item.operational_module_item_id or 0)
        operacao = str((catalog_item.operacao if catalog_item else None) or "").strip() or "Sem agrupamento"
        status = str(item.status or "").strip().upper() or "NAO_AVALIADO"
        if item.valor:
            preenchidos += 1
        else:
            pendentes += 1
        row = {
            "id": item.id,
            "operacao": operacao,
            "controle": item.controle,
            "parametro": item.parametro,
            "valor": item.valor,
            "observacao": item.observacao,
            "status": status,
            "status_label": _item_status_label(status),
            "tinta": item.tinta,
            "lote": item.lote,
            "ph": item.ph,
            "viscosidade": item.viscosidade,
            "sujidade": item.sujidade,
            "acoes_corretivas": item.acoes_corretivas,
        }
        rendered_items.append(row)
        if catalog_mode:
            if operacao not in grouped_rows:
                ordered_groups.append(operacao)
            grouped_rows[operacao].append(row)

    if catalog_mode:
        grouped_catalog_items = [
            {"operacao": operacao, "items": grouped_rows[operacao]}
            for operacao in ordered_groups
        ]
        for index, group in enumerate(grouped_catalog_items, start=1):
            group_total = len(group["items"])
            group_filled = sum(1 for group_item in group["items"] if str(group_item.get("valor") or "").strip())
            group_percent = int(round((group_filled / group_total) * 100)) if group_total > 0 else 0
            status_key, status_label = _progress_status(group_total, group_filled)
            tab_views.append(
                {
                    "code": f"grupo-{index}",
                    "title": group["operacao"],
                    "filled": group_filled,
                    "total": group_total,
                    "percent": group_percent,
                    "status_key": status_key,
                    "status_label": status_label,
                }
            )

    total_items = len(relatorio.itens)
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
        "mode": "catalog" if catalog_mode else "legacy",
        "itens": rendered_items,
        "grupos": grouped_catalog_items,
        "tabs": tab_views,
        "summary": {
            "total": total_items,
            "preenchidos": preenchidos,
            "pendentes": pendentes,
            "percentual": percentual,
            "progress_label": f"{preenchidos}/{total_items} itens preenchidos",
        },
    }


def save_relatorio(session: Session, relatorio_id: int, form_data: Any, submit_action: str) -> CentralTintasRelatorio:
    relatorio = _load_relatorio(session, relatorio_id)
    if relatorio is None:
        raise CentralTintasValidationError("Relatorio nao encontrado.")

    grouped_fields: dict[int, dict[str, Any]] = defaultdict(dict)
    for key, value in form_data.items():
        match = ITEM_KEY_PATTERN.match(str(key))
        if not match:
            continue
        grouped_fields[int(match.group(1))][match.group(2)] = value

    existing_items = {item.id: item for item in relatorio.itens}
    catalog_mode = any(item.operational_module_item_id for item in relatorio.itens)

    if catalog_mode:
        for item_id, item in existing_items.items():
            payload = grouped_fields.get(item_id, {})
            item.valor = _clean_text(payload.get("valor"), max_len=120)
            item.observacao = _clean_text(payload.get("observacao"))
            item.status = "PREENCHIDO" if item.valor else "NAO_AVALIADO"
            item.updated_at = _now()

        if not existing_items:
            raise CentralTintasValidationError("Nenhum item de catalogo foi encontrado para este turno.")

        if submit_action == "concluir":
            pendentes = [item for item in existing_items.values() if not _clean_text(item.valor)]
            if pendentes:
                raise CentralTintasValidationError(
                    "Existem itens pendentes. Preencha todos os valores antes de concluir."
                )

        relatorio.updated_at = _now()
        if submit_action == "concluir":
            relatorio.status = CENTRAL_TINTAS_STATUS_CONCLUIDO
            relatorio.concluded_at = _now()
        else:
            relatorio.status = CENTRAL_TINTAS_STATUS_EM_ANDAMENTO
        session.commit()
        return _load_relatorio(session, relatorio.id) or relatorio

    for item_id, payload in grouped_fields.items():
        if item_id > 0:
            item = existing_items.get(item_id)
            if item is None:
                continue
            if str(payload.get("remove") or "0").strip() == "1":
                session.delete(item)
                continue
            _apply_legacy_item_payload(item, payload)
            item.updated_at = _now()
            continue

        if catalog_mode:
            continue
        if str(payload.get("remove") or "0").strip() == "1":
            continue
        if _legacy_item_payload_is_blank(payload):
            continue
        session.add(
            CentralTintasItem(
                central_tintas_id=relatorio.id,
                tinta=_clean_text(payload.get("tinta"), max_len=120),
                lote=_clean_text(payload.get("lote"), max_len=80),
                ph=_clean_text(payload.get("ph"), max_len=40),
                viscosidade=_clean_text(payload.get("viscosidade"), max_len=80),
                sujidade=_clean_text(payload.get("sujidade"), max_len=120),
                acoes_corretivas=_clean_text(payload.get("acoes_corretivas")),
                created_at=_now(),
                updated_at=_now(),
            )
        )

    session.flush()
    remaining_items = [item for item in relatorio.itens if item not in session.deleted]
    if not remaining_items:
        raise CentralTintasValidationError("Inclua ao menos um registro para o turno.")

    relatorio.updated_at = _now()
    if submit_action == "concluir":
        relatorio.status = CENTRAL_TINTAS_STATUS_CONCLUIDO
        relatorio.concluded_at = _now()
    else:
        relatorio.status = CENTRAL_TINTAS_STATUS_EM_ANDAMENTO
    session.commit()
    return _load_relatorio(session, relatorio.id) or relatorio


def _apply_legacy_item_payload(item: CentralTintasItem, payload: dict[str, Any]) -> None:
    item.tinta = _clean_text(payload.get("tinta"), max_len=120)
    item.lote = _clean_text(payload.get("lote"), max_len=80)
    item.ph = _clean_text(payload.get("ph"), max_len=40)
    item.viscosidade = _clean_text(payload.get("viscosidade"), max_len=80)
    item.sujidade = _clean_text(payload.get("sujidade"), max_len=120)
    item.acoes_corretivas = _clean_text(payload.get("acoes_corretivas"))


def _legacy_item_payload_is_blank(payload: dict[str, Any]) -> bool:
    for field_name in GENERIC_FIELDS:
        if _clean_text(payload.get(field_name)):
            return False
    return True
