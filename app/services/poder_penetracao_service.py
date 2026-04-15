from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Modelo, PoderPenetracaoItem, PoderPenetracaoLancamento, Responsavel


TOTAL_PONTOS = 30
VALOR_REFERENCIA = 7.9
STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"
STATUS_BADGES = {
    STATUS_RASCUNHO: "Rascunho",
    STATUS_CONCLUIDO: "Concluído",
}
STATUS_LABELS = {
    "approved": "Aprovado",
    "reproved": "Reprovado",
    "empty": "Vazio",
}


@dataclass(frozen=True)
class ContextOptions:
    responsaveis: list[Responsavel]
    modelos: list[Modelo]


@dataclass(frozen=True)
class ParsedContext:
    data_referencia: date
    semana_referencia: str
    modelo: str
    responsavel_nome: str
    cis: str | None
    velocidade: str | None
    tipo: str | None
    observacoes: str | None
    acao_corretiva: str | None


@dataclass(frozen=True)
class ProgressSummary:
    total: int
    preenchidos: int
    aprovados: int
    reprovados: int
    percentual_aprovacao: int


@dataclass(frozen=True)
class ExistingContextStatus:
    lancamento_id: int
    status: str
    label: str
    message: str
    action_label: str
    action_url: str


class PoderPenetracaoValidationError(ValueError):
    pass


def list_context_options(session: Session) -> ContextOptions:
    responsaveis = list(
        session.scalars(
            select(Responsavel)
            .where(Responsavel.ativo.is_(True))
            .order_by(Responsavel.nome)
        ).all()
    )
    modelos = list(
        session.scalars(
            select(Modelo)
            .where(Modelo.ativo.is_(True))
            .order_by(Modelo.nome)
        ).all()
    )
    return ContextOptions(responsaveis=responsaveis, modelos=modelos)


def default_week_label(target_date: date) -> str:
    iso_year, iso_week, _ = target_date.isocalendar()
    return f"{iso_year}-S{iso_week:02d}"


def parse_context_payload(form_data) -> ParsedContext:
    data_value = (form_data.get("data_referencia") or "").strip()
    modelo = (form_data.get("modelo") or "").strip()
    responsavel_nome = (form_data.get("responsavel_nome") or "").strip()
    cis = (form_data.get("cis") or "").strip() or None
    velocidade = (form_data.get("velocidade") or "").strip() or None
    tipo = (form_data.get("tipo") or "").strip() or None
    observacoes = (form_data.get("observacoes") or "").strip() or None
    acao_corretiva = (form_data.get("acao_corretiva") or "").strip() or None

    missing = []
    if not data_value:
        missing.append("data")
    if not modelo:
        missing.append("modelo")
    if not responsavel_nome:
        missing.append("responsável")
    if missing:
        raise PoderPenetracaoValidationError(f"Preencha: {', '.join(missing)}.")

    try:
        parsed_date = date.fromisoformat(data_value)
    except ValueError as error:
        raise PoderPenetracaoValidationError("Data inválida para o lançamento.") from error

    semana_referencia = (form_data.get("semana_referencia") or "").strip() or default_week_label(parsed_date)

    return ParsedContext(
        data_referencia=parsed_date,
        semana_referencia=semana_referencia,
        modelo=modelo,
        responsavel_nome=responsavel_nome,
        cis=cis,
        velocidade=velocidade,
        tipo=tipo,
        observacoes=observacoes,
        acao_corretiva=acao_corretiva,
    )


def build_point_rows(existing_rows: dict[int, dict] | None = None) -> list[dict]:
    existing_rows = existing_rows or {}
    rows: list[dict] = []
    for ponto_numero in range(1, TOTAL_PONTOS + 1):
        existing = existing_rows.get(ponto_numero, {})
        raw_value = existing.get("valor_medido")
        valor = _coerce_value(raw_value)
        status = _evaluate_value(valor)
        rows.append(
            {
                "ponto_numero": ponto_numero,
                "valor_medido": _display_value(raw_value, valor),
                "status": status["status"],
                "status_label": status["label"],
                "aprovado": status["status"] == "approved",
                "reprovado": status["status"] == "reproved",
                "faixa_texto": f"Referência: ≥ {VALOR_REFERENCIA}",
            }
        )
    return rows


def summarize_progress(point_rows: list[dict]) -> ProgressSummary:
    total = len(point_rows)
    preenchidos = sum(1 for row in point_rows if str(row.get("valor_medido") or "").strip())
    aprovados = sum(1 for row in point_rows if row.get("aprovado"))
    reprovados = sum(1 for row in point_rows if row.get("reprovado"))
    percentual = int(round((aprovados / preenchidos) * 100)) if preenchidos else 0
    return ProgressSummary(
        total=total,
        preenchidos=preenchidos,
        aprovados=aprovados,
        reprovados=reprovados,
        percentual_aprovacao=percentual,
    )


def find_existing_lancamento_for_context(
    session: Session,
    semana_referencia: str,
    modelo: str,
    cis: str | None,
    exclude_id: int | None = None,
) -> PoderPenetracaoLancamento | None:
    statement = (
        select(PoderPenetracaoLancamento)
        .where(PoderPenetracaoLancamento.semana_referencia == semana_referencia)
        .where(PoderPenetracaoLancamento.modelo == modelo)
        .where(PoderPenetracaoLancamento.cis == cis)
        .order_by(PoderPenetracaoLancamento.updated_at.desc(), PoderPenetracaoLancamento.id.desc())
    )
    if exclude_id is not None:
        statement = statement.where(PoderPenetracaoLancamento.id != exclude_id)
    return session.scalars(statement).first()


def build_existing_context_status(lancamento: PoderPenetracaoLancamento | None) -> ExistingContextStatus | None:
    if lancamento is None:
        return None
    if lancamento.status == STATUS_RASCUNHO:
        return ExistingContextStatus(
            lancamento_id=lancamento.id,
            status=lancamento.status,
            label=STATUS_BADGES[lancamento.status],
            message="Já existe lançamento para este contexto semanal.",
            action_label="Continuar edição",
            action_url=f"/poder-penetracao/lancamentos/{lancamento.id}/editar",
        )
    return ExistingContextStatus(
        lancamento_id=lancamento.id,
        status=lancamento.status,
        label=STATUS_BADGES[lancamento.status],
        message="Já existe lançamento para este contexto semanal.",
        action_label="Visualizar",
        action_url=f"/poder-penetracao/lancamentos/{lancamento.id}",
    )


def get_lancamento(session: Session, lancamento_id: int) -> PoderPenetracaoLancamento | None:
    statement = (
        select(PoderPenetracaoLancamento)
        .options(joinedload(PoderPenetracaoLancamento.itens))
        .where(PoderPenetracaoLancamento.id == lancamento_id)
    )
    return session.scalars(statement).unique().first()


def get_existing_row_map(lancamento: PoderPenetracaoLancamento) -> dict[int, dict]:
    return {
        row.ponto_numero: {"valor_medido": row.valor_medido, "aprovado": row.aprovado}
        for row in lancamento.itens
    }


def save_lancamento(
    session: Session,
    context: ParsedContext,
    form_data,
    status: str,
    lancamento_id: int | None = None,
) -> PoderPenetracaoLancamento:
    lancamento = None
    if lancamento_id is not None:
        lancamento = get_lancamento(session, lancamento_id)
        if lancamento is None:
            raise PoderPenetracaoValidationError("Lançamento não encontrado.")
        if lancamento.status == STATUS_CONCLUIDO:
            raise PoderPenetracaoValidationError("Lançamentos concluídos não podem ser alterados nesta etapa.")
    else:
        existing_for_context = find_existing_lancamento_for_context(
            session,
            context.semana_referencia,
            context.modelo,
            context.cis,
        )
        if existing_for_context is not None:
            raise PoderPenetracaoValidationError("Já existe lançamento para este contexto semanal. Use continuar edição ou visualizar.")

    if lancamento is None:
        lancamento = PoderPenetracaoLancamento()
        session.add(lancamento)

    lancamento.data_referencia = context.data_referencia
    lancamento.semana_referencia = context.semana_referencia
    lancamento.modelo = context.modelo
    lancamento.responsavel_nome = context.responsavel_nome
    lancamento.cis = context.cis
    lancamento.velocidade = context.velocidade
    lancamento.tipo = context.tipo
    lancamento.observacoes = context.observacoes
    lancamento.acao_corretiva = context.acao_corretiva
    lancamento.status = status

    session.flush()

    existing_rows = {row.ponto_numero: row for row in lancamento.itens}
    valores_preenchidos: list[float] = []
    aprovados = 0
    reprovados = 0
    for ponto_numero in range(1, TOTAL_PONTOS + 1):
        valor = _parse_value(form_data.get(f"ponto_{ponto_numero}"))
        status_info = _evaluate_value(valor)
        row = existing_rows.get(ponto_numero)
        if row is None:
            row = PoderPenetracaoItem(ponto_numero=ponto_numero)
            lancamento.itens.append(row)
        row.valor_medido = valor
        row.aprovado = None if valor is None else bool(status_info["status"] == "approved")
        if valor is not None:
            valores_preenchidos.append(valor)
            if status_info["status"] == "approved":
                aprovados += 1
            elif status_info["status"] == "reproved":
                reprovados += 1

    total_pontos = len(valores_preenchidos)
    lancamento.total_pontos = total_pontos
    lancamento.total_aprovados = aprovados
    lancamento.total_reprovados = reprovados
    lancamento.percentual_aprovacao = round((aprovados / total_pontos) * 100, 2) if total_pontos else 0.0
    lancamento.menor_valor = min(valores_preenchidos) if valores_preenchidos else None

    session.commit()
    session.refresh(lancamento)
    return get_lancamento(session, lancamento.id) or lancamento


def list_history(
    session: Session,
    semana_referencia: str | None = None,
    modelo: str | None = None,
    data_referencia: str | None = None,
    status: str | None = None,
) -> list[PoderPenetracaoLancamento]:
    statement = select(PoderPenetracaoLancamento).order_by(
        PoderPenetracaoLancamento.data_referencia.desc(),
        PoderPenetracaoLancamento.created_at.desc(),
    )
    if semana_referencia:
        statement = statement.where(PoderPenetracaoLancamento.semana_referencia == semana_referencia)
    if modelo:
        statement = statement.where(PoderPenetracaoLancamento.modelo == modelo)
    if data_referencia:
        statement = statement.where(PoderPenetracaoLancamento.data_referencia == date.fromisoformat(data_referencia))
    if status:
        statement = statement.where(PoderPenetracaoLancamento.status == status)
    return list(session.scalars(statement).all())


def list_weekly_launches(session: Session, target_date: date) -> list[PoderPenetracaoLancamento]:
    week_label = default_week_label(target_date)
    statement = (
        select(PoderPenetracaoLancamento)
        .where(PoderPenetracaoLancamento.semana_referencia == week_label)
        .order_by(PoderPenetracaoLancamento.updated_at.desc(), PoderPenetracaoLancamento.id.desc())
    )
    return list(session.scalars(statement).all())


def count_pending_launches(session: Session, target_date: date) -> int:
    week_label = default_week_label(target_date)
    statement = (
        select(func.count(PoderPenetracaoLancamento.id))
        .where(PoderPenetracaoLancamento.semana_referencia == week_label)
        .where(PoderPenetracaoLancamento.status == STATUS_RASCUNHO)
    )
    return int(session.scalar(statement) or 0)


def count_reproved_points(session: Session, target_date: date) -> int:
    week_label = default_week_label(target_date)
    statement = (
        select(func.count(PoderPenetracaoItem.id))
        .join(PoderPenetracaoLancamento, PoderPenetracaoLancamento.id == PoderPenetracaoItem.lancamento_id)
        .where(PoderPenetracaoLancamento.semana_referencia == week_label)
        .where(PoderPenetracaoItem.aprovado.is_(False))
    )
    return int(session.scalar(statement) or 0)


def average_approval(session: Session, target_date: date) -> float:
    week_label = default_week_label(target_date)
    statement = select(func.avg(PoderPenetracaoLancamento.percentual_aprovacao)).where(
        PoderPenetracaoLancamento.semana_referencia == week_label
    )
    value = session.scalar(statement)
    return float(value or 0.0)


def _parse_value(raw_value) -> float | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError as error:
        raise PoderPenetracaoValidationError(f"Valor inválido no ensaio: '{text}'.") from error


def _coerce_value(raw_value) -> float | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    try:
        return float(str(raw_value).strip().replace(",", "."))
    except ValueError:
        return None


def _evaluate_value(valor_medido: float | None) -> dict:
    if valor_medido is None:
        return {"status": "empty", "label": STATUS_LABELS["empty"]}
    if valor_medido >= VALOR_REFERENCIA:
        return {"status": "approved", "label": STATUS_LABELS["approved"]}
    return {"status": "reproved", "label": STATUS_LABELS["reproved"]}


def _display_value(raw_value, parsed_value: float | None) -> str:
    if isinstance(raw_value, str):
        return raw_value.strip()
    if parsed_value is None:
        return ""
    return _format_value(parsed_value)


def _format_value(valor: float | None) -> str:
    if valor is None:
        return ""
    texto = f"{valor:.1f}"
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto
