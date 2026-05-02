from __future__ import annotations

from datetime import UTC, date, datetime, time
from math import ceil
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.models import CentralTintasRegistro


class CentralTintasValidationError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def central_tintas_schema_available(session: Session) -> bool:
    inspector = inspect(session.get_bind())
    return inspector.has_table("central_tintas_registros")


def _clean_text(value: Any, *, max_len: int | None = None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if max_len is not None:
        return text[:max_len]
    return text


def _parse_datetime(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise CentralTintasValidationError("Informe data/hora.")

    normalized = raw.replace("Z", "")
    for parser in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(normalized, parser)
        except ValueError:
            continue
    raise CentralTintasValidationError("Data/hora invalida.")


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise CentralTintasValidationError("Data de filtro invalida.") from error


def _serialize(row: CentralTintasRegistro) -> dict[str, Any]:
    return {
        "id": row.id,
        "data_hora": row.data_hora.strftime("%Y-%m-%dT%H:%M"),
        "responsavel": row.responsavel or "",
        "turno": row.turno or "",
        "tinta": row.tinta or "",
        "lote": row.lote or "",
        "ph": row.ph or "",
        "viscosidade": row.viscosidade or "",
        "sujidade": row.sujidade or "",
        "acoes_corretivas": row.acoes_corretivas or "",
    }


def list_registros(
    session: Session,
    *,
    page: int,
    per_page: int,
    data_inicial: str | None = None,
    data_final: str | None = None,
    responsavel: str | None = None,
    turno: str | None = None,
) -> dict[str, Any]:
    if not central_tintas_schema_available(session):
        return {
            "items": [],
            "total": 0,
            "page": 1,
            "per_page": per_page,
            "total_pages": 1,
            "filters": {
                "data_inicial": data_inicial or "",
                "data_final": data_final or "",
                "responsavel": responsavel or "",
                "turno": turno or "",
            },
        }

    page = max(1, int(page or 1))
    per_page = max(1, int(per_page or 50))

    statement = select(CentralTintasRegistro)

    dt_start = _parse_date(data_inicial)
    dt_end = _parse_date(data_final)
    resp = _clean_text(responsavel)
    turno_value = _clean_text(turno)

    if dt_start is not None:
        statement = statement.where(CentralTintasRegistro.data_hora >= datetime.combine(dt_start, time.min))
    if dt_end is not None:
        statement = statement.where(CentralTintasRegistro.data_hora <= datetime.combine(dt_end, time.max))
    if resp:
        statement = statement.where(CentralTintasRegistro.responsavel == resp)
    if turno_value:
        statement = statement.where(CentralTintasRegistro.turno == turno_value)

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(session.scalar(count_statement) or 0)
    total_pages = max(1, ceil(total / per_page))
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page
    rows = list(
        session.scalars(
            statement.order_by(CentralTintasRegistro.data_hora.desc(), CentralTintasRegistro.id.desc())
            .limit(per_page)
            .offset(offset)
        ).all()
    )

    return {
        "items": [_serialize(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "filters": {
            "data_inicial": data_inicial or "",
            "data_final": data_final or "",
            "responsavel": responsavel or "",
            "turno": turno or "",
        },
    }


def create_registro(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    if not central_tintas_schema_available(session):
        raise CentralTintasValidationError("Estrutura da Central de Tintas nao instalada. Execute as migrations.")

    row = CentralTintasRegistro(
        data_hora=_parse_datetime(payload.get("data_hora") or _now().strftime("%Y-%m-%dT%H:%M")),
        responsavel=_clean_text(payload.get("responsavel"), max_len=120),
        turno=_clean_text(payload.get("turno"), max_len=20),
        tinta=_clean_text(payload.get("tinta"), max_len=120),
        lote=_clean_text(payload.get("lote"), max_len=80),
        ph=_clean_text(payload.get("ph"), max_len=40),
        viscosidade=_clean_text(payload.get("viscosidade"), max_len=80),
        sujidade=_clean_text(payload.get("sujidade"), max_len=120),
        acoes_corretivas=_clean_text(payload.get("acoes_corretivas")),
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize(row)


def update_registro(session: Session, registro_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    row = session.get(CentralTintasRegistro, registro_id)
    if row is None:
        raise CentralTintasValidationError("Registro nao encontrado.")

    allowed_fields = {
        "data_hora",
        "responsavel",
        "turno",
        "tinta",
        "lote",
        "ph",
        "viscosidade",
        "sujidade",
        "acoes_corretivas",
    }

    for field in allowed_fields:
        if field not in payload:
            continue
        value = payload.get(field)
        if field == "data_hora":
            row.data_hora = _parse_datetime(value)
        elif field == "responsavel":
            row.responsavel = _clean_text(value, max_len=120)
        elif field == "turno":
            row.turno = _clean_text(value, max_len=20)
        elif field == "tinta":
            row.tinta = _clean_text(value, max_len=120)
        elif field == "lote":
            row.lote = _clean_text(value, max_len=80)
        elif field == "ph":
            row.ph = _clean_text(value, max_len=40)
        elif field == "viscosidade":
            row.viscosidade = _clean_text(value, max_len=80)
        elif field == "sujidade":
            row.sujidade = _clean_text(value, max_len=120)
        elif field == "acoes_corretivas":
            row.acoes_corretivas = _clean_text(value)

    row.updated_at = _now()
    session.commit()
    session.refresh(row)
    return _serialize(row)


def delete_registro(session: Session, registro_id: int) -> None:
    row = session.get(CentralTintasRegistro, registro_id)
    if row is None:
        raise CentralTintasValidationError("Registro nao encontrado.")
    session.delete(row)
    session.commit()
