from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import AspectoLancamento, AspectoRegistro, Modelo, Responsavel, Turno


MAX_REGISTROS_POR_LOTE = 10


@dataclass(frozen=True)
class ContextOptions:
    responsaveis: list[Responsavel]
    turnos: list[Turno]
    modelos: list[Modelo]


@dataclass(frozen=True)
class ParsedContext:
    data_referencia: date
    turno: str
    modelo: str
    responsavel_nome: str


@dataclass(frozen=True)
class AspectoEntryInput:
    cis: str
    cod_posicao: str
    local: str
    anomalia: str
    lado: str
    geracao: str
    quantidade: int


@dataclass(frozen=True)
class ProgressSummary:
    total_registrados: int
    limite: int


class AspectoValidationError(ValueError):
    pass


def list_context_options(session: Session) -> ContextOptions:
    responsaveis = list(
        session.scalars(
            select(Responsavel)
            .where(Responsavel.ativo.is_(True))
            .order_by(Responsavel.nome)
        ).all()
    )
    turnos = list(
        session.scalars(
            select(Turno)
            .where(Turno.ativo.is_(True))
            .order_by(_case_turno_order(Turno.codigo), Turno.codigo, Turno.nome)
        ).all()
    )
    modelos = list(
        session.scalars(
            select(Modelo)
            .where(Modelo.ativo.is_(True))
            .order_by(Modelo.nome)
        ).all()
    )
    return ContextOptions(responsaveis=responsaveis, turnos=turnos, modelos=modelos)


def _case_turno_order(column):
    return case((column.in_(["1", "2", "3"]), 0), else_=1)


def parse_context_payload(form_data) -> ParsedContext:
    data_value = (form_data.get("data_referencia") or "").strip()
    turno = (form_data.get("turno") or "").strip()
    modelo = (form_data.get("modelo") or "").strip()
    responsavel_nome = (form_data.get("responsavel_nome") or "").strip()

    missing = []
    if not data_value:
        missing.append("data")
    if not turno:
        missing.append("turno")
    if not modelo:
        missing.append("modelo")
    if not responsavel_nome:
        missing.append("responsável")
    if missing:
        raise AspectoValidationError(f"Preencha: {', '.join(missing)}.")

    try:
        parsed_date = date.fromisoformat(data_value)
    except ValueError as error:
        raise AspectoValidationError("Data inválida para o lançamento.") from error

    return ParsedContext(
        data_referencia=parsed_date,
        turno=turno,
        modelo=modelo,
        responsavel_nome=responsavel_nome,
    )


def build_form_entries(existing_entries: list[dict] | None = None, minimum_rows: int = 1) -> list[dict]:
    entries = [dict(entry) for entry in (existing_entries or [])]
    while len(entries) < minimum_rows:
        entries.append(_empty_entry())
    normalized: list[dict] = []
    for index, entry in enumerate(entries, start=1):
        normalized.append(
            {
                "row_number": index,
                "cis": str(entry.get("cis") or ""),
                "cod_posicao": str(entry.get("cod_posicao") or ""),
                "local": str(entry.get("local") or ""),
                "anomalia": str(entry.get("anomalia") or ""),
                "lado": str(entry.get("lado") or ""),
                "geracao": str(entry.get("geracao") or ""),
                "quantidade": str(entry.get("quantidade") or ""),
            }
        )
    return normalized


def summarize_progress(entries: list[dict]) -> ProgressSummary:
    total_registrados = sum(1 for entry in entries if any(str(entry.get(field) or "").strip() for field in _entry_fields()))
    return ProgressSummary(total_registrados=total_registrados, limite=MAX_REGISTROS_POR_LOTE)


def parse_entries(form_data) -> list[AspectoEntryInput]:
    collected = {field: form_data.getlist(field) for field in _entry_fields()}
    row_count = max((len(values) for values in collected.values()), default=0)
    entries: list[AspectoEntryInput] = []

    for index in range(row_count):
        row = {field: _value_at(collected[field], index) for field in _entry_fields()}
        if not any(row.values()):
            continue

        missing = [label for field, label in _required_labels().items() if not row[field]]
        if missing:
            raise AspectoValidationError(
                f"Complete todos os campos da carroceria {index + 1}: {', '.join(missing)}."
            )

        quantidade = _parse_quantidade(row["quantidade"], index + 1)
        entries.append(
            AspectoEntryInput(
                cis=row["cis"],
                cod_posicao=row["cod_posicao"],
                local=row["local"],
                anomalia=row["anomalia"],
                lado=row["lado"],
                geracao=row["geracao"],
                quantidade=quantidade,
            )
        )

    if not entries:
        raise AspectoValidationError("Adicione ao menos uma carroceria para salvar o lote.")
    if len(entries) > MAX_REGISTROS_POR_LOTE:
        raise AspectoValidationError(f"O lote permite no máximo {MAX_REGISTROS_POR_LOTE} carrocerias por vez.")
    return entries


