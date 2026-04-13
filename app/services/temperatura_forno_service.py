from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Responsavel, TemperaturaFornoItem, TemperaturaFornoLancamento


STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"
STATUS_BADGES = {
    STATUS_RASCUNHO: "Rascunho",
    STATUS_CONCLUIDO: "Concluído",
}
STATUS_LABELS = {
    "ok": "Dentro da faixa",
    "out": "Fora do padrão",
    "neutral": "Não avaliado",
}
ZONA_SPECS = [
    {"zona_numero": 1, "nominal": 90.0, "tolerancia": 30.0},
    {"zona_numero": 2, "nominal": 90.0, "tolerancia": 30.0},
    {"zona_numero": 3, "nominal": 130.0, "tolerancia": 30.0},
    {"zona_numero": 4, "nominal": 170.0, "tolerancia": 20.0},
    {"zona_numero": 5, "nominal": 160.0, "tolerancia": 20.0},
    {"zona_numero": 6, "nominal": 180.0, "tolerancia": 20.0},
    {"zona_numero": 7, "nominal": 180.0, "tolerancia": 20.0},
    {"zona_numero": 8, "nominal": 180.0, "tolerancia": 20.0},
    {"zona_numero": 9, "nominal": 180.0, "tolerancia": 20.0},
    {"zona_numero": 10, "nominal": 180.0, "tolerancia": 20.0},
    {"zona_numero": 11, "nominal": 180.0, "tolerancia": 20.0},
    {"zona_numero": 12, "nominal": 180.0, "tolerancia": 20.0},
]


@dataclass(frozen=True)
class ContextOptions:
    responsaveis: list[Responsavel]


@dataclass(frozen=True)
class ParsedContext:
    data_referencia: date
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


class TemperaturaFornoValidationError(ValueError):
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
    responsavel_nome = (form_data.get("responsavel_nome") or "").strip()
    observacoes_gerais = (form_data.get("observacoes_gerais") or "").strip() or None

    missing = []
    if not data_value:
        missing.append("data")
    if not responsavel_nome:
        missing.append("responsável")
    if missing:
        raise TemperaturaFornoValidationError(f"Preencha: {', '.join(missing)}.")

    try:
        parsed_date = date.fromisoformat(data_value)
    except ValueError as error:
        raise TemperaturaFornoValidationError("Data inválida para o lançamento.") from error

    return ParsedContext(
        data_referencia=parsed_date,
        responsavel_nome=responsavel_nome,
        observacoes_gerais=observacoes_gerais,
    )


def build_zone_rows(existing_rows: dict[int, dict] | None = None) -> list[dict]:
    existing_rows = existing_rows or {}
    rows: list[dict] = []
    for spec in ZONA_SPECS:
        faixa_min = spec["nominal"] - spec["tolerancia"]
        faixa_max = spec["nominal"] + spec["tolerancia"]
        existing = existing_rows.get(spec["zona_numero"], {})
        raw_value = existing.get("valor_temperatura")
        valor = _coerce_temperature(raw_value)
        status = _evaluate_zone(valor, faixa_min, faixa_max)
        rows.append(
            {
                "zona_numero": spec["zona_numero"],
                "faixa_min": faixa_min,
                "faixa_max": faixa_max,
                "faixa_texto": f"{int(faixa_min)} a {int(faixa_max)} °C",
                "valor_temperatura": _display_temperature(raw_value, valor),
                "status": status["status"],
                "status_label": status["label"],
                "fora_padrao": status["fora_padrao"],
                "is_out": status["status"] == "out",
            }
        )
    return rows


def summarize_progress(zone_rows: list[dict]) -> ProgressSummary:
    total = len(zone_rows)
    preenchidos = sum(1 for row in zone_rows if str(row.get("valor_temperatura") or "").strip())
    fora_padrao = sum(1 for row in zone_rows if row.get("fora_padrao"))
    percentual = int(round((preenchidos / total) * 100)) if total else 0
    return ProgressSummary(total=total, preenchidos=preenchidos, fora_padrao=fora_padrao, percentual=percentual)


def find_existing_lancamento_for_context(
    session: Session,
    data_referencia: date,
    exclude_id: int | None = None,
) -> TemperaturaFornoLancamento | None:
    statement = (
        select(TemperaturaFornoLancamento)
        .where(TemperaturaFornoLancamento.data_referencia == data_referencia)
        .order_by(TemperaturaFornoLancamento.updated_at.desc(), TemperaturaFornoLancamento.id.desc())
    )
    if exclude_id is not None:
        statement = statement.where(TemperaturaFornoLancamento.id != exclude_id)
    return session.scalars(statement).first()


def build_existing_context_status(
    lancamento: TemperaturaFornoLancamento | None,
) -> ExistingContextStatus | None:
    if lancamento is None:
        return None
    if lancamento.status == STATUS_RASCUNHO:
        return ExistingContextStatus(
            lancamento_id=lancamento.id,
            status=lancamento.status,
            label=STATUS_BADGES[lancamento.status],
            message="Já existe lançamento para esta data.",
            action_label="Continuar edição",
            action_url=f"/temperatura-forno-ed/lancamentos/{lancamento.id}/editar",
        )
    return ExistingContextStatus(
        lancamento_id=lancamento.id,
        status=lancamento.status,
        label=STATUS_BADGES[lancamento.status],
        message="Já existe lançamento para esta data.",
        action_label="Visualizar",
        action_url=f"/temperatura-forno-ed/lancamentos/{lancamento.id}",
    )


def get_lancamento(session: Session, lancamento_id: int) -> TemperaturaFornoLancamento | None:
    statement = (
        select(TemperaturaFornoLancamento)
        .options(joinedload(TemperaturaFornoLancamento.itens))
        .where(TemperaturaFornoLancamento.id == lancamento_id)
    )
    return session.scalars(statement).unique().first()


def get_existing_row_map(lancamento: TemperaturaFornoLancamento) -> dict[int, dict]:
    return {
        row.zona_numero: {
            "valor_temperatura": row.valor_temperatura,
            "faixa_min": row.faixa_min,
            "faixa_max": row.faixa_max,
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
) -> TemperaturaFornoLancamento:
    lancamento = None
    if lancamento_id is not None:
        lancamento = get_lancamento(session, lancamento_id)
        if lancamento is None:
            raise TemperaturaFornoValidationError("Lançamento não encontrado.")
        if lancamento.status == STATUS_CONCLUIDO:
            raise TemperaturaFornoValidationError("Lançamentos concluídos não podem ser alterados nesta etapa.")
    else:
        existing_for_context = find_existing_lancamento_for_context(session, context.data_referencia)
        if existing_for_context is not None:
            raise TemperaturaFornoValidationError("Já existe lançamento para esta data. Use continuar edição ou visualizar.")

    if lancamento is None:
        lancamento = TemperaturaFornoLancamento()
        session.add(lancamento)

    lancamento.data_referencia = context.data_referencia
    lancamento.responsavel_nome = context.responsavel_nome
    lancamento.status = status
    lancamento.observacoes_gerais = context.observacoes_gerais

    session.flush()

    existing_rows = {row.zona_numero: row for row in lancamento.itens}
    total_fora_padrao = 0
    for spec in ZONA_SPECS:
        zona_numero = spec["zona_numero"]
        faixa_min = spec["nominal"] - spec["tolerancia"]
        faixa_max = spec["nominal"] + spec["tolerancia"]
        valor = _parse_temperature(form_data.get(f"zona_{zona_numero}"))
        avaliacao = _evaluate_zone(valor, faixa_min, faixa_max)
        if avaliacao["fora_padrao"]:
            total_fora_padrao += 1
        row = existing_rows.get(zona_numero)
        if row is None:
            row = TemperaturaFornoItem(zona_numero=zona_numero)
            lancamento.itens.append(row)
        row.valor_temperatura = valor
        row.faixa_min = faixa_min
        row.faixa_max = faixa_max
        row.fora_padrao = bool(avaliacao["fora_padrao"])

    lancamento.total_zonas_fora_padrao = total_fora_padrao
    session.commit()
    session.refresh(lancamento)
    return get_lancamento(session, lancamento.id) or lancamento


def list_history(
    session: Session,
    data_inicial: str | None = None,
    data_final: str | None = None,
    status: str | None = None,
    somente_fora_padrao: bool = False,
) -> list[dict]:
    statement = (
        select(
            TemperaturaFornoLancamento,
            func.sum(case((TemperaturaFornoItem.valor_temperatura.is_not(None), 1), else_=0)).label("quantidade_zonas"),
            func.sum(case((TemperaturaFornoItem.fora_padrao.is_(True), 1), else_=0)).label("quantidade_fora_padrao"),
        )
        .outerjoin(TemperaturaFornoItem, TemperaturaFornoItem.lancamento_id == TemperaturaFornoLancamento.id)
        .group_by(TemperaturaFornoLancamento.id)
        .order_by(TemperaturaFornoLancamento.data_referencia.desc(), TemperaturaFornoLancamento.created_at.desc())
    )
    if data_inicial:
        statement = statement.where(TemperaturaFornoLancamento.data_referencia >= date.fromisoformat(data_inicial))
    if data_final:
        statement = statement.where(TemperaturaFornoLancamento.data_referencia <= date.fromisoformat(data_final))
    if status:
        statement = statement.where(TemperaturaFornoLancamento.status == status)
    if somente_fora_padrao:
        statement = statement.having(func.sum(case((TemperaturaFornoItem.fora_padrao.is_(True), 1), else_=0)) > 0)

    rows = session.execute(statement).all()
    return [
        {
            "lancamento": lancamento,
            "quantidade_zonas": int(quantidade_zonas or 0),
            "quantidade_fora_padrao": int(quantidade_fora_padrao or 0),
        }
        for lancamento, quantidade_zonas, quantidade_fora_padrao in rows
    ]


def list_daily_launches(session: Session, target_date: date) -> list[TemperaturaFornoLancamento]:
    statement = (
        select(TemperaturaFornoLancamento)
        .where(TemperaturaFornoLancamento.data_referencia == target_date)
        .order_by(TemperaturaFornoLancamento.updated_at.desc())
    )
    return list(session.scalars(statement).all())


def count_launches_with_outliers(session: Session, target_date: date) -> int:
    statement = select(func.count(TemperaturaFornoLancamento.id)).where(
        TemperaturaFornoLancamento.data_referencia == target_date
    )
    statement = statement.where(TemperaturaFornoLancamento.total_zonas_fora_padrao > 0)
    return int(session.scalar(statement) or 0)


def count_pending_launches(session: Session, target_date: date) -> int:
    statement = select(func.count(TemperaturaFornoLancamento.id)).where(
        TemperaturaFornoLancamento.data_referencia == target_date
    )
    statement = statement.where(TemperaturaFornoLancamento.status == STATUS_RASCUNHO)
    return int(session.scalar(statement) or 0)


def _parse_temperature(raw_value) -> float | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError as error:
        raise TemperaturaFornoValidationError(f"Temperatura inválida: '{text}'.") from error


def _coerce_temperature(raw_value) -> float | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    try:
        return float(str(raw_value).strip().replace(",", "."))
    except ValueError:
        return None


def _evaluate_zone(valor_temperatura: float | None, faixa_min: float, faixa_max: float) -> dict:
    if valor_temperatura is None:
        return {"status": "neutral", "fora_padrao": None, "label": STATUS_LABELS["neutral"]}
    fora_padrao = valor_temperatura < faixa_min or valor_temperatura > faixa_max
    if fora_padrao:
        return {"status": "out", "fora_padrao": True, "label": STATUS_LABELS["out"]}
    return {"status": "ok", "fora_padrao": False, "label": STATUS_LABELS["ok"]}


def _display_temperature(raw_value, parsed_value: float | None) -> str:
    if isinstance(raw_value, str):
        return raw_value.strip()
    if parsed_value is None:
        return ""
    return _format_temperature(parsed_value)


def _format_temperature(valor_temperatura: float | None) -> str:
    if valor_temperatura is None:
        return ""
    texto = f"{valor_temperatura:.1f}"
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto
