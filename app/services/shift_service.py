"""
Serviço de Turno Operacional

Gerencia a entidade-mãe do fluxo operacional (OperationalShift).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    OperationalModuleRecord,
    OperationalShift,
    OperationalShiftModule,
    Responsavel,
    Turno,
    SHIFT_STATUS_NAO_INICIADO,
    SHIFT_STATUS_EM_ANDAMENTO,
    SHIFT_STATUS_PARCIAL,
    SHIFT_STATUS_CONCLUIDO,
    SHIFT_STATUS_LABELS,
    MODULE_PREVISAO_OBRIGATORIO,
    MODULE_PREVISAO_PREVISTO,
    MODULE_PREVISAO_NAO_PREVISTO,
    MODULE_PREVISAO_SEM_EXECUCAO,
    MODULE_PREVISAO_LABELS,
)
from app.services.operational_module_service import (
    MODULE_CONFIGS,
    MODULE_STATUS_NAO_INICIADO,
    MODULE_STATUS_EM_ANDAMENTO,
    MODULE_STATUS_PARCIAL,
    MODULE_STATUS_CONCLUIDO,
    STATUS_LABELS,
    SETOR_PTED,
    SETOR_LAB,
    SETOR_STATUS_NAO_INICIADO,
    FREQUENCY_LABELS,
    build_sector_view,
    operational_schema_available,
)


class ShiftValidationError(ValueError):
    """Erro de validação de turno operacional."""
    pass


@dataclass(frozen=True)
class ShiftContext:
    """Contexto do turno para templates."""
    shift: OperationalShift | None
    data_referencia: date
    turno: str | None
    has_active_shift: bool
    can_create_shift: bool


def _status_badge_label(status: str) -> str:
    if status == MODULE_STATUS_EM_ANDAMENTO:
        return "Andamento"
    return STATUS_LABELS.get(status, "Nao iniciado")


def _build_sector_progress(
    session: Session,
    config: Any,
    context: dict[str, Any],
    sector_record: Any | None,
    setor_tipo: str,
) -> dict[str, int]:
    metricas = sector_record.metricas if sector_record else {}
    total = int(metricas.get("total") or 0)
    preenchidos = int(metricas.get("preenchidos") or 0)
    if total <= 0:
        total = len(config.default_rows_builder(session, context, setor_tipo))
    return {"preenchidos": preenchidos, "total": total}


def _effective_module_status(status_geral: str, total_items: int) -> str:
    if total_items == 0:
        return MODULE_STATUS_CONCLUIDO
    return status_geral


def shift_schema_available(session: Session) -> bool:
    """Verifica se as tabelas de turno operacional existem."""
    from sqlalchemy import inspect
    bind = session.get_bind()
    inspector = inspect(bind)
    required_tables = ("operational_shifts", "operational_shift_modules")
    return all(inspector.has_table(t) for t in required_tables)


def get_active_shift(
    session: Session,
    data_referencia: date | None = None,
    turno: str | None = None,
) -> OperationalShift | None:
    """
    Busca turno operacional ativo para a data/turno especificados.
    Se não especificado, usa a data de hoje.
    """
    if not shift_schema_available(session):
        return None
    
    target_date = data_referencia or date.today()
    
    statement = (
        select(OperationalShift)
        .options(joinedload(OperationalShift.modulos))
        .where(OperationalShift.data_referencia == target_date)
    )
    
    if turno:
        statement = statement.where(OperationalShift.turno == turno)
    else:
        # Se não especificou turno, busca qualquer turno do dia
        statement = statement.order_by(OperationalShift.created_at.desc())
    
    return session.scalars(statement).unique().first()


def get_shift_by_id(session: Session, shift_id: int) -> OperationalShift | None:
    """Busca turno operacional por ID."""
    if not shift_schema_available(session):
        return None
    
    statement = (
        select(OperationalShift)
        .options(joinedload(OperationalShift.modulos))
        .where(OperationalShift.id == shift_id)
    )
    return session.scalars(statement).unique().first()


def get_module_record_for_shift(
    session: Session,
    shift_id: int,
    module_code: str,
) -> OperationalModuleRecord | None:
    """
    Busca o registro de um módulo dentro de um turno específico.
    
    Args:
        session: Sessão do banco
        shift_id: ID do turno operacional
        module_code: Código do módulo (ed, temperatura-forno-ed, etc.)
    
    Returns:
        O registro do módulo se existir, None caso contrário
    """
    if not shift_schema_available(session):
        return None
    
    statement = (
        select(OperationalModuleRecord)
        .where(OperationalModuleRecord.shift_id == shift_id)
        .where(OperationalModuleRecord.module_code == module_code)
    )
    return session.scalars(statement).first()


def create_shift(
    session: Session,
    data_referencia: date,
    turno: str | None = None,
    responsavel_pted: str | None = None,
    responsavel_lab: str | None = None,
    observacoes: str | None = None,
) -> OperationalShift:
    """
    Cria um novo turno operacional.
    
    Raises:
        ShiftValidationError: Se já existir turno para a data/turno.
    """
    if not shift_schema_available(session):
        raise ShiftValidationError(
            "As tabelas de turno operacional ainda não foram criadas. "
            "Execute 'alembic upgrade head'."
        )
    
    # Verifica se já existe turno para esta data/turno
    existing = get_active_shift(session, data_referencia, turno)
    if existing:
        raise ShiftValidationError(
            f"Já existe um turno operacional para {data_referencia.strftime('%d/%m/%Y')}"
            + (f" turno {turno}" if turno else "")
            + "."
        )
    
    now = datetime.now(UTC).replace(tzinfo=None)
    
    shift = OperationalShift(
        data_referencia=data_referencia,
        turno=turno,
        responsavel_pted=responsavel_pted,
        responsavel_lab=responsavel_lab,
        status_geral=SHIFT_STATUS_EM_ANDAMENTO,
        observacoes=observacoes,
        created_at=now,
        updated_at=now,
    )
    session.add(shift)
    session.flush()  # Para obter o ID
    
    # Cria registros de previsão para cada módulo
    for code, config in MODULE_CONFIGS.items():
        # Define previsão baseada na frequência
        if config.frequency == "daily":
            previsao = MODULE_PREVISAO_OBRIGATORIO
        elif config.frequency == "weekly":
            previsao = MODULE_PREVISAO_PREVISTO
        else:  # conditional
            previsao = MODULE_PREVISAO_PREVISTO
        
        shift_module = OperationalShiftModule(
            shift_id=shift.id,
            module_code=code,
            previsao=previsao,
        )
        session.add(shift_module)
    
    session.commit()
    return shift


def update_shift_status(session: Session, shift: OperationalShift) -> None:
    """
    Recalcula o status geral do turno com base nos módulos.
    """
    if not shift_schema_available(session):
        return
    
    # Busca todos os módulos do turno
    modules = list(
        session.scalars(
            select(OperationalModuleRecord)
            .where(OperationalModuleRecord.shift_id == shift.id)
        ).all()
    )
    
    # Busca previsões
    previsoes = {
        sm.module_code: sm.previsao
        for sm in session.scalars(
            select(OperationalShiftModule)
            .where(OperationalShiftModule.shift_id == shift.id)
        ).all()
    }
    
    # Conta status considerando apenas módulos previstos
    previstos = [
        code for code, prev in previsoes.items()
        if prev in (MODULE_PREVISAO_OBRIGATORIO, MODULE_PREVISAO_PREVISTO)
    ]
    
    modulos_dict = {m.module_code: m for m in modules}
    
    total_previstos = len(previstos)
    concluidos = 0
    em_andamento = 0
    
    for code in previstos:
        m = modulos_dict.get(code)
        if m:
            if m.status_geral == MODULE_STATUS_CONCLUIDO:
                concluidos += 1
            elif m.status_geral in (MODULE_STATUS_EM_ANDAMENTO, MODULE_STATUS_PARCIAL):
                em_andamento += 1
    
    # Determina status geral
    if total_previstos == 0:
        new_status = SHIFT_STATUS_NAO_INICIADO
    elif concluidos == total_previstos:
        new_status = SHIFT_STATUS_CONCLUIDO
    elif concluidos > 0:
        new_status = SHIFT_STATUS_PARCIAL
    elif em_andamento > 0:
        new_status = SHIFT_STATUS_EM_ANDAMENTO
    else:
        new_status = SHIFT_STATUS_EM_ANDAMENTO  # Turno iniciado mas sem módulos
    
    if shift.status_geral != new_status:
        shift.status_geral = new_status
        shift.updated_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()


def conclude_shift(session: Session, shift: OperationalShift) -> None:
    """Encerra manualmente o turno operacional."""
    if not shift_schema_available(session):
        return

    shift.status_geral = SHIFT_STATUS_CONCLUIDO
    shift.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.commit()


def update_module_previsao(
    session: Session,
    shift_id: int,
    module_code: str,
    previsao: str,
    observacao: str | None = None,
) -> None:
    """Atualiza a previsão de um módulo no turno."""
    if not shift_schema_available(session):
        return
    
    if previsao not in MODULE_PREVISAO_LABELS:
        raise ShiftValidationError(f"Previsão inválida: {previsao}")
    
    statement = (
        select(OperationalShiftModule)
        .where(OperationalShiftModule.shift_id == shift_id)
        .where(OperationalShiftModule.module_code == module_code)
    )
    shift_module = session.scalars(statement).first()
    
    if shift_module:
        shift_module.previsao = previsao
        shift_module.observacao = observacao
        shift_module.atualizado_em = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
    
    # Atualiza status do turno
    shift = get_shift_by_id(session, shift_id)
    if shift:
        update_shift_status(session, shift)


def build_shift_detail(
    session: Session,
    shift: OperationalShift,
) -> dict[str, Any]:
    """
    Monta detalhes completos de um turno para exibição.
    """
    if not shift_schema_available(session):
        return {}
    
    # Busca previsões
    previsoes = {
        sm.module_code: {
            "previsao": sm.previsao,
            "previsao_label": MODULE_PREVISAO_LABELS.get(sm.previsao, sm.previsao),
            "observacao": sm.observacao,
        }
        for sm in session.scalars(
            select(OperationalShiftModule)
            .where(OperationalShiftModule.shift_id == shift.id)
        ).all()
    }
    
    # Busca registros de módulos
    modulos_dict = {
        m.module_code: m
        for m in shift.modulos
    }

    shift_context = {"data_referencia": shift.data_referencia}
    if shift.turno:
        shift_context["turno"] = shift.turno
    shift_context["shift_id"] = shift.id
    
    # Monta lista de módulos
    modules_list = []
    for code, config in MODULE_CONFIGS.items():
        record = modulos_dict.get(code)
        prev_info = previsoes.get(code, {
            "previsao": MODULE_PREVISAO_PREVISTO,
            "previsao_label": MODULE_PREVISAO_LABELS[MODULE_PREVISAO_PREVISTO],
            "observacao": None,
        })
        
        # Status do módulo
        if record:
            status_geral = record.status_geral
            record_id = record.id
            
            # Status dos setores
            pted = next((s for s in record.setores if s.setor_tipo == SETOR_PTED), None)
            lab = next((s for s in record.setores if s.setor_tipo == SETOR_LAB), None)
            
            status_pted = pted.status_setor if pted else SETOR_STATUS_NAO_INICIADO
            status_lab = lab.status_setor if lab and SETOR_LAB in config.sector_sequence else SETOR_STATUS_NAO_INICIADO
            
            desvios = sum(
                int((s.metricas or {}).get("flag_count", 0))
                for s in record.setores
            )
        else:
            status_geral = MODULE_STATUS_NAO_INICIADO
            record_id = None
            status_pted = SETOR_STATUS_NAO_INICIADO
            status_lab = SETOR_STATUS_NAO_INICIADO
            desvios = 0

        pted_view = build_sector_view(session, config, shift_context, record, SETOR_PTED)
        pted_progress = {
            "preenchidos": int(pted_view["summary"]["preenchidos"]),
            "total": int(pted_view["summary"]["total"]),
        }
        lab_view = (
            build_sector_view(session, config, shift_context, record, SETOR_LAB)
            if SETOR_LAB in config.sector_sequence
            else None
        )
        lab_progress = {
            "preenchidos": int(lab_view["summary"]["preenchidos"]),
            "total": int(lab_view["summary"]["total"]),
        } if lab_view is not None else {"preenchidos": 0, "total": 0}
        total_items = pted_progress["total"] + lab_progress["total"]
        total_filled = pted_progress["preenchidos"] + lab_progress["preenchidos"]
        progress_percent = round((total_filled / total_items) * 100) if total_items > 0 else 100
        has_applicable_items = total_items > 0
        non_applicable_count = int(pted_view["summary"].get("not_applicable_count", 0)) + int(
            lab_view["summary"].get("not_applicable_count", 0) if lab_view else 0
        )
        on_demand_count = int(pted_view["summary"].get("on_demand_count", 0)) + int(
            lab_view["summary"].get("on_demand_count", 0) if lab_view else 0
        )
        effective_status_geral = _effective_module_status(status_geral, total_items)
        
        # Determina ação principal
        previsao = prev_info["previsao"]
        if previsao in (MODULE_PREVISAO_NAO_PREVISTO, MODULE_PREVISAO_SEM_EXECUCAO):
            action = "nao_previsto"
            action_label = "Não previsto"
        elif record_id is None and has_applicable_items:
            action = "iniciar"
            action_label = "Iniciar"
        elif effective_status_geral == MODULE_STATUS_CONCLUIDO:
            action = "visualizar"
            action_label = "Visualizar"
        else:
            action = "continuar"
            action_label = "Continuar"
        
        modules_list.append({
            "code": code,
            "slug": config.slug,
            "title": config.title,
            "description": config.description,
            "frequency": config.frequency,
            "frequency_label": FREQUENCY_LABELS.get(config.frequency, config.frequency),
            "supports_turno": config.supports_turno,
            "record_id": record_id,
            "status_geral": effective_status_geral,
            "status_badge_label": "Sem itens aplicáveis" if not has_applicable_items else _status_badge_label(effective_status_geral),
            "status_geral_label": "Sem itens aplicáveis hoje" if not has_applicable_items else STATUS_LABELS.get(effective_status_geral, "Não iniciado"),
            "status_badge_tone": MODULE_STATUS_CONCLUIDO if not has_applicable_items else effective_status_geral,
            "status_pted": status_pted,
            "status_pted_label": STATUS_LABELS.get(status_pted, "Não iniciado"),
            "status_lab": status_lab,
            "lab_enabled": SETOR_LAB in config.sector_sequence,
            "pted_progress": pted_progress,
            "lab_progress": lab_progress,
            "progress_percent": progress_percent,
            "has_alert": desvios > 0,
            "has_applicable_items": has_applicable_items,
            "non_applicable_count": non_applicable_count,
            "on_demand_count": on_demand_count,
            "status_lab_label": STATUS_LABELS.get(status_lab, "Não iniciado") if SETOR_LAB in config.sector_sequence else "-",
            "previsao": previsao,
            "previsao_label": prev_info["previsao_label"],
            "previsao_observacao": prev_info["observacao"],
            "action": action,
            "action_label": action_label,
            "desvios": desvios,
        })
    
    # Calcula métricas
    previstos = [m for m in modules_list if m["previsao"] in (MODULE_PREVISAO_OBRIGATORIO, MODULE_PREVISAO_PREVISTO)]
    total_previstos = len(previstos)
    concluidos = sum(1 for m in previstos if m["status_geral"] == MODULE_STATUS_CONCLUIDO)
    em_andamento = sum(1 for m in previstos if m["status_geral"] in (MODULE_STATUS_EM_ANDAMENTO, MODULE_STATUS_PARCIAL))
    nao_iniciados = total_previstos - concluidos - em_andamento
    nao_previstos = len(modules_list) - total_previstos
    pending_modules = [
        {
            "code": m["code"],
            "title": m["title"],
            "status_geral": m["status_geral"],
            "status_geral_label": m["status_geral_label"],
        }
        for m in previstos
        if m["status_geral"] != MODULE_STATUS_CONCLUIDO
    ]

    # If the shift was manually closed, preserve persisted status.
    # Otherwise derive the status from module progress for UI feedback.
    if shift.status_geral == SHIFT_STATUS_CONCLUIDO:
        display_shift_status = SHIFT_STATUS_CONCLUIDO
    else:
        display_shift_status = (
            SHIFT_STATUS_CONCLUIDO
            if total_previstos and concluidos == total_previstos
            else SHIFT_STATUS_PARCIAL if concluidos > 0
            else SHIFT_STATUS_EM_ANDAMENTO
        )

    return {
        "id": shift.id,
        "data": shift.data_referencia,
        "data_label": shift.data_referencia.strftime("%d/%m/%Y"),
        "turno": shift.turno,
        "responsavel_pted": shift.responsavel_pted,
        "responsavel_lab": shift.responsavel_lab,
        "status_geral": display_shift_status,
        "status_geral_label": SHIFT_STATUS_LABELS.get(display_shift_status, "Não iniciado"),
        "observacoes": shift.observacoes,
        "modules": modules_list,
        "total_modules": len(modules_list),
        "total_previstos": total_previstos,
        "concluidos": concluidos,
        "em_andamento": em_andamento,
        "nao_iniciados": nao_iniciados,
        "nao_previstos": nao_previstos,
        "pending_modules": pending_modules,
        "pending_count": len(pending_modules),
        "progresso": round((concluidos / total_previstos * 100) if total_previstos > 0 else 0),
    }


def list_shared_options(session: Session) -> dict[str, list[Any]]:
    """Lista opções compartilhadas para formulários."""
    from sqlalchemy import case
    
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
            .order_by(
                case((Turno.codigo.in_(["1", "2", "3"]), 0), else_=1),
                Turno.codigo,
                Turno.nome,
            )
        ).all()
    )
    
    return {
        "responsaveis": responsaveis,
        "turnos": turnos,
        "previsoes": [
            {"value": k, "label": v}
            for k, v in MODULE_PREVISAO_LABELS.items()
        ],
    }


def build_shifts_history(
    session: Session,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    turno: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Histórico de turnos operacionais com filtros.
    """
    if not shift_schema_available(session):
        return []
    
    statement = (
        select(OperationalShift)
        .options(joinedload(OperationalShift.modulos))
        .order_by(
            OperationalShift.data_referencia.desc(),
            OperationalShift.turno.desc(),
        )
        .limit(limit)
    )
    
    if data_inicio:
        statement = statement.where(OperationalShift.data_referencia >= data_inicio)
    if data_fim:
        statement = statement.where(OperationalShift.data_referencia <= data_fim)
    if turno:
        statement = statement.where(OperationalShift.turno == turno)
    if status:
        statement = statement.where(OperationalShift.status_geral == status)
    
    shifts = session.scalars(statement).unique().all()
    
    return [build_shift_detail(session, s) for s in shifts]
