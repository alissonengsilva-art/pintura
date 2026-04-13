from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import PressaoFiltrosItem, PressaoFiltrosLancamento, Responsavel, Turno


TOTAL_FILTROS = 24
STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"
STATUS_BADGES = {
    STATUS_RASCUNHO: "Rascunho",
    STATUS_CONCLUIDO: "Concluído",
}


@dataclass(frozen=True)
class ContextOptions:
    responsaveis: list[Responsavel]
    turnos: list[Turno]


@dataclass(frozen=True)
class ParsedContext:
    data_referencia: date
    turno: str
    responsavel_nome: str
    observacoes_gerais: str | None


@dataclass(frozen=True)
class ProgressSummary:
    total: int
    preenchidos: int
    em_alarme: int
    percentual: int


@dataclass(frozen=True)
class ExistingContextStatus:
    lancamento_id: int
    status: str
    label: str
    message: str
    action_label: str
    action_url: str


class PressaoFiltrosValidationError(ValueError):
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
    return ContextOptions(responsaveis=responsaveis, turnos=turnos)


def _case_turno_order(column):
    return case((column.in_(["1", "2", "3"]), 0), else_=1)


def parse_context_payload(form_data) -> ParsedContext:
    data_value = (form_data.get("data_referencia") or "").strip()
    turno = (form_data.get("turno") or "").strip()
    responsavel_nome = (form_data.get("responsavel_nome") or "").strip()
    observacoes_gerais = (form_data.get("observacoes_gerais") or "").strip() or None

    missing = []
    if not data_value:
        missing.append("data")
    if not turno:
        missing.append("turno")
    if not responsavel_nome:
        missing.append("responsável")
    if missing:
        raise PressaoFiltrosValidationError(f"Preencha: {', '.join(missing)}.")

    try:
        parsed_date = date.fromisoformat(data_value)
    except ValueError as error:
        raise PressaoFiltrosValidationError("Data inválida para o lançamento.") from error

    return ParsedContext(
        data_referencia=parsed_date,
        turno=turno,
        responsavel_nome=responsavel_nome,
        observacoes_gerais=observacoes_gerais,
    )


def build_filter_rows(existing_rows: dict[int, dict] | None = None) -> list[dict]:
    existing_rows = existing_rows or {}
    rows: list[dict] = []
    for filtro_numero in range(1, TOTAL_FILTROS + 1):
        existing = existing_rows.get(filtro_numero, {})
        raw_value = existing.get("valor_pressao")
        valor = _coerce_pressure(raw_value)
        display_value = _display_pressure(raw_value, valor)
        em_alarme = _compute_alarm(valor)
        rows.append(
            {
                "filtro_numero": filtro_numero,
                "valor_pressao": display_value,
                "em_alarme": em_alarme,
                "status_label": "Em alarme" if em_alarme else "Normal",
            }
        )
    return rows


def summarize_progress(filter_rows: list[dict]) -> ProgressSummary:
    total = len(filter_rows)
    preenchidos = sum(1 for row in filter_rows if str(row.get("valor_pressao") or "").strip())
    em_alarme = sum(1 for row in filter_rows if row.get("em_alarme"))
    percentual = int(round((preenchidos / total) * 100)) if total else 0
    return ProgressSummary(total=total, preenchidos=preenchidos, em_alarme=em_alarme, percentual=percentual)


def find_existing_lancamento_for_context(
    session: Session,
    data_referencia: date,
    turno: str,
    exclude_id: int | None = None,
) -> PressaoFiltrosLancamento | None:
    statement = (
        select(PressaoFiltrosLancamento)
        .where(PressaoFiltrosLancamento.data_referencia == data_referencia)
        .where(PressaoFiltrosLancamento.turno == turno)
        .order_by(PressaoFiltrosLancamento.updated_at.desc(), PressaoFiltrosLancamento.id.desc())
    )
    if exclude_id is not None:
        statement = statement.where(PressaoFiltrosLancamento.id != exclude_id)
    return session.scalars(statement).first()


def build_existing_context_status(lancamento: PressaoFiltrosLancamento | None) -> ExistingContextStatus | None:
    if lancamento is None:
        return None
    if lancamento.status == STATUS_RASCUNHO:
        return ExistingContextStatus(
            lancamento_id=lancamento.id,
            status=lancamento.status,
            label=STATUS_BADGES[lancamento.status],
            message="Já existe lançamento para este contexto.",
            action_label="Continuar edição",
            action_url=f"/pressao-filtros-ed/lancamentos/{lancamento.id}/editar",
        )
    return ExistingContextStatus(
        lancamento_id=lancamento.id,
        status=lancamento.status,
        label=STATUS_BADGES[lancamento.status],
        message="Já existe lançamento para este contexto.",
        action_label="Visualizar",
        action_url=f"/pressao-filtros-ed/lancamentos/{lancamento.id}",
    )


def get_lancamento(session: Session, lancamento_id: int) -> PressaoFiltrosLancamento | None:
    statement = (
        select(PressaoFiltrosLancamento)
        .options(joinedload(PressaoFiltrosLancamento.itens))
        .where(PressaoFiltrosLancamento.id == lancamento_id)
    )
    return session.scalars(statement).unique().first()


def get_existing_row_map(lancamento: PressaoFiltrosLancamento) -> dict[int, dict]:
    return {
        row.filtro_numero: {
            "valor_pressao": row.valor_pressao,
            "em_alarme": row.em_alarme,
        }
        for row in lancamento.itens
    }


def save_lancamento(
    session: Session,
    context: ParsedContext,
    form_data,
    status: str,
    lancamento_id: int | None = None,
) -> PressaoFiltrosLancamento:
    lancamento = None
    if lancamento_id is not None:
        lancamento = get_lancamento(session, lancamento_id)
        if lancamento is None:
            raise PressaoFiltrosValidationError("Lançamento não encontrado.")
        if lancamento.status == STATUS_CONCLUIDO:
            raise PressaoFiltrosValidationError("Lançamentos concluídos não podem ser alterados nesta etapa.")
    else:
        existing_for_context = find_existing_lancamento_for_context(session, context.data_referencia, context.turno)
        if existing_for_context is not None:
            raise PressaoFiltrosValidationError("Já existe lançamento para este contexto. Use continuar edição ou visualizar.")

    if lancamento is None:
        lancamento = PressaoFiltrosLancamento()
        session.add(lancamento)

    lancamento.data_referencia = context.data_referencia
    lancamento.turno = context.turno
    lancamento.responsavel_nome = context.responsavel_nome
    lancamento.status = status
    lancamento.observacoes_gerais = context.observacoes_gerais

    session.flush()

    existing_rows = {row.filtro_numero: row for row in lancamento.itens}
    total_alarmes = 0
    for filtro_numero in range(1, TOTAL_FILTROS + 1):
        valor = _parse_pressure(form_data.get(f"filtro_{filtro_numero}"))
        em_alarme = _compute_alarm(valor)
        if em_alarme:
            total_alarmes += 1
        row = existing_rows.get(filtro_numero)
        if row is None:
            row = PressaoFiltrosItem(filtro_numero=filtro_numero)
            lancamento.itens.append(row)
        row.valor_pressao = valor
        row.em_alarme = em_alarme

    lancamento.total_filtros_em_alarme = total_alarmes
    session.commit()
    session.refresh(lancamento)
    return get_lancamento(session, lancamento.id) or lancamento


def list_history(
    session: Session,
    data_inicial: str | None = None,
    data_final: str | None = None,
    turno: str | None = None,
    status: str | None = None,
    somente_alarme: bool = False,
) -> list[dict]:
    statement = (
        select(
            PressaoFiltrosLancamento,
            func.sum(case((PressaoFiltrosItem.valor_pressao.is_not(None), 1), else_=0)).label("quantidade_filtros"),
            func.sum(case((PressaoFiltrosItem.em_alarme.is_(True), 1), else_=0)).label("quantidade_alarmes"),
        )
        .outerjoin(PressaoFiltrosItem, PressaoFiltrosItem.lancamento_id == PressaoFiltrosLancamento.id)
        .group_by(PressaoFiltrosLancamento.id)
        .order_by(PressaoFiltrosLancamento.data_referencia.desc(), PressaoFiltrosLancamento.created_at.desc())
    )
    if data_inicial:
        statement = statement.where(PressaoFiltrosLancamento.data_referencia >= date.fromisoformat(data_inicial))
    if data_final:
        statement = statement.where(PressaoFiltrosLancamento.data_referencia <= date.fromisoformat(data_final))
    if turno:
        statement = statement.where(PressaoFiltrosLancamento.turno == turno)
    if status:
        statement = statement.where(PressaoFiltrosLancamento.status == status)
    if somente_alarme:
        statement = statement.having(func.sum(case((PressaoFiltrosItem.em_alarme.is_(True), 1), else_=0)) > 0)

    rows = session.execute(statement).all()
    return [
        {
            "lancamento": lancamento,
            "quantidade_filtros": int(quantidade_filtros or 0),
            "quantidade_alarmes": int(quantidade_alarmes or 0),
        }
        for lancamento, quantidade_filtros, quantidade_alarmes in rows
    ]


def list_daily_launches(session: Session, target_date: date, turno: str | None = None) -> list[PressaoFiltrosLancamento]:
    statement = select(PressaoFiltrosLancamento).where(PressaoFiltrosLancamento.data_referencia == target_date)
    if turno:
        statement = statement.where(PressaoFiltrosLancamento.turno == turno)
    statement = statement.order_by(PressaoFiltrosLancamento.turno, PressaoFiltrosLancamento.updated_at.desc())
    return list(session.scalars(statement).all())


def count_launches_with_alarm(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = select(func.count(PressaoFiltrosLancamento.id)).where(PressaoFiltrosLancamento.data_referencia == target_date)
    statement = statement.where(PressaoFiltrosLancamento.total_filtros_em_alarme > 0)
    if turno:
        statement = statement.where(PressaoFiltrosLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def count_pending_launches(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = select(func.count(PressaoFiltrosLancamento.id)).where(PressaoFiltrosLancamento.data_referencia == target_date)
    statement = statement.where(PressaoFiltrosLancamento.status == STATUS_RASCUNHO)
    if turno:
        statement = statement.where(PressaoFiltrosLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def _parse_pressure(raw_value) -> float | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError as error:
        raise PressaoFiltrosValidationError(f"Valor de pressão inválido: '{text}'.") from error


def _coerce_pressure(raw_value) -> float | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    try:
        return float(str(raw_value).strip().replace(",", "."))
    except ValueError:
        return None


def _compute_alarm(valor_pressao: float | None) -> bool:
    return valor_pressao is not None and valor_pressao > 1.0


def _format_pressure(valor_pressao: float | None) -> str:
    if valor_pressao is None:
        return ""
    texto = f"{valor_pressao:.2f}"
    if texto.endswith("00"):
        texto = texto[:-3]
    elif texto.endswith("0"):
        texto = texto[:-1]
    return texto


def _display_pressure(raw_value, parsed_value: float | None) -> str:
    if isinstance(raw_value, str):
        return raw_value.strip()
    if parsed_value is None:
        return ""
    return _format_pressure(parsed_value)
