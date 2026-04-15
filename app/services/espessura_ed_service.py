from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import EspessuraEDItem, EspessuraEDLancamento, Modelo, Responsavel, Turno


TOTAL_PONTOS = 38
STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"
STATUS_BADGES = {
    STATUS_RASCUNHO: "Rascunho",
    STATUS_CONCLUIDO: "Concluído",
}
STATUS_LABELS = {
    "filled": "Preenchido",
    "empty": "Vazio",
    "attention": "Atenção",
}
ATTENTION_MIN = 10.0
ATTENTION_MAX = 60.0


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
    cis: str | None
    observacoes_gerais: str | None


@dataclass(frozen=True)
class ProgressSummary:
    total: int
    preenchidos: int
    percentual: int
    atencao: int


@dataclass(frozen=True)
class ExistingContextStatus:
    lancamento_id: int
    status: str
    label: str
    message: str
    action_label: str
    action_url: str


class EspessuraEDValidationError(ValueError):
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
    cis = (form_data.get("cis") or "").strip() or None
    observacoes_gerais = (form_data.get("observacoes_gerais") or "").strip() or None

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
        raise EspessuraEDValidationError(f"Preencha: {', '.join(missing)}.")

    try:
        parsed_date = date.fromisoformat(data_value)
    except ValueError as error:
        raise EspessuraEDValidationError("Data inválida para o lançamento.") from error

    return ParsedContext(
        data_referencia=parsed_date,
        turno=turno,
        modelo=modelo,
        responsavel_nome=responsavel_nome,
        cis=cis,
        observacoes_gerais=observacoes_gerais,
    )


def build_point_rows(existing_rows: dict[int, dict] | None = None) -> list[dict]:
    existing_rows = existing_rows or {}
    rows: list[dict] = []
    for ponto_numero in range(1, TOTAL_PONTOS + 1):
        existing = existing_rows.get(ponto_numero, {})
        raw_value = existing.get("valor_espessura")
        valor = _coerce_value(raw_value)
        status = _evaluate_value(valor)
        rows.append(
            {
                "ponto_numero": ponto_numero,
                "valor_espessura": _display_value(raw_value, valor),
                "status": status["status"],
                "status_label": status["label"],
                "is_attention": status["status"] == "attention",
                "is_filled": status["status"] in {"filled", "attention"},
                "faixa_preparada": "Faixa futura: min/max a definir",
            }
        )
    return rows


def summarize_progress(point_rows: list[dict]) -> ProgressSummary:
    total = len(point_rows)
    preenchidos = sum(1 for row in point_rows if str(row.get("valor_espessura") or "").strip())
    atencao = sum(1 for row in point_rows if row.get("is_attention"))
    percentual = int(round((preenchidos / total) * 100)) if total else 0
    return ProgressSummary(total=total, preenchidos=preenchidos, percentual=percentual, atencao=atencao)


def find_existing_lancamento_for_context(
    session: Session,
    data_referencia: date,
    turno: str,
    modelo: str,
    cis: str | None,
    exclude_id: int | None = None,
) -> EspessuraEDLancamento | None:
    statement = (
        select(EspessuraEDLancamento)
        .where(EspessuraEDLancamento.data_referencia == data_referencia)
        .where(EspessuraEDLancamento.turno == turno)
        .where(EspessuraEDLancamento.modelo == modelo)
        .where(EspessuraEDLancamento.cis == cis)
        .order_by(EspessuraEDLancamento.updated_at.desc(), EspessuraEDLancamento.id.desc())
    )
    if exclude_id is not None:
        statement = statement.where(EspessuraEDLancamento.id != exclude_id)
    return session.scalars(statement).first()


def build_existing_context_status(lancamento: EspessuraEDLancamento | None) -> ExistingContextStatus | None:
    if lancamento is None:
        return None
    if lancamento.status == STATUS_RASCUNHO:
        return ExistingContextStatus(
            lancamento_id=lancamento.id,
            status=lancamento.status,
            label=STATUS_BADGES[lancamento.status],
            message="Já existe lançamento para este contexto.",
            action_label="Continuar edição",
            action_url=f"/espessura-ed/lancamentos/{lancamento.id}/editar",
        )
    return ExistingContextStatus(
        lancamento_id=lancamento.id,
        status=lancamento.status,
        label=STATUS_BADGES[lancamento.status],
        message="Já existe lançamento para este contexto.",
        action_label="Visualizar",
        action_url=f"/espessura-ed/lancamentos/{lancamento.id}",
    )


def get_lancamento(session: Session, lancamento_id: int) -> EspessuraEDLancamento | None:
    statement = (
        select(EspessuraEDLancamento)
        .options(joinedload(EspessuraEDLancamento.itens))
        .where(EspessuraEDLancamento.id == lancamento_id)
    )
    return session.scalars(statement).unique().first()


def get_existing_row_map(lancamento: EspessuraEDLancamento) -> dict[int, dict]:
    return {row.ponto_numero: {"valor_espessura": row.valor_espessura} for row in lancamento.itens}


def save_lancamento(
    session: Session,
    context: ParsedContext,
    form_data,
    status: str,
    lancamento_id: int | None = None,
) -> EspessuraEDLancamento:
    lancamento = None
    if lancamento_id is not None:
        lancamento = get_lancamento(session, lancamento_id)
        if lancamento is None:
            raise EspessuraEDValidationError("Lançamento não encontrado.")
        if lancamento.status == STATUS_CONCLUIDO:
            raise EspessuraEDValidationError("Lançamentos concluídos não podem ser alterados nesta etapa.")
    else:
        existing_for_context = find_existing_lancamento_for_context(
            session,
            context.data_referencia,
            context.turno,
            context.modelo,
            context.cis,
        )
        if existing_for_context is not None:
            raise EspessuraEDValidationError("Já existe lançamento para este contexto. Use continuar edição ou visualizar.")

    if lancamento is None:
        lancamento = EspessuraEDLancamento()
        session.add(lancamento)

    lancamento.data_referencia = context.data_referencia
    lancamento.turno = context.turno
    lancamento.modelo = context.modelo
    lancamento.responsavel_nome = context.responsavel_nome
    lancamento.cis = context.cis
    lancamento.status = status
    lancamento.observacoes_gerais = context.observacoes_gerais

    session.flush()

    existing_rows = {row.ponto_numero: row for row in lancamento.itens}
    total_preenchidos = 0
    for ponto_numero in range(1, TOTAL_PONTOS + 1):
        valor = _parse_value(form_data.get(f"ponto_{ponto_numero}"))
        if valor is not None:
            total_preenchidos += 1
        row = existing_rows.get(ponto_numero)
        if row is None:
            row = EspessuraEDItem(ponto_numero=ponto_numero)
            lancamento.itens.append(row)
        row.valor_espessura = valor

    lancamento.total_pontos_preenchidos = total_preenchidos
    session.commit()
    session.refresh(lancamento)
    return get_lancamento(session, lancamento.id) or lancamento


def list_history(
    session: Session,
    data_referencia: str | None = None,
    turno: str | None = None,
    modelo: str | None = None,
    status: str | None = None,
) -> list[dict]:
    statement = (
        select(
            EspessuraEDLancamento,
            func.sum(case((EspessuraEDItem.valor_espessura.is_not(None), 1), else_=0)).label("quantidade_pontos"),
        )
        .outerjoin(EspessuraEDItem, EspessuraEDItem.lancamento_id == EspessuraEDLancamento.id)
        .group_by(EspessuraEDLancamento.id)
        .order_by(EspessuraEDLancamento.data_referencia.desc(), EspessuraEDLancamento.created_at.desc())
    )
    if data_referencia:
        statement = statement.where(EspessuraEDLancamento.data_referencia == date.fromisoformat(data_referencia))
    if turno:
        statement = statement.where(EspessuraEDLancamento.turno == turno)
    if modelo:
        statement = statement.where(EspessuraEDLancamento.modelo == modelo)
    if status:
        statement = statement.where(EspessuraEDLancamento.status == status)

    rows = session.execute(statement).all()
    return [
        {
            "lancamento": lancamento,
            "quantidade_pontos": int(quantidade_pontos or 0),
        }
        for lancamento, quantidade_pontos in rows
    ]


def list_daily_launches(session: Session, target_date: date, turno: str | None = None) -> list[EspessuraEDLancamento]:
    statement = select(EspessuraEDLancamento).where(EspessuraEDLancamento.data_referencia == target_date)
    if turno:
        statement = statement.where(EspessuraEDLancamento.turno == turno)
    statement = statement.order_by(EspessuraEDLancamento.updated_at.desc(), EspessuraEDLancamento.id.desc())
    return list(session.scalars(statement).all())


def count_pending_launches(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = select(func.count(EspessuraEDLancamento.id)).where(EspessuraEDLancamento.data_referencia == target_date)
    statement = statement.where(EspessuraEDLancamento.status == STATUS_RASCUNHO)
    if turno:
        statement = statement.where(EspessuraEDLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def count_daily_filled_points(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = (
        select(func.count(EspessuraEDItem.id))
        .join(EspessuraEDLancamento, EspessuraEDLancamento.id == EspessuraEDItem.lancamento_id)
        .where(EspessuraEDLancamento.data_referencia == target_date)
        .where(EspessuraEDItem.valor_espessura.is_not(None))
    )
    if turno:
        statement = statement.where(EspessuraEDLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def _parse_value(raw_value) -> float | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError as error:
        raise EspessuraEDValidationError(f"Valor de espessura inválido: '{text}'.") from error


def _coerce_value(raw_value) -> float | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    try:
        return float(str(raw_value).strip().replace(",", "."))
    except ValueError:
        return None


def _evaluate_value(valor_espessura: float | None) -> dict:
    if valor_espessura is None:
        return {"status": "empty", "label": STATUS_LABELS["empty"]}
    if valor_espessura < ATTENTION_MIN or valor_espessura > ATTENTION_MAX:
        return {"status": "attention", "label": STATUS_LABELS["attention"]}
    return {"status": "filled", "label": STATUS_LABELS["filled"]}


def _display_value(raw_value, parsed_value: float | None) -> str:
    if isinstance(raw_value, str):
        return raw_value.strip()
    if parsed_value is None:
        return ""
    return _format_value(parsed_value)


def _format_value(valor_espessura: float | None) -> str:
    if valor_espessura is None:
        return ""
    texto = f"{valor_espessura:.1f}"
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto
