from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Modelo,
    OperationalModuleItem,
    OperationalModuleRecord,
    OperationalModuleSectorRecord,
    OperationalModuleSectorEntry,
    OperationalShift,
)
from app.services.operational_module_service import (
    SETOR_LABELS,
    build_detail_context,
    get_master,
    get_module_config,
    list_all_modules,
    operational_schema_available,
)
from app.services.shift_service import build_shift_detail, get_shift_by_id, list_shared_options


@dataclass(frozen=True)
class ReportFilters:
    data_inicio: date | None = None
    data_fim: date | None = None
    modulo: str | None = None
    parametro: str | None = None
    setor: str | None = None
    prioridade: str | None = None
    agrupamento: str = "dia"
    # Secundários (mantidos por compatibilidade)
    turno: str | None = None
    responsavel: str | None = None
    status: str | None = None


def report_filter_options(session: Session) -> dict[str, Any]:
    shared = list_shared_options(session)
    modulos = list_all_modules()
    parametros_por_modulo: dict[str, list[dict[str, str]]] = {}
    parametros: list[dict[str, str]] = []
    seen_global: set[str] = set()
    seen_per_module: dict[str, set[str]] = {}

    for item in session.scalars(select(OperationalModuleItem).where(OperationalModuleItem.ativo.is_(True))).all():
        label = _checklist_item_label(item.operacao, item.controle)
        if not label:
            continue
        value = f"id:{item.id}"
        entry = {"value": value, "label": label}

        if value not in seen_global:
            parametros.append(entry)
            seen_global.add(value)

        module_key = item.module_code
        seen_per_module.setdefault(module_key, set())
        if value not in seen_per_module[module_key]:
            parametros_por_modulo.setdefault(module_key, []).append(entry)
            seen_per_module[module_key].add(value)

    parametros.sort(key=lambda row: row["label"])
    for key in list(parametros_por_modulo.keys()):
        parametros_por_modulo[key].sort(key=lambda row: row["label"])

    return {
        "turnos": shared.get("turnos", []),
        "responsaveis": shared.get("responsaveis", []),
        "modulos": modulos,
        "parametros": parametros,
        "parametros_por_modulo": parametros_por_modulo,
        "setores": [
            {"value": "", "label": "Todos"},
            {"value": "PTED", "label": SETOR_LABELS["PTED"]},
            {"value": "LABORATORIO", "label": SETOR_LABELS["LABORATORIO"]},
        ],
        "prioridades": [
            {"value": "", "label": "Todas"},
            {"value": "baixo", "label": "Baixo"},
            {"value": "medio", "label": "Médio"},
            {"value": "alto", "label": "Alto"},
        ],
        "agrupamentos": [
            {"value": "parametro", "label": "Por parâmetro"},
            {"value": "modulo", "label": "Por módulo"},
            {"value": "dia", "label": "Por dia"},
        ],
    }


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _checklist_item_label(operacao: Any, controle: Any) -> str:
    op = _normalize_text(operacao)
    ctrl = _normalize_text(controle)
    if op and ctrl:
        return f"{op} - {ctrl}"
    return ctrl or op


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y %H:%M")


def _parse_bool_flag(entry: OperationalModuleSectorEntry) -> bool:
    if entry.fora_padrao is not None:
        return bool(entry.fora_padrao)
    label = _normalize_text((entry.dados or {}).get("status_label")).lower()
    return "fora" in label


def _extract_expected_limits(
    item_lookup: dict[tuple[str, str], OperationalModuleItem],
    module_code: str,
    controle: str,
    dados: dict[str, Any],
) -> str:
    expected = _normalize_text(dados.get("expected") or dados.get("parametro"))
    if expected:
        return expected
    item = item_lookup.get((module_code, controle.lower()))
    if item is None:
        return "—"
    if item.valor_min is not None or item.valor_max is not None:
        return f"{item.valor_min if item.valor_min is not None else '—'} .. {item.valor_max if item.valor_max is not None else '—'}"
    if item.parametro:
        return str(item.parametro)
    return "—"


def _build_item_lookup(session: Session) -> dict[tuple[str, str], OperationalModuleItem]:
    items = session.scalars(select(OperationalModuleItem).where(OperationalModuleItem.ativo.is_(True))).all()
    lookup: dict[tuple[str, str], OperationalModuleItem] = {}
    for item in items:
        controle_key = _normalize_text(item.controle).lower()
        if controle_key:
            lookup[(item.module_code, controle_key)] = item
    return lookup


def _build_item_lookup_by_id(session: Session) -> dict[int, OperationalModuleItem]:
    items = session.scalars(select(OperationalModuleItem).where(OperationalModuleItem.ativo.is_(True))).all()
    return {int(item.id): item for item in items}


def _build_analytic_rows(session: Session, filters: ReportFilters) -> list[dict[str, Any]]:
    if not operational_schema_available(session):
        return []

    item_lookup = _build_item_lookup(session)
    item_lookup_by_id = _build_item_lookup_by_id(session)
    group_models_lookup: dict[str, str] = {}
    for model in session.scalars(select(Modelo).where(Modelo.ativo.is_(True)).order_by(Modelo.nome, Modelo.codigo)).all():
        group_code = _normalize_text(getattr(model, "grupo_retificador", "")).lower()
        if not group_code:
            continue
        label = f"{_normalize_text(model.nome)} ({_normalize_text(model.codigo)})" if _normalize_text(model.codigo) else _normalize_text(model.nome)
        if not label:
            continue
        group_models_lookup[group_code] = f"{group_models_lookup[group_code]}, {label}" if group_code in group_models_lookup else label
    statement = (
        select(OperationalModuleRecord)
        .options(joinedload(OperationalModuleRecord.setores).joinedload(OperationalModuleSectorRecord.respostas))
        .order_by(OperationalModuleRecord.data_referencia.desc(), OperationalModuleRecord.updated_at.desc())
    )
    if filters.data_inicio:
        statement = statement.where(OperationalModuleRecord.data_referencia >= filters.data_inicio)
    if filters.data_fim:
        statement = statement.where(OperationalModuleRecord.data_referencia <= filters.data_fim)
    if filters.modulo:
        statement = statement.where(OperationalModuleRecord.module_code == filters.modulo)
    if filters.turno:
        statement = statement.where(OperationalModuleRecord.turno == filters.turno)

    records = session.scalars(statement).unique().all()
    rows: list[dict[str, Any]] = []

    for record in records:
        config = get_module_config(record.module_code)
        for setor in record.setores:
            if filters.setor and setor.setor_tipo != filters.setor:
                continue
            responsavel = _normalize_text(setor.responsavel_nome) or "—"
            if filters.responsavel and filters.responsavel != responsavel:
                continue
            for entry in setor.respostas:
                dados = entry.dados or {}
                flag = _parse_bool_flag(entry)
                status_analitico = "Fora do padrão" if flag else "Dentro do padrão"
                if filters.status:
                    wanted = _normalize_text(filters.status).lower()
                    if wanted in {"fora", "fora_padrao", "fora do padrão"} and not flag:
                        continue
                    if wanted in {"dentro", "dentro_padrao", "dentro do padrão"} and flag:
                        continue

                operacao = _normalize_text(dados.get("operacao") or dados.get("label") or entry.referencia)
                controle = _normalize_text(
                    dados.get("descricao")
                    or dados.get("label")
                    or dados.get("anomalia")
                    or dados.get("local")
                    or entry.referencia
                )
                item = item_lookup.get((record.module_code, controle.lower()))
                item_id_value = dados.get("item_id")
                if item_id_value not in (None, ""):
                    try:
                        item = item_lookup_by_id.get(int(item_id_value)) or item
                    except (TypeError, ValueError):
                        pass

                first_column_key = config.columns[0].key if config.columns else "controle"
                parametro_nome = _normalize_text(dados.get(first_column_key))
                if not parametro_nome:
                    if first_column_key == "operacao":
                        parametro_nome = _normalize_text((item.operacao if item else None) or operacao)
                    elif first_column_key in {"label", "descricao", "cis", "cod_posicao", "local", "anomalia", "lado", "geracao", "quantidade"}:
                        parametro_nome = _normalize_text(controle)
                    else:
                        parametro_nome = _normalize_text((getattr(item, first_column_key, None) if item else None) or controle or dados.get("parametro"))

                checklist_item = _checklist_item_label(
                    (item.operacao if item else None) or operacao,
                    (item.controle if item else None) or controle,
                ) or "—"
                selected_param = _normalize_text(filters.parametro)
                if selected_param:
                    if selected_param.startswith("id:"):
                        expected_id = selected_param.split(":", 1)[1].strip()
                        current_id = str(item.id) if item else ""
                        if current_id != expected_id:
                            continue
                    else:
                        if checklist_item.lower() != selected_param.lower():
                            continue

                if not checklist_item:
                    continue
                prioridade = _normalize_text(dados.get("prioridade") or (item.prioridade if item else None) or "medio").lower()
                if prioridade not in {"baixo", "medio", "alto"}:
                    prioridade = "medio"
                if filters.prioridade and filters.prioridade != prioridade:
                    continue
                valor = _normalize_text(entry.valor_texto or dados.get("value") or dados.get("quantidade") or "—")
                expected_limits = _extract_expected_limits(item_lookup, record.module_code, controle, dados)
                observacao = _normalize_text(entry.observacao or dados.get("row_observation") or "—")
                turno_label = _normalize_text(record.turno) or "—"
                grupo_retificador = _normalize_text((record.context_data or {}).get("grupo_retificador")) or "—"
                group_models_text = group_models_lookup.get(grupo_retificador.lower(), "—") if grupo_retificador != "—" else "—"
                modelo_nome = _normalize_text(dados.get("modelo_nome"))
                modelo_codigo = _normalize_text(dados.get("modelo_codigo"))
                modelo_retificador = (
                    f"{modelo_nome} ({modelo_codigo})".strip()
                    if modelo_nome and modelo_codigo
                    else modelo_nome or modelo_codigo or _normalize_text((record.context_data or {}).get("modelo")) or "—"
                )
                data_label = record.data_referencia.strftime("%d/%m/%Y")
                updated_at_label = _format_datetime(entry.updated_at)
                setor_label = SETOR_LABELS.get(setor.setor_tipo, setor.setor_tipo)

                rows.append(
                    {
                        "id": f"{record.id}-{setor.id}-{entry.id}",
                        "sort_date": record.data_referencia,
                        "data_label": data_label,
                        "turno_label": turno_label,
                        "grupo_retificador": grupo_retificador,
                        "group_models_text": group_models_text,
                        "modelo_retificador": modelo_retificador,
                        "modulo_code": record.module_code,
                        "modulo_label": config.title,
                        "setor": setor.setor_tipo,
                        "setor_label": setor_label,
                        "operacao": operacao,
                        "controle": controle,
                        "item_id": item.id if item else None,
                        "checklist_item": checklist_item,
                        "parametro": parametro_nome or "—",
                        "valor": valor,
                        "status_label": status_analitico,
                        "desvio_label": "Sim" if flag else "Não",
                        "desvio": flag,
                        "responsavel": responsavel,
                        "observacao": observacao,
                        "expected_limits": expected_limits,
                        "updated_at_label": updated_at_label,
                        "history_key": f"{record.module_code}|{setor.setor_tipo}|{(item.id if item else _normalize_text(entry.referencia))}|{controle.lower()}",
                        "prioridade": prioridade,
                        "prioridade_label": {"baixo": "Baixo", "medio": "Médio", "alto": "Alto"}[prioridade],
                    }
                )

    rows.sort(key=lambda item: (item["sort_date"], item["id"]), reverse=True)

    # Monta histórico por item dentro do recorte filtrado.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["history_key"], []).append(row)
    for row in rows:
        history_rows = grouped.get(row["history_key"], [])[:12]
        row["detail_payload"] = {
            "data": row["data_label"],
            "turno": row["turno_label"],
            "modulo": row["modulo_label"],
            "grupo_retificador": row.get("grupo_retificador", "—"),
            "group_models_text": row.get("group_models_text", "—"),
            "modelo_retificador": row.get("modelo_retificador", "—"),
            "setor": row["setor_label"],
            "operacao": row["operacao"],
            "controle": row["controle"],
            "parametro": row["parametro"],
            "checklist_item": row["checklist_item"],
            "prioridade": row["prioridade_label"],
            "valor": row["valor"],
            "status": row["status_label"],
            "desvio": row["desvio_label"],
            "expected_limits": row["expected_limits"],
            "observacao": row["observacao"],
            "responsavel": row["responsavel"],
            "atualizado_em": row["updated_at_label"],
            "historico": [
                {
                    "data": h["data_label"],
                    "turno": h["turno_label"],
                    "valor": h["valor"],
                    "status": h["status_label"],
                    "desvio": h["desvio_label"],
                    "responsavel": h["responsavel"],
                }
                for h in history_rows
            ],
        }
    return rows


def _build_group_summary(rows: list[dict[str, Any]], agrupamento: str) -> list[dict[str, Any]]:
    bucket_key = "data_label"
    if agrupamento == "modulo":
        bucket_key = "modulo_label"
    elif agrupamento == "parametro":
        bucket_key = "checklist_item"

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = _normalize_text(row.get(bucket_key)) or "—"
        slot = grouped.setdefault(label, {"label": label, "total": 0, "fora": 0, "dentro": 0})
        slot["total"] += 1
        if row["desvio"]:
            slot["fora"] += 1
        else:
            slot["dentro"] += 1

    result = []
    for item in grouped.values():
        total = int(item["total"])
        fora = int(item["fora"])
        percentual = (fora * 100 / total) if total else 0
        result.append(
            {
                "label": item["label"],
                "total": total,
                "dentro": int(item["dentro"]),
                "fora": fora,
                "percentual_desvio": round(percentual, 1),
            }
        )
    result.sort(key=lambda item: item["total"], reverse=True)
    return result


def build_reports_snapshot(session: Session, filters: ReportFilters) -> dict[str, Any]:
    rows = _build_analytic_rows(session, filters)
    total = len(rows)
    fora = sum(1 for row in rows if row["desvio"])
    dentro = total - fora
    percentual_desvio = round((fora * 100 / total), 1) if total else 0.0

    metrics = [
        {"label": "Total de medições", "value": total},
        {"label": "Dentro do padrão", "value": dentro},
        {"label": "Fora do padrão", "value": fora},
        {"label": "Percentual de desvio", "value": f"{percentual_desvio:.1f}%"},
    ]

    grouped = _build_group_summary(rows, filters.agrupamento)
    desvios = [row for row in rows if row["desvio"]]
    grouped_modulo = _build_group_summary(rows, "modulo")
    return {
        "filters": filters,
        "rows": rows,
        "metrics": metrics,
        "grouped": grouped,
        "desvios": desvios,
        "grouped_modulo": grouped_modulo,
        "percentual_desvio": percentual_desvio,
    }


def build_shift_pdf_context(session: Session, shift_id: int) -> dict[str, Any] | None:
    shift = get_shift_by_id(session, shift_id)
    if not shift:
        return None
    return build_shift_detail(session, shift)


def build_shift_report_detail(session: Session, shift_id: int) -> dict[str, Any] | None:
    shift = get_shift_by_id(session, shift_id)
    if not shift:
        return None
    return build_shift_detail(session, shift)


def build_module_report_detail(session: Session, module_code: str, record_id: int, setor: str | None = None) -> dict[str, Any] | None:
    master = get_master(session, record_id)
    if master is None or master.module_code != module_code:
        return None
    config = get_module_config(module_code)
    detail = build_detail_context(session, config, master, report_setor=setor)
    detail["module_config"] = config
    detail["report_setor"] = setor
    return detail


