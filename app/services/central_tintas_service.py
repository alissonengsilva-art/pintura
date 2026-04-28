from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CentralTintasItem,
    CentralTintasRelatorio,
    CENTRAL_TINTAS_STATUS_CONCLUIDO,
    CENTRAL_TINTAS_STATUS_EM_ANDAMENTO,
    Turno,
)


class CentralTintasValidationError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def central_tintas_schema_available(session: Session) -> bool:
    inspector = inspect(session.get_bind())
    return inspector.has_table("central_tintas_relatorios") and inspector.has_table("central_tintas_itens")


def _semana_mes_por_data(data_controle: date) -> tuple[str, str]:
    semana = str(data_controle.isocalendar().week)
    mes = str(data_controle.month)
    return semana, mes


def list_turno_options(session: Session) -> list[Turno]:
    return list(session.scalars(select(Turno).where(Turno.ativo.is_(True)).order_by(Turno.codigo, Turno.nome)).all())


def create_relatorio(session: Session, data_controle: date, turno: str, responsavel: str) -> CentralTintasRelatorio:
    if not central_tintas_schema_available(session):
        raise CentralTintasValidationError("Estrutura da Central de Tintas nao instalada. Execute as migrations.")
    if not turno.strip():
        raise CentralTintasValidationError("Informe o turno.")
    if not responsavel.strip():
        raise CentralTintasValidationError("Informe o responsavel.")

    semana, mes = _semana_mes_por_data(data_controle)
    relatorio = CentralTintasRelatorio(
        data_controle=data_controle,
        semana=semana,
        mes=mes,
        responsavel=responsavel.strip(),
        turno=turno.strip(),
        status=CENTRAL_TINTAS_STATUS_EM_ANDAMENTO,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(relatorio)
    session.flush()

    # Garante linha inicial para manter o mesmo fluxo visual de checklist.
    session.add(CentralTintasItem(central_tintas_id=relatorio.id, created_at=_now(), updated_at=_now()))
    session.commit()
    session.refresh(relatorio)
    return relatorio


def get_relatorio_by_id(session: Session, relatorio_id: int) -> CentralTintasRelatorio | None:
    if not central_tintas_schema_available(session):
        return None
    return session.scalars(
        select(CentralTintasRelatorio)
        .options(joinedload(CentralTintasRelatorio.itens))
        .where(CentralTintasRelatorio.id == relatorio_id)
    ).unique().first()


def build_relatorio_detail(session: Session, relatorio_obj: CentralTintasRelatorio) -> dict:
    session.refresh(relatorio_obj)
    itens = [
        {
            "id": item.id,
            "tinta": item.tinta or "",
            "lote": item.lote or "",
            "ph": item.ph or "",
            "viscosidade": item.viscosidade or "",
            "sujidade": item.sujidade or "",
            "acoes_corretivas": item.acoes_corretivas or "",
        }
        for item in relatorio_obj.itens
    ]
    preenchidos = sum(
        1
        for row in itens
        if any(
            str(row.get(field) or "").strip()
            for field in ("tinta", "lote", "ph", "viscosidade", "sujidade", "acoes_corretivas")
        )
    )
    return {
        "id": relatorio_obj.id,
        "data_label": relatorio_obj.data_controle.strftime("%d/%m/%Y"),
        "data_controle": relatorio_obj.data_controle,
        "semana": relatorio_obj.semana,
        "mes": relatorio_obj.mes,
        "responsavel": relatorio_obj.responsavel,
        "turno": relatorio_obj.turno,
        "status": relatorio_obj.status,
        "status_label": "Concluido" if relatorio_obj.status == CENTRAL_TINTAS_STATUS_CONCLUIDO else "Em andamento",
        "itens": itens,
        "preenchidos": preenchidos,
        "total": len(itens),
    }


def list_relatorios_history(session: Session, limit: int = 100) -> list[dict]:
    if not central_tintas_schema_available(session):
        return []
    relatorios = list(
        session.scalars(
            select(CentralTintasRelatorio)
            .options(joinedload(CentralTintasRelatorio.itens))
            .order_by(CentralTintasRelatorio.data_controle.desc(), CentralTintasRelatorio.turno.desc(), CentralTintasRelatorio.id.desc())
            .limit(limit)
        ).unique().all()
    )
    return [build_relatorio_detail(session, relatorio) for relatorio in relatorios]


def save_relatorio(session: Session, relatorio_obj: CentralTintasRelatorio, form_data: dict[str, str], action: str = "salvar") -> None:
    rows_map: dict[int, dict[str, str]] = {}
    for key, raw_value in form_data.items():
        if not key.startswith("item_"):
            continue
        parts = key.split("_", 2)
        if len(parts) != 3:
            continue
        _, item_id_raw, field = parts
        try:
            item_id = int(item_id_raw)
        except ValueError:
            continue
        rows_map.setdefault(item_id, {})[field] = str(raw_value or "").strip()

    keep_ids: set[int] = set()
    now = _now()
    existing_by_id = {item.id: item for item in relatorio_obj.itens}

    for item_id, payload in rows_map.items():
        marked_remove = payload.get("remove", "").strip() == "1"
        if marked_remove:
            if item_id > 0 and item_id in existing_by_id:
                session.delete(existing_by_id[item_id])
            continue

        if item_id > 0 and item_id in existing_by_id:
            item = existing_by_id[item_id]
        else:
            item = CentralTintasItem(central_tintas_id=relatorio_obj.id, created_at=now, updated_at=now)
            session.add(item)

        item.tinta = payload.get("tinta") or None
        item.lote = payload.get("lote") or None
        item.ph = payload.get("ph") or None
        item.viscosidade = payload.get("viscosidade") or None
        item.sujidade = payload.get("sujidade") or None
        item.acoes_corretivas = payload.get("acoes_corretivas") or None
        item.updated_at = now
        session.flush()
        keep_ids.add(item.id)

    # Mantem ao menos uma linha para o editor.
    if not keep_ids:
        session.add(CentralTintasItem(central_tintas_id=relatorio_obj.id, created_at=now, updated_at=now))

    relatorio_obj.updated_at = now
    if action == "concluir":
        if not any(
            item
            for item in relatorio_obj.itens
            if any(
                str(getattr(item, field) or "").strip()
                for field in ("tinta", "lote", "ph", "viscosidade", "sujidade", "acoes_corretivas")
            )
        ):
            raise CentralTintasValidationError("Preencha ao menos uma linha antes de concluir o relatorio.")
        relatorio_obj.status = CENTRAL_TINTAS_STATUS_CONCLUIDO
        relatorio_obj.concluded_at = now
    else:
        relatorio_obj.status = CENTRAL_TINTAS_STATUS_EM_ANDAMENTO

    session.commit()


def conclude_relatorio(session: Session, relatorio_obj: CentralTintasRelatorio) -> None:
    now = _now()
    relatorio_obj.status = CENTRAL_TINTAS_STATUS_CONCLUIDO
    relatorio_obj.concluded_at = now
    relatorio_obj.updated_at = now
    session.commit()