def save_lancamento(session: Session, context: ParsedContext, entries: list[AspectoEntryInput]) -> AspectoLancamento:
    lancamento = AspectoLancamento(
        data_referencia=context.data_referencia,
        turno=context.turno,
        modelo=context.modelo,
        responsavel_nome=context.responsavel_nome,
        total_registros=len(entries),
        total_quantidade=sum(entry.quantidade for entry in entries),
    )
    session.add(lancamento)
    session.flush()

    for entry in entries:
        session.add(
            AspectoRegistro(
                lancamento_id=lancamento.id,
                data_referencia=context.data_referencia,
                turno=context.turno,
                modelo=context.modelo,
                responsavel_nome=context.responsavel_nome,
                cis=entry.cis,
                cod_posicao=entry.cod_posicao,
                local=entry.local,
                anomalia=entry.anomalia,
                lado=entry.lado,
                geracao=entry.geracao,
                quantidade=entry.quantidade,
            )
        )

    session.commit()
    session.refresh(lancamento)
    return get_lancamento(session, lancamento.id) or lancamento


def get_lancamento(session: Session, lancamento_id: int) -> AspectoLancamento | None:
    statement = (
        select(AspectoLancamento)
        .options(joinedload(AspectoLancamento.registros))
        .where(AspectoLancamento.id == lancamento_id)
    )
    return session.scalars(statement).unique().first()


def list_history(
    session: Session,
    data_referencia: str | None = None,
    turno: str | None = None,
    modelo: str | None = None,
) -> list[AspectoLancamento]:
    statement = select(AspectoLancamento).order_by(
        AspectoLancamento.data_referencia.desc(),
        AspectoLancamento.created_at.desc(),
    )
    if data_referencia:
        statement = statement.where(AspectoLancamento.data_referencia == date.fromisoformat(data_referencia))
    if turno:
        statement = statement.where(AspectoLancamento.turno == turno)
    if modelo:
        statement = statement.where(AspectoLancamento.modelo == modelo)
    return list(session.scalars(statement).all())


def list_daily_launches(session: Session, target_date: date, turno: str | None = None) -> list[AspectoLancamento]:
    statement = select(AspectoLancamento).where(AspectoLancamento.data_referencia == target_date)
    if turno:
        statement = statement.where(AspectoLancamento.turno == turno)
    statement = statement.order_by(AspectoLancamento.updated_at.desc(), AspectoLancamento.id.desc())
    return list(session.scalars(statement).all())


def count_daily_launches(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = select(func.count(AspectoLancamento.id)).where(AspectoLancamento.data_referencia == target_date)
    if turno:
        statement = statement.where(AspectoLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def count_daily_records(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = select(func.count(AspectoRegistro.id)).where(AspectoRegistro.data_referencia == target_date)
    if turno:
        statement = statement.where(AspectoRegistro.turno == turno)
    return int(session.scalar(statement) or 0)


def count_daily_quantity(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = select(func.sum(AspectoRegistro.quantidade)).where(AspectoRegistro.data_referencia == target_date)
    if turno:
        statement = statement.where(AspectoRegistro.turno == turno)
    return int(session.scalar(statement) or 0)


def _entry_fields() -> tuple[str, ...]:
    return ("cis", "cod_posicao", "local", "anomalia", "lado", "geracao", "quantidade")


def _required_labels() -> dict[str, str]:
    return {
        "cis": "CIS",
        "cod_posicao": "código da posição",
        "local": "local",
        "anomalia": "anomalia",
        "lado": "lado",
        "geracao": "geração",
        "quantidade": "quantidade",
    }


def _empty_entry() -> dict[str, str]:
    return {
        "cis": "",
        "cod_posicao": "",
        "local": "",
        "anomalia": "",
        "lado": "",
        "geracao": "",
        "quantidade": "1",
    }


def _value_at(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return str(values[index] or "").strip()


def _parse_quantidade(raw_value: str, row_number: int) -> int:
    try:
        quantidade = int(raw_value)
    except ValueError as error:
        raise AspectoValidationError(f"Quantidade inválida na carroceria {row_number}.") from error
    if quantidade <= 0:
        raise AspectoValidationError(f"Quantidade deve ser maior que zero na carroceria {row_number}.")
    return quantidade
