from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload, object_session

from app.models import EDLancamento, EDLancamentoItem, OperationalModuleItem, Responsavel, Turno
from app.services import operational_module_item_service


TIPO_DIA_OPTIONS = [
    ("normal", "Normal"),
    ("sabado", "Sábado"),
    ("domingo", "Domingo"),
    ("parada", "Parada"),
]

SETOR_OPTIONS = ["Laboratório", "PT/ED"]
STATUS_RASCUNHO = "rascunho"
STATUS_CONCLUIDO = "concluido"
STATUS_BADGES = {
    STATUS_RASCUNHO: "Rascunho",
    STATUS_CONCLUIDO: "Concluído",
}
EVALUATION_LABELS = {
    "ok": "Dentro do esperado",
    "out": "Fora do esperado",
    "neutral": "Não avaliado",
}
_SHIFT_CODES = {"1", "2", "3"}


@dataclass(frozen=True)
class ContextOptions:
    responsaveis: list[Responsavel]
    turnos: list[Turno]


@dataclass(frozen=True)
class ParsedContext:
    data_referencia: date
    tipo_dia: str
    setor: str
    turno: str
    responsavel_nome: str
    observacoes_gerais: str | None


@dataclass(frozen=True)
class ProgressSummary:
    total: int
    preenchidos: int
    percentual: int


@dataclass(frozen=True)
class ExistingContextStatus:
    lancamento_id: int
    status: str
    label: str
    message: str
    action_label: str
    action_url: str


class EDValidationError(ValueError):
    pass


_number_pattern = re.compile(r"-?\d+(?:[\.,]\d+)?")
_range_pattern = re.compile(r"(-?\d+(?:[\.,]\d+)?)\s*[-–]\s*(-?\d+(?:[\.,]\d+)?)")


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
            .order_by(case_turno_order(Turno.codigo), Turno.codigo, Turno.nome)
        ).all()
    )
    return ContextOptions(responsaveis=responsaveis, turnos=turnos)


def case_turno_order(column):
    return case((column.in_(["1", "2", "3"]), 0), else_=1)


def parse_context_payload(form_data) -> ParsedContext:
    data_value = (form_data.get("data_referencia") or "").strip()
    tipo_dia = (form_data.get("tipo_dia") or "").strip().lower()
    setor = (form_data.get("setor") or "").strip()
    turno = (form_data.get("turno") or "").strip()
    responsavel_nome = (form_data.get("responsavel_nome") or "").strip()
    observacoes_gerais = (form_data.get("observacoes_gerais") or "").strip() or None

    missing_fields = []
    if not data_value:
        missing_fields.append("data")
    if not tipo_dia:
        missing_fields.append("tipo do dia")
    if not setor:
        missing_fields.append("setor")
    if not turno:
        missing_fields.append("turno")
    if not responsavel_nome:
        missing_fields.append("responsável")
    if missing_fields:
        raise EDValidationError(f"Preencha: {', '.join(missing_fields)}.")

    try:
        parsed_date = date.fromisoformat(data_value)
    except ValueError as error:
        raise EDValidationError("Data inválida para o lançamento.") from error

    return ParsedContext(
        data_referencia=parsed_date,
        tipo_dia=tipo_dia,
        setor=setor,
        turno=turno,
        responsavel_nome=responsavel_nome,
        observacoes_gerais=observacoes_gerais,
    )


def load_items_for_context(session: Session, setor: str, turno: str) -> list[OperationalModuleItem]:
    setor_tipo = _resolve_setor_tipo(setor)
    items = operational_module_item_service.get_items_by_module_and_setor(session, "ed", setor_tipo)
    filtered = [item for item in items if _matches_turno(item, turno)]
    return _deduplicate_items(filtered)


def list_items_by_ids(session: Session, item_ids: list[int]) -> list[OperationalModuleItem]:
    if not item_ids:
        return []
    items = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.id.in_(item_ids))
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.operacao, OperationalModuleItem.id)
        ).all()
    )
    order_map = {item_id: index for index, item_id in enumerate(item_ids)}
    return sorted(items, key=lambda item: (order_map.get(item.id, 9999), item.ordem, item.id))


def build_item_rows(items: list[OperationalModuleItem], existing_rows: dict[int, dict] | None = None) -> list[dict]:
    rows = []
    existing_rows = existing_rows or {}
    for item in items:
        existing = existing_rows.get(item.id, {})
        valor = existing.get("valor_informado")
        observacao = existing.get("observacao_item")
        evaluation = evaluate_parameter(item.parametro, valor)
        rows.append(
            {
                "item": item,
                "valor_informado": valor or "",
                "observacao_item": observacao or "",
                "avaliacao": evaluation,
                "is_out": evaluation["status"] == "out",
            }
        )
    return rows


def summarize_progress(item_rows: list[dict]) -> ProgressSummary:
    total = len(item_rows)
    preenchidos = sum(1 for row in item_rows if (row.get("valor_informado") or "").strip())
    percentual = int(round((preenchidos / total) * 100)) if total else 0
    return ProgressSummary(total=total, preenchidos=preenchidos, percentual=percentual)


def find_existing_lancamento_for_context(
    session: Session,
    data_referencia: date,
    setor: str,
    turno: str,
    exclude_id: int | None = None,
) -> EDLancamento | None:
    statement = (
        select(EDLancamento)
        .where(EDLancamento.data_referencia == data_referencia)
        .where(EDLancamento.setor == setor)
        .where(EDLancamento.turno == turno)
        .order_by(EDLancamento.updated_at.desc(), EDLancamento.id.desc())
    )
    if exclude_id is not None:
        statement = statement.where(EDLancamento.id != exclude_id)
    return session.scalars(statement).first()


def build_existing_context_status(lancamento: EDLancamento | None) -> ExistingContextStatus | None:
    if lancamento is None:
        return None
    if lancamento.status == STATUS_RASCUNHO:
        return ExistingContextStatus(
            lancamento_id=lancamento.id,
            status=lancamento.status,
            label=STATUS_BADGES[lancamento.status],
            message="Já existe lançamento para este contexto.",
            action_label="Continuar edição",
            action_url=f"/ed/lancamentos/{lancamento.id}/editar",
        )
    return ExistingContextStatus(
        lancamento_id=lancamento.id,
        status=lancamento.status,
        label=STATUS_BADGES[lancamento.status],
        message="Já existe lançamento para este contexto.",
        action_label="Visualizar",
        action_url=f"/ed/lancamentos/{lancamento.id}",
    )


def get_lancamento(session: Session, lancamento_id: int) -> EDLancamento | None:
    statement = (
        select(EDLancamento)
        .options(
            joinedload(EDLancamento.itens).joinedload(EDLancamentoItem.operational_module_item),
            joinedload(EDLancamento.itens).joinedload(EDLancamentoItem.item_ed),
        )
        .where(EDLancamento.id == lancamento_id)
    )
    return session.scalars(statement).unique().first()


def get_existing_row_map(lancamento: EDLancamento) -> dict[int, dict]:
    row_map: dict[int, dict] = {}
    current_session = object_session(lancamento)
    legacy_item_map = (
        operational_module_item_service.get_item_map_by_legacy_ed_id(current_session)
        if current_session is not None
        else {}
    )
    for row in lancamento.itens:
        item_id = row.operational_module_item_id
        if item_id is None and row.item_ed_id is not None:
            mapped = legacy_item_map.get(row.item_ed_id)
            item_id = mapped.id if mapped else None
        if item_id is None:
            continue
        row_map[item_id] = {
            "valor_informado": row.valor_informado,
            "observacao_item": row.observacao_item,
            "fora_parametro": row.fora_parametro,
        }
    return row_map


def save_lancamento(
    session: Session,
    context: ParsedContext,
    item_ids: list[int],
    form_data,
    status: str,
    lancamento_id: int | None = None,
) -> EDLancamento:
    if not item_ids:
        raise EDValidationError("Nenhum item operacional foi carregado para salvar.")

    lancamento = None
    if lancamento_id is not None:
        lancamento = get_lancamento(session, lancamento_id)
        if lancamento is None:
            raise EDValidationError("Lançamento não encontrado.")
        if lancamento.status == STATUS_CONCLUIDO:
            raise EDValidationError("Lançamentos concluídos não podem ser alterados nesta etapa.")
    else:
        existing_for_context = find_existing_lancamento_for_context(
            session,
            context.data_referencia,
            context.setor,
            context.turno,
        )
        if existing_for_context is not None:
            raise EDValidationError("Já existe lançamento para este contexto. Use continuar edição ou visualizar.")

    if lancamento is None:
        lancamento = EDLancamento()
        session.add(lancamento)

    lancamento.data_referencia = context.data_referencia
    lancamento.tipo_dia = context.tipo_dia
    lancamento.setor = context.setor
    lancamento.turno = context.turno
    lancamento.responsavel_nome = context.responsavel_nome
    lancamento.status = status
    lancamento.observacoes_gerais = context.observacoes_gerais

    session.flush()

    item_lookup = {
        item.id: item
        for item in session.scalars(select(OperationalModuleItem).where(OperationalModuleItem.id.in_(item_ids))).all()
    }
    existing_rows = {
        row.operational_module_item_id: row
        for row in lancamento.itens
        if row.operational_module_item_id is not None
    }

    missing_required_items: list[str] = []
    for item_id in item_ids:
        item = item_lookup.get(item_id)
        if item is None:
            continue
        valor = (form_data.get(f"valor_{item_id}") or "").strip() or None
        observacao = (form_data.get(f"observacao_{item_id}") or "").strip() or None
        if status == STATUS_CONCLUIDO and not valor:
            label_controle = str(item.controle or "").strip() or f"Item {item_id}"
            missing_required_items.append(label_controle)
        evaluation = evaluate_parameter(item.parametro, valor)
        if evaluation["fora_parametro"] is True and not observacao:
            raise EDValidationError(
                f"Informe observação para itens fora do padrão, como '{item.controle}'."
            )
        row = existing_rows.get(item_id)
        if row is None:
            row = EDLancamentoItem(operational_module_item_id=item_id)
            lancamento.itens.append(row)
        row.operational_module_item_id = item_id
        row.valor_informado = valor
        row.observacao_item = observacao
        row.fora_parametro = evaluation["fora_parametro"]

    for existing_item_id, row in list(existing_rows.items()):
        if existing_item_id not in item_ids:
            lancamento.itens.remove(row)

    if status == STATUS_CONCLUIDO and missing_required_items:
        preview = ", ".join(missing_required_items[:3])
        suffix = "..." if len(missing_required_items) > 3 else ""
        raise EDValidationError(
            f"Preencha todos os itens antes de concluir. Pendentes: {preview}{suffix}"
        )

    session.commit()
    session.refresh(lancamento)
    return get_lancamento(session, lancamento.id) or lancamento


def list_history(
    session: Session,
    data_referencia: str | None = None,
    data_inicial: str | None = None,
    data_final: str | None = None,
    setor: str | None = None,
    turno: str | None = None,
    status: str | None = None,
) -> list[dict]:
    statement = (
        select(EDLancamento, func.count(EDLancamentoItem.id).label("quantidade_itens"))
        .outerjoin(EDLancamentoItem, EDLancamentoItem.lancamento_id == EDLancamento.id)
        .group_by(EDLancamento.id)
        .order_by(EDLancamento.data_referencia.desc(), EDLancamento.created_at.desc())
    )

    if data_referencia:
        statement = statement.where(EDLancamento.data_referencia == date.fromisoformat(data_referencia))
    if data_inicial:
        statement = statement.where(EDLancamento.data_referencia >= date.fromisoformat(data_inicial))
    if data_final:
        statement = statement.where(EDLancamento.data_referencia <= date.fromisoformat(data_final))
    if setor:
        statement = statement.where(EDLancamento.setor == setor)
    if turno:
        statement = statement.where(EDLancamento.turno == turno)
    if status:
        statement = statement.where(EDLancamento.status == status)

    rows = session.execute(statement).all()
    return [{"lancamento": lancamento, "quantidade_itens": quantidade_itens} for lancamento, quantidade_itens in rows]


def list_daily_launches(
    session: Session,
    target_date: date,
    setor: str | None = None,
    turno: str | None = None,
) -> list[EDLancamento]:
    statement = select(EDLancamento).where(EDLancamento.data_referencia == target_date)
    if setor:
        statement = statement.where(EDLancamento.setor == setor)
    if turno:
        statement = statement.where(EDLancamento.turno == turno)
    statement = statement.order_by(EDLancamento.setor, EDLancamento.turno, EDLancamento.updated_at.desc())
    return list(session.scalars(statement).all())


def count_pending_launches(
    session: Session,
    target_date: date,
    setor: str | None = None,
    turno: str | None = None,
) -> int:
    statement = select(func.count(EDLancamento.id)).where(EDLancamento.data_referencia == target_date)
    statement = statement.where(EDLancamento.status == STATUS_RASCUNHO)
    if setor:
        statement = statement.where(EDLancamento.setor == setor)
    if turno:
        statement = statement.where(EDLancamento.turno == turno)
    return int(session.scalar(statement) or 0)


def evaluate_parameter(parametro: str | None, valor_informado: str | None) -> dict:
    if not valor_informado or not valor_informado.strip():
        return {"status": "neutral", "fora_parametro": None, "label": EVALUATION_LABELS["neutral"]}
    if not parametro:
        return {"status": "neutral", "fora_parametro": None, "label": EVALUATION_LABELS["neutral"]}

    current_value = _extract_first_number(valor_informado)
    if current_value is None:
        return {"status": "neutral", "fora_parametro": None, "label": EVALUATION_LABELS["neutral"]}

    parameter_text = parametro.strip()
    result: bool | None = None

    if parameter_text.startswith("<="):
        target = _extract_first_number(parameter_text[2:])
        if target is not None:
            result = current_value <= target
    elif parameter_text.startswith("<"):
        target = _extract_first_number(parameter_text[1:])
        if target is not None:
            result = current_value < target
    elif parameter_text.startswith(">="):
        target = _extract_first_number(parameter_text[2:])
        if target is not None:
            result = current_value >= target
    elif parameter_text.startswith(">"):
        target = _extract_first_number(parameter_text[1:])
        if target is not None:
            result = current_value > target
    else:
        range_match = _range_pattern.search(parameter_text)
        if range_match:
            start = _to_decimal(range_match.group(1))
            end = _to_decimal(range_match.group(2))
            if start is not None and end is not None:
                lower = min(start, end)
                upper = max(start, end)
                result = lower <= current_value <= upper

    if result is None:
        return {"status": "neutral", "fora_parametro": None, "label": EVALUATION_LABELS["neutral"]}
    if result:
        return {"status": "ok", "fora_parametro": False, "label": EVALUATION_LABELS["ok"]}
    return {"status": "out", "fora_parametro": True, "label": EVALUATION_LABELS["out"]}


def _resolve_setor_tipo(setor: str) -> str:
    selected = _normalize_text(setor)
    if selected == "laboratorio":
        return "LABORATORIO"
    return "PTED"


def _matches_turno(item: OperationalModuleItem, turno: str) -> bool:
    item_turno = (item.turno_padrao or "").strip()
    selected = (turno or "").strip()
    if item_turno in _SHIFT_CODES:
        return item_turno == selected
    return True


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    normalized = normalized.replace("á", "a").replace("ã", "a").replace("â", "a")
    normalized = normalized.replace("é", "e").replace("ê", "e")
    normalized = normalized.replace("í", "i")
    normalized = normalized.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    normalized = normalized.replace("ú", "u")
    normalized = normalized.replace("ç", "c")
    return normalized


def _deduplicate_items(items: list[OperationalModuleItem]) -> list[OperationalModuleItem]:
    """Evita renderização duplicada quando existem registros idênticos legados no ED."""
    unique: list[OperationalModuleItem] = []
    seen: set[tuple[object, ...]] = set()
    for item in items:
        key = (
            str(item.module_code or "").strip().lower(),
            str(item.setor_tipo or "").strip().upper(),
            str(item.turno_padrao or "").strip(),
            str(item.operacao or "").strip().lower(),
            str(item.controle or "").strip().lower(),
            int(item.ordem or 0),
            str(item.frequencia_tipo or "").strip().lower(),
            item.dia_semana,
            item.dia_mes,
            str(item.tipo_validacao or "").strip().lower(),
            str(item.parametro_exibicao or item.parametro or "").strip().lower(),
            _normalize_decimal(item.limite_minimo),
            _normalize_decimal(item.limite_maximo),
            _normalize_decimal(item.valor_min),
            _normalize_decimal(item.valor_max),
            str(item.unidade or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _normalize_decimal(value) -> str:
    if value is None:
        return ""
    try:
        return format(Decimal(str(value)), "f")
    except (InvalidOperation, ValueError):
        return str(value)


def _extract_first_number(value: str) -> Decimal | None:
    match = _number_pattern.search(value)
    if not match:
        return None
    return _to_decimal(match.group(0))


def _to_decimal(value: str) -> Decimal | None:
    try:
        if "," in value and "." in value:
            return Decimal(value.replace(".", "").replace(",", "."))
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None
