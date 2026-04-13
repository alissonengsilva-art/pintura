from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Modelo, Responsavel, TensaoRetificadoresItem, TensaoRetificadoresLancamento, Turno


TOTAL_ZONAS = 29
FAIXA_MINIMA = 80.0
FAIXA_MAXIMA = 400.0
STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"
STATUS_BADGES = {
    STATUS_RASCUNHO: "Rascunho",
    STATUS_CONCLUIDO: "Concluído",
}
STATUS_LABELS = {
    "ok": "OK",
    "out": "Fora do padrão",
    "neutral": "Não avaliado",
}


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
    observacoes_gerais: str | None


@dataclass(frozen=True)
class ProgressSummary:
    total: int
    preenchidos: int
    fora_padrao: int
    percentual: int


@dataclass(frozen=True)
class ExistingContextStatus:
    lancamento_id: int
    status: str
    label: str
    message: str
    action_label: str
    action_url: str


class TensaoRetificadoresValidationError(ValueError):
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
        raise TensaoRetificadoresValidationError(f"Preencha: {', '.join(missing)}.")

    try:
        parsed_date = date.fromisoformat(data_value)
    except ValueError as error:
        raise TensaoRetificadoresValidationError("Data inválida para o lançamento.") from error

    return ParsedContext(
        data_referencia=parsed_date,
        turno=turno,
        modelo=modelo,
        responsavel_nome=responsavel_nome,
        observacoes_gerais=observacoes_gerais,
    )


def build_zone_rows(existing_rows: dict[int, dict] | None = None) -> list[dict]:
    existing_rows = existing_rows or {}
    rows: list[dict] = []
    for zona_numero in range(1, TOTAL_ZONAS + 1):
        existing = existing_rows.get(zona_numero, {})
        raw_value = existing.get("valor_tensao")
        valor = _coerce_tensao(raw_value)
        status = _evaluate_tensao(valor)
        rows.append(
            {
                "zona_numero": zona_numero,
                "faixa_texto": f"{int(FAIXA_MINIMA)}V a {int(FAIXA_MAXIMA)}V",
                "valor_tensao": _display_tensao(raw_value, valor),
                "status": status["status"],
                "status_label": status["label"],
                "fora_padrao": status["fora_padrao"],
                "is_out": status["status"] == "out",
            }
        )
    return rows


def summarize_progress(zone_rows: list[dict]) -> ProgressSummary:
    total = len(zone_rows)
    preenchidos = sum(1 for row in zone_rows if str(row.get("valor_tensao") or "").strip())
    fora_padrao = sum(1 for row in zone_rows if row.get("fora_padrao"))
    percentual = int(round((preenchidos / total) * 100)) if total else 0
    return ProgressSummary(total=total, preenchidos=preenchidos, fora_padrao=fora_padrao, percentual=percentual)


def find_existing_lancamento_for_context(
    session: Session,
    data_referencia: date,
    turno: str,
    modelo: str,
    exclude_id: int | None = None,
) -> TensaoRetificadoresLancamento | None:
    statement = (
        select(TensaoRetificadoresLancamento)
        .where(TensaoRetificadoresLancamento.data_referencia == data_referencia)
        .where(TensaoRetificadoresLancamento.turno == turno)
        .where(TensaoRetificadoresLancamento.modelo == modelo)
        .order_by(TensaoRetificadoresLancamento.updated_at.desc(), TensaoRetificadoresLancamento.id.desc())
    )
    if exclude_id is not None:
        statement = statement.where(TensaoRetificadoresLancamento.id != exclude_id)
    return session.scalars(statement).first()


def build_existing_context_status(
    lancamento: TensaoRetificadoresLancamento | None,
) -> ExistingContextStatus | None:
    if lancamento is None:
        return None
    if lancamento.status == STATUS_RASCUNHO:
        return ExistingContextStatus(
            lancamento_id=lancamento.id,
            status=lancamento.status,
            label=STATUS_BADGES[lancamento.status],
            message="Já existe lançamento para este contexto.",
            action_label="Continuar edição",
            action_url=f"/tensao-retificadores-ed/lancamentos/{lancamento.id}/editar",
        )
    return ExistingContextStatus(
        lancamento_id=lancamento.id,
        status=lancamento.status,
        label=STATUS_BADGES[lancamento.status],
        message="Já existe lançamento para este contexto.",
        action_label="Visualizar",
        action_url=f"/tensao-retificadores-ed/lancamentos/{lancamento.id}",
    )


def get_lancamento(session: Session, lancamento_id: int) -> TensaoRetificadoresLancamento | None:
    statement = (
        select(TensaoRetificadoresLancamento)
        .options(joinedload(TensaoRetificadoresLancamento.itens))
        .where(TensaoRetificadoresLancamento.id == lancamento_id)
    )
    return session.scalars(statement).unique().first()


def get_existing_row_map(lancamento: TensaoRetificadoresLancamento) -> dict[int, dict]:
    return {
        row.zona_numero: {
            "valor_tensao": row.valor_tensao,
            "fora_padrao": row.fora_padrao,
        }
        for row in lancamento.itens
    }


def save_lancamento(
    session: Session,
    context: ParsedContext,
    form_data,
    status: str,
    lancamento_id: int | None = None,
) -> TensaoRetificadoresLancamento:
    lancamento = None
    if lancamento_id is not None:
        lancamento = get_lancamento(session, lancamento_id)
        if lancamento is None:
            raise TensaoRetificadoresValidationError("Lançamento não encontrado.")
        if lancamento.status == STATUS_CONCLUIDO:
            raise TensaoRetificadoresValidationError("Lançamentos concluídos não podem ser alterados nesta etapa.")
    else:
        existing_for_context = find_existing_lancamento_for_context(
            session,
            context.data_referencia,
            context.turno,
            context.modelo,
        )
        if existing_for_context is not None:
            raise TensaoRetificadoresValidationError("Já existe lançamento para este contexto. Use continuar edição ou visualizar.")

    if lancamento is None:
        lancamento = TensaoRetificadoresLancamento()
        session.add(lancamento)

    lancamento.data_referencia = context.data_referencia
    lancamento.turno = context.turno
    lancamento.modelo = context.modelo
    lancamento.responsavel_nome = context.responsavel_nome
    lancamento.status = status
    lancamento.observacoes_gerais = context.observacoes_gerais

    session.flush()

    existing_rows = {row.zona_numero: row for row in lancamento.itens}
    total_fora_padrao = 0
    for zona_numero in range(1, TOTAL_ZONAS + 1):
        valor = _parse_tensao(form_data.get(f"zona_{zona_numero}"))
        avaliacao = _evaluate_tensao(valor)
        if avaliacao["fora_padrao"]:
            total_fora_padrao += 1
        row = existing_rows.get(zona_numero)
        if row is None:
            row = TensaoRetificadoresItem(zona_numero=zona_numero)
            lancamento.itens.append(row)
        row.valor_tensao = valor
        row.fora_padrao = bool(avaliacao["fora_padrao"])

    lancamento.total_zonas_fora_padrao = total_fora_padrao
    session.commit()
    session.refresh(lancamento)
    return get_lancamento(session, lancamento.id) or lancamento


def list_history(
    session: Session,
    data_inicial: str | None = None,
    data_final: str | None = None,
    turno: str | None = None,
    modelo: str | None = None,
    status: str | None = None,
    somente_fora_padrao: bool = False,
) -> list[dict]:
    statement = (
        select(
            TensaoRetificadoresLancamento,
            func.sum(case((TensaoRetificadoresItem.valor_tensao.is_not(None), 1), else_=0)).label("quantidade_zonas"),
            func.sum(case((TensaoRetificadoresItem.fora_padrao.is_(True), 1), else_=0)).label("quantidade_fora_padrao"),
        )
        .outerjoin(TensaoRetificadoresItem, TensaoRetificadoresItem.lancamento_id == TensaoRetificadoresLancamento.id)
        .group_by(TensaoRetificadoresLancamento.id)
        .order_by(TensaoRetificadoresLancamento.data_referencia.desc(), TensaoRetificadoresLancamento.created_at.desc())
    )
    if data_inicial:
        statement = statement.where(TensaoRetificadoresLancamento.data_referencia >= date.fromisoformat(data_inicial))
    if data_final:
        statement = statement.where(TensaoRetificadoresLancamento.data_referencia <= date.fromisoformat(data_final))
    if turno:
        statement = statement.where(TensaoRetificadoresLancamento.turno == turno)
    if modelo:
        statement = statement.where(TensaoRetificadoresLancamento.modelo == modelo)
    if status:
        statement = statement.where(TensaoRetificadoresLancamento.status == status)
    if somente_fora_padrao:
        statement = statement.having(func.sum(case((TensaoRetificadoresItem.fora_padrao.is_(True), 1), else_=0)) > 0)

    rows = session.execute(statement).all()
    return [
        {
            "lancamento": lancamento,
            "quantidade_zonas": int(quantidade_zonas or 0),
            "quantidade_fora_padrao": int(quantidade_fora_padrao or 0),
        }
        for lancamento, quantidade_zonas, quantidade_fora_padrao in rows
    ]


def list_daily_launches(
    session: Session,
    target_date: date,
    turno: str | None = None,
    modelo: str | None = None,
) -> list[TensaoRetificadoresLancamento]:
    statement = select(TensaoRetificadoresLancamento).where(TensaoRetificadoresLancamento.data_referencia == target_date)
    if turno:
        statement = statement.where(TensaoRetificadoresLancamento.turno == turno)
    if modelo:
        statement = statement.where(TensaoRetificadoresLancamento.modelo == modelo)
    statement = statement.order_by(TensaoRetificadoresLancamento.turno, TensaoRetificadoresLancamento.modelo, TensaoRetificadoresLancamento.updated_at.desc())
    return list(session.scalars(statement).all())


def count_launches_with_outliers(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = select(func.count(TensaoRetificadoresLancamento.id)).where(
        TensaoRetificadoresLancamento.data_referencia == target_date
    )
    statement = statement.where(TensaoRetificadoresLancamento.total_zonas_fora_padrao > 0)
    if turno:
        statement = statement.where(TensaoRetificadoresLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def count_outlier_zones(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = (
        select(func.count(TensaoRetificadoresItem.id))
        .join(TensaoRetificadoresLancamento, TensaoRetificadoresLancamento.id == TensaoRetificadoresItem.lancamento_id)
        .where(TensaoRetificadoresLancamento.data_referencia == target_date)
        .where(TensaoRetificadoresItem.fora_padrao.is_(True))
    )
    if turno:
        statement = statement.where(TensaoRetificadoresLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def count_pending_launches(session: Session, target_date: date, turno: str | None = None) -> int:
    statement = select(func.count(TensaoRetificadoresLancamento.id)).where(
        TensaoRetificadoresLancamento.data_referencia == target_date
    )
    statement = statement.where(TensaoRetificadoresLancamento.status == STATUS_RASCUNHO)
    if turno:
        statement = statement.where(TensaoRetificadoresLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def _parse_tensao(raw_value) -> float | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError as error:
        raise TensaoRetificadoresValidationError(f"Valor de tensão inválido: '{text}'.") from error


def _coerce_tensao(raw_value) -> float | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    try:
        return float(str(raw_value).strip().replace(",", "."))
    except ValueError:
        return None


def _evaluate_tensao(valor_tensao: float | None) -> dict:
    if valor_tensao is None:
        return {"status": "neutral", "fora_padrao": None, "label": STATUS_LABELS["neutral"]}
    fora_padrao = valor_tensao < FAIXA_MINIMA or valor_tensao > FAIXA_MAXIMA
    if fora_padrao:
        return {"status": "out", "fora_padrao": True, "label": STATUS_LABELS["out"]}
    return {"status": "ok", "fora_padrao": False, "label": STATUS_LABELS["ok"]}


def _display_tensao(raw_value, parsed_value: float | None) -> str:
    if isinstance(raw_value, str):
        return raw_value.strip()
    if parsed_value is None:
        return ""
    return _format_tensao(parsed_value)


def _format_tensao(valor_tensao: float | None) -> str:
    if valor_tensao is None:
        return ""
    texto = f"{valor_tensao:.1f}"
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto
