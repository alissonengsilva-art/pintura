from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Responsavel, RugosidadeItem, RugosidadeLancamento


MODELOS_FIXOS = ["521", "226", "551", "598", "291"]
LIMITE_REFERENCIA = 14.0
STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"
STATUS_BADGES = {
    STATUS_RASCUNHO: "Rascunho",
    STATUS_CONCLUIDO: "Concluído",
}
STATUS_LABELS = {
    "ok": "OK",
    "outlier": "Fora do padrão",
    "empty": "Vazio",
}


@dataclass(frozen=True)
class ContextOptions:
    responsaveis: list[Responsavel]


@dataclass(frozen=True)
class ParsedContext:
    data_referencia: date
    sequencia: str
    responsavel_nome: str
    observacoes_gerais: str | None


@dataclass(frozen=True)
class MatrixSummary:
    total_modelos: int
    preenchidos: int
    fora_padrao: int
    percentual_preenchido: int


@dataclass(frozen=True)
class ExistingContextStatus:
    lancamento_id: int
    status: str
    label: str
    message: str
    action_label: str
    action_url: str


class RugosidadeValidationError(ValueError):
    pass


def list_context_options(session: Session) -> ContextOptions:
    responsaveis = list(
        session.scalars(
            select(Responsavel)
            .where(Responsavel.ativo.is_(True))
            .order_by(Responsavel.nome)
        ).all()
    )
    return ContextOptions(responsaveis=responsaveis)


def parse_context_payload(form_data) -> ParsedContext:
    data_value = (form_data.get("data_referencia") or "").strip()
    sequencia = (form_data.get("sequencia") or "").strip()
    responsavel_nome = (form_data.get("responsavel_nome") or "").strip()
    observacoes_gerais = (form_data.get("observacoes_gerais") or "").strip() or None

    missing = []
    if not data_value:
        missing.append("data")
    if not sequencia:
        missing.append("sequência")
    if not responsavel_nome:
        missing.append("responsável")
    if missing:
        raise RugosidadeValidationError(f"Preencha: {', '.join(missing)}.")

    try:
        parsed_date = date.fromisoformat(data_value)
    except ValueError as error:
        raise RugosidadeValidationError("Data inválida para o lançamento.") from error

    return ParsedContext(
        data_referencia=parsed_date,
        sequencia=sequencia,
        responsavel_nome=responsavel_nome,
        observacoes_gerais=observacoes_gerais,
    )


def build_matrix_rows(existing_rows: dict[str, dict] | None = None) -> list[dict]:
    existing_rows = existing_rows or {}
    rows: list[dict] = []
    for modelo_codigo in MODELOS_FIXOS:
        existing = existing_rows.get(modelo_codigo, {})
        raw_value = existing.get("valor_rugosidade")
        valor = _coerce_value(raw_value)
        status = _evaluate_value(valor)
        rows.append(
            {
                "modelo_codigo": modelo_codigo,
                "limite_referencia": _format_value(LIMITE_REFERENCIA),
                "valor_rugosidade": _display_value(raw_value, valor),
                "status": status["status"],
                "status_label": status["label"],
                "fora_padrao": status["status"] == "outlier",
                "dentro_padrao": status["status"] == "ok",
            }
        )
    return rows


def summarize_matrix(matrix_rows: list[dict]) -> MatrixSummary:
    total_modelos = len(matrix_rows)
    preenchidos = sum(1 for row in matrix_rows if str(row.get("valor_rugosidade") or "").strip())
    fora_padrao = sum(1 for row in matrix_rows if row.get("fora_padrao"))
    percentual_preenchido = int(round((preenchidos / total_modelos) * 100)) if total_modelos else 0
    return MatrixSummary(
        total_modelos=total_modelos,
        preenchidos=preenchidos,
        fora_padrao=fora_padrao,
        percentual_preenchido=percentual_preenchido,
    )


def find_existing_lancamento_for_context(
    session: Session,
    data_referencia: date,
    sequencia: str,
    exclude_id: int | None = None,
) -> RugosidadeLancamento | None:
    statement = (
        select(RugosidadeLancamento)
        .where(RugosidadeLancamento.data_referencia == data_referencia)
        .where(RugosidadeLancamento.sequencia == sequencia)
        .order_by(RugosidadeLancamento.updated_at.desc(), RugosidadeLancamento.id.desc())
    )
    if exclude_id is not None:
        statement = statement.where(RugosidadeLancamento.id != exclude_id)
    return session.scalars(statement).first()


def build_existing_context_status(lancamento: RugosidadeLancamento | None) -> ExistingContextStatus | None:
    if lancamento is None:
        return None
    if lancamento.status == STATUS_RASCUNHO:
        return ExistingContextStatus(
            lancamento_id=lancamento.id,
            status=lancamento.status,
            label=STATUS_BADGES[lancamento.status],
            message="Já existe lançamento para esta data e sequência.",
            action_label="Continuar edição",
            action_url=f"/rugosidade/lancamentos/{lancamento.id}/editar",
        )
    return ExistingContextStatus(
        lancamento_id=lancamento.id,
        status=lancamento.status,
        label=STATUS_BADGES[lancamento.status],
        message="Já existe lançamento para esta data e sequência.",
        action_label="Visualizar",
        action_url=f"/rugosidade/lancamentos/{lancamento.id}",
    )


def get_lancamento(session: Session, lancamento_id: int) -> RugosidadeLancamento | None:
    statement = (
        select(RugosidadeLancamento)
        .options(joinedload(RugosidadeLancamento.itens))
        .where(RugosidadeLancamento.id == lancamento_id)
    )
    return session.scalars(statement).unique().first()


def get_existing_row_map(lancamento: RugosidadeLancamento) -> dict[str, dict]:
    return {
        row.modelo_codigo: {"valor_rugosidade": row.valor_rugosidade, "fora_padrao": row.fora_padrao}
        for row in lancamento.itens
    }


def save_lancamento(
    session: Session,
    context: ParsedContext,
    form_data,
    status: str,
    lancamento_id: int | None = None,
) -> RugosidadeLancamento:
    lancamento = None
    if lancamento_id is not None:
        lancamento = get_lancamento(session, lancamento_id)
        if lancamento is None:
            raise RugosidadeValidationError("Lançamento não encontrado.")
        if lancamento.status == STATUS_CONCLUIDO:
            raise RugosidadeValidationError("Lançamentos concluídos não podem ser alterados nesta etapa.")
    else:
        existing_for_context = find_existing_lancamento_for_context(
            session,
            context.data_referencia,
            context.sequencia,
        )
        if existing_for_context is not None:
            raise RugosidadeValidationError("Já existe lançamento para esta data e sequência. Use continuar edição ou visualizar.")

    if lancamento is None:
        lancamento = RugosidadeLancamento()
        session.add(lancamento)

    lancamento.data_referencia = context.data_referencia
    lancamento.sequencia = context.sequencia
    lancamento.responsavel_nome = context.responsavel_nome
    lancamento.observacoes_gerais = context.observacoes_gerais
    lancamento.status = status

    session.flush()

    existing_rows = {row.modelo_codigo: row for row in lancamento.itens}
    fora_padrao_total = 0
    for modelo_codigo in MODELOS_FIXOS:
        valor = _parse_value(form_data.get(f"modelo_{modelo_codigo}"))
        status_info = _evaluate_value(valor)
        row = existing_rows.get(modelo_codigo)
        if row is None:
            row = RugosidadeItem(modelo_codigo=modelo_codigo)
            lancamento.itens.append(row)
        row.valor_rugosidade = valor
        row.limite_referencia = LIMITE_REFERENCIA
        row.fora_padrao = None if valor is None else bool(status_info["status"] == "outlier")
        if row.fora_padrao:
            fora_padrao_total += 1

    lancamento.total_modelos_fora_padrao = fora_padrao_total

    session.commit()
    session.refresh(lancamento)
    return get_lancamento(session, lancamento.id) or lancamento


def list_history(
    session: Session,
    data_referencia: str | None = None,
    sequencia: str | None = None,
    status: str | None = None,
    somente_desvio: bool = False,
) -> list[RugosidadeLancamento]:
    statement = select(RugosidadeLancamento).order_by(
        RugosidadeLancamento.data_referencia.desc(),
        RugosidadeLancamento.created_at.desc(),
    )
    if data_referencia:
        statement = statement.where(RugosidadeLancamento.data_referencia == date.fromisoformat(data_referencia))
    if sequencia:
        statement = statement.where(RugosidadeLancamento.sequencia == sequencia)
    if status:
        statement = statement.where(RugosidadeLancamento.status == status)
    if somente_desvio:
        statement = statement.where(RugosidadeLancamento.total_modelos_fora_padrao > 0)
    return list(session.scalars(statement).all())


def list_daily_launches(session: Session, target_date: date) -> list[RugosidadeLancamento]:
    statement = (
        select(RugosidadeLancamento)
        .where(RugosidadeLancamento.data_referencia == target_date)
        .order_by(RugosidadeLancamento.updated_at.desc(), RugosidadeLancamento.id.desc())
    )
    return list(session.scalars(statement).all())


def count_pending_launches(session: Session, target_date: date) -> int:
    statement = (
        select(func.count(RugosidadeLancamento.id))
        .where(RugosidadeLancamento.data_referencia == target_date)
        .where(RugosidadeLancamento.status == STATUS_RASCUNHO)
    )
    return int(session.scalar(statement) or 0)


def count_outlier_models(session: Session, target_date: date) -> int:
    statement = (
        select(func.count(RugosidadeItem.id))
        .join(RugosidadeLancamento, RugosidadeLancamento.id == RugosidadeItem.lancamento_id)
        .where(RugosidadeLancamento.data_referencia == target_date)
        .where(RugosidadeItem.fora_padrao.is_(True))
    )
    return int(session.scalar(statement) or 0)


def average_filled_percentage(session: Session, target_date: date) -> float:
    launches = list_daily_launches(session, target_date)
    if not launches:
        return 0.0
    percentages: list[float] = []
    for lancamento in launches:
        preenchidos = sum(1 for item in lancamento.itens if item.valor_rugosidade is not None)
        percentages.append((preenchidos / len(MODELOS_FIXOS)) * 100)
    return round(sum(percentages) / len(percentages), 2)


def _parse_value(raw_value) -> float | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError as error:
        raise RugosidadeValidationError(f"Valor inválido de rugosidade: '{text}'.") from error


def _coerce_value(raw_value) -> float | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    try:
        return float(str(raw_value).strip().replace(",", "."))
    except ValueError:
        return None


def _evaluate_value(valor_rugosidade: float | None) -> dict:
    if valor_rugosidade is None:
        return {"status": "empty", "label": STATUS_LABELS["empty"]}
    if valor_rugosidade <= LIMITE_REFERENCIA:
        return {"status": "ok", "label": STATUS_LABELS["ok"]}
    return {"status": "outlier", "label": STATUS_LABELS["outlier"]}


def _display_value(raw_value, parsed_value: float | None) -> str:
    if isinstance(raw_value, str):
        return raw_value.strip()
    if parsed_value is None:
        return ""
    return _format_value(parsed_value)


def _format_value(valor: float | None) -> str:
    if valor is None:
        return ""
    texto = f"{valor:.3f}"
    texto = texto.rstrip("0").rstrip(".")
    return texto
