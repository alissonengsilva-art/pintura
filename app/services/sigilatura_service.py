from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    SIG_MODULE_CODES,
    SIG_SHIFT_STATUS_CONCLUIDO,
    SIG_SHIFT_STATUS_EM_ANDAMENTO,
    SIG_SHIFT_STATUS_NAO_INICIADO,
    SIG_SHIFT_STATUS_PARCIAL,
    SIG_STATUS_LABELS,
    SigilaturaEscorrimento,
    SigilaturaEspessuraPVC,
    SigilaturaModulo,
    SigilaturaResposta,
    SigilaturaTemperaturaForno,
    SigilaturaTurno,
    Turno,
)


MODULE_META = {
    "sigilatura": {
        "title": "Sigilatura",
        "description": "Checklist operacional de sigilatura por turno.",
    },
    "espessura-pvc": {
        "title": "Espessura PVC",
        "description": "Medições de espessura PVC por modelo, linha e ponto.",
    },
    "temperatura-forno-sigilatura": {
        "title": "Temperatura Forno Sigilatura",
        "description": "Leituras de zonas térmicas e validação por faixa.",
    },
    "escorrimento": {
        "title": "Escorrimento",
        "description": "Checklist operacional de escorrimento.",
    },
}


class SigilaturaValidationError(ValueError):
    pass


def sigilatura_schema_available(session: Session) -> bool:
    inspector = inspect(session.get_bind())
    required = (
        "sigilatura_turnos",
        "sigilatura_modulos",
        "sigilatura_respostas",
        "sigilatura_espessura_pvc",
        "sigilatura_temperatura_forno",
        "sigilatura_escorrimento",
    )
    return all(inspector.has_table(table) for table in required)


def list_turno_options(session: Session) -> list[Turno]:
    return list(session.scalars(select(Turno).where(Turno.ativo.is_(True)).order_by(Turno.codigo, Turno.nome)).all())


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _sigilatura_base_items(turno: str) -> list[dict[str, Any]]:
    by_turno = {
        "1": [
            ("APLICAÇÃO PVC", "ESPESSURA", "", ">220", "1XTURNO"),
            ("APLICAÇÃO PVC", "REGIÃO COBERTA", "", "OK", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA CARGO BOX", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA MANUAL SPRUZZO", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA LINHA MANUAL 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA UBS 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA PVC 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA UBS 2", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA PVC 2", "", "26 - 32", "1XTURNO"),
            ("FORNO SEALER", "TEMPERATURA INTERNA", "Automático", "<200", "2XSEMANA"),
        ],
        "2": [
            ("APLICAÇÃO PVC", "ESPESSURA", "", ">220", "1XTURNO"),
            ("APLICAÇÃO PVC", "REGIÃO COBERTA", "", "OK", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA CARGO BOX", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA MANUAL SPRUZZO", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA LINHA MANUAL 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA UBS 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA PVC 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA UBS 2", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA PVC 2", "", "26 - 32", "1XTURNO"),
            ("FORNO SEALER", "CURVA DE COZIMENTO", "", ">20", "1XSEMANA"),
        ],
        "3": [
            ("APLICAÇÃO PVC", "ESPESSURA", "", ">220", "1XTURNO"),
            ("APLICAÇÃO PVC", "REGIÃO COBERTA", "", "OK", "1XTURNO"),
            ("SIGILATURA", "ESCORRIMENTO", "", ">5", "1XSEMANA"),
            ("SIGILATURA", "TEMPERATURA CARGO BOX", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA MANUAL SPRUZZO", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA LINHA MANUAL 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA UBS 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA UBS 2", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA PVC 1", "", "26 - 32", "1XTURNO"),
            ("SIGILATURA", "TEMPERATURA PVC 2", "", "26 - 32", "1XTURNO"),
        ],
    }
    source = by_turno.get(turno, by_turno["1"])
    rows = []
    for idx, (operacao, controle, norma, parametro, frequencia) in enumerate(source, start=1):
        rows.append(
            {
                "item_key": f"SIG-{idx:02d}",
                "ordem": idx,
                "operacao": operacao,
                "controle": controle,
                "norma": norma,
                "parametro": parametro,
                "frequencia": frequencia,
                "turno_label": turno,
            }
        )
    return rows


def _espessura_base_items(turno: str) -> list[dict[str, Any]]:
    rows = []
    idx = 1
    for modelo in ("226", "291"):
        for linha in ("1", "2"):
            for ponto in range(1, 9):
                rows.append(
                    {
                        "item_key": f"ESP-{modelo}-L{linha}-P{ponto}",
                        "ordem": idx,
                        "ponto": f"Ponto {ponto}",
                        "linha": linha,
                        "frequencia": "1/TURNO",
                        "turno_label": turno,
                        "modelo": modelo,
                        "valor_referencia": ">220",
                    }
                )
                idx += 1
    return rows


def _temperatura_base_items() -> list[dict[str, Any]]:
    base = [
        ("1.2", "150 +- 20"),
        ("2.1", "155 +- 20"),
        ("2.2", "155 +- 20"),
        ("3.1", "160 +- 20"),
        ("3.2", "160 +- 20"),
        ("4.1", "160 +- 20"),
        ("4.2", "160 +- 20"),
        ("5.1", "150 +- 20"),
        ("5.2", "150 +- 20"),
        ("6.1", "155 +- 20"),
        ("6.2", "155 +- 20"),
        ("7.1", "100 +- 20"),
        ("7.2", "100 +- 20"),
        ("8.1", "45 +- 20"),
        ("8.2", "45 +- 20"),
    ]
    rows = []
    for idx, (zona, referencia) in enumerate(base, start=1):
        rows.append({"item_key": f"TEMP-{idx:02d}", "ordem": idx, "zona": f"Zona {zona}", "referencia": referencia})
    return rows


def _escorrimento_base_items() -> list[dict[str, Any]]:
    return [
        {"item_key": "ESC-01", "ordem": 1, "numero_amostra": "1"},
        {"item_key": "ESC-02", "ordem": 2, "numero_amostra": "2"},
        {"item_key": "ESC-03", "ordem": 3, "numero_amostra": "3"},
    ]


def _evaluate_param_rule(parametro: str | None, valor: str | None) -> tuple[str, str]:
    value = str(valor or "").strip()
    rule = str(parametro or "").strip().upper()
    if not value:
        return ("NAO_AVALIADO", "NAO")
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        number = None
    if rule == "OK":
        ok = value.upper() == "OK"
        return ("DENTRO", "NAO") if ok else ("FORA", "SIM")
    if rule.startswith(">") and number is not None:
        limit = float(rule.replace(">", "").strip().split(" ")[0])
        return ("DENTRO", "NAO") if number > limit else ("FORA", "SIM")
    if rule.startswith("<") and number is not None:
        limit = float(rule.replace("<", "").strip().split(" ")[0])
        return ("DENTRO", "NAO") if number < limit else ("FORA", "SIM")
    if "-" in rule and number is not None:
        parts = rule.replace("ºC", "").replace("MM", "").split("-")
        if len(parts) == 2:
            low = float(parts[0].strip())
            high = float(parts[1].strip())
            return ("DENTRO", "NAO") if low <= number <= high else ("FORA", "SIM")
    if "+-" in rule and number is not None:
        center, delta = [p.strip() for p in rule.replace(" ", "").split("+-", 1)]
        low = float(center)
        dev = float(delta)
        return ("DENTRO", "NAO") if (low - dev) <= number <= (low + dev) else ("FORA", "SIM")
    return ("DENTRO", "NAO")


def _module_progress_from_rows(rows: list[dict[str, Any]]) -> dict[str, int | str]:
    total = len(rows)
    preenchidos = sum(1 for row in rows if str(row.get("valor") or row.get("valor_medido") or row.get("resultados_obtidos") or "").strip())
    desvios = sum(
        1
        for row in rows
        if (row.get("desvio") == "SIM" or row.get("status") in {"FORA", "FORA_PADRAO", "FORA_DO_PADRAO"})
    )
    if preenchidos <= 0:
        status = SIG_SHIFT_STATUS_NAO_INICIADO
    elif preenchidos < total:
        status = SIG_SHIFT_STATUS_EM_ANDAMENTO
    else:
        status = SIG_SHIFT_STATUS_CONCLUIDO
    return {"total": total, "preenchidos": preenchidos, "desvios": desvios, "status": status}


def _ensure_modulos(session: Session, turno: SigilaturaTurno) -> None:
    existing = {m.module_code: m for m in turno.modulos}
    created = False
    for code in SIG_MODULE_CODES:
        if code in existing:
            continue
        session.add(SigilaturaModulo(turno_id=turno.id, module_code=code, total=0, preenchidos=0, desvios=0))
        created = True
    if created:
        session.flush()
        session.refresh(turno)


def create_turno(session: Session, data_referencia: date, turno: str, responsavel: str | None = None) -> SigilaturaTurno:
    if not sigilatura_schema_available(session):
        raise SigilaturaValidationError("Estrutura de Sigilatura não disponível. Execute as migrations.")
    exists = session.scalars(
        select(SigilaturaTurno).where(SigilaturaTurno.data_referencia == data_referencia).where(SigilaturaTurno.turno == turno)
    ).first()
    if exists:
        raise SigilaturaValidationError("Já existe turno de sigilatura para essa data/turno.")
    obj = SigilaturaTurno(
        data_referencia=data_referencia,
        turno=turno,
        responsavel=(responsavel or None),
        status_geral=SIG_SHIFT_STATUS_EM_ANDAMENTO,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(obj)
    session.flush()
    _ensure_modulos(session, obj)
    session.commit()
    session.refresh(obj)
    return obj


def get_turno_by_id(session: Session, turno_id: int) -> SigilaturaTurno | None:
    if not sigilatura_schema_available(session):
        return None
    return session.scalars(
        select(SigilaturaTurno)
        .options(joinedload(SigilaturaTurno.modulos).joinedload(SigilaturaModulo.respostas))
        .where(SigilaturaTurno.id == turno_id)
    ).unique().first()


def list_turnos(session: Session, limit: int = 100) -> list[SigilaturaTurno]:
    if not sigilatura_schema_available(session):
        return []
    return list(
        session.scalars(
            select(SigilaturaTurno)
            .options(joinedload(SigilaturaTurno.modulos).joinedload(SigilaturaModulo.respostas))
            .order_by(SigilaturaTurno.data_referencia.desc(), SigilaturaTurno.turno.desc())
            .limit(limit)
        ).unique().all()
    )


def _load_module_rows(session: Session, turno_obj: SigilaturaTurno, module_code: str) -> list[dict[str, Any]]:
    modulo = next((m for m in turno_obj.modulos if m.module_code == module_code), None)
    if modulo is None:
        return []

    if module_code == "sigilatura":
        defaults = _sigilatura_base_items(turno_obj.turno)
        existing = {r.item_key: r for r in modulo.respostas}
        rows = []
        for base in defaults:
            item = existing.get(base["item_key"])
            rows.append(
                {
                    **base,
                    "valor": item.valor if item else "",
                    "observacao": item.observacao if item else "",
                    "status": item.status if item else "NAO_AVALIADO",
                    "desvio": item.desvio if item else "NAO",
                }
            )
        return rows

    if module_code == "espessura-pvc":
        defaults = _espessura_base_items(turno_obj.turno)
        existing = {
            f"ESP-{row.modelo}-L{row.linha}-P{row.ponto.replace('Ponto ', '')}": row
            for row in session.scalars(select(SigilaturaEspessuraPVC).where(SigilaturaEspessuraPVC.modulo_id == modulo.id)).all()
        }
        rows = []
        for base in defaults:
            item = existing.get(base["item_key"])
            measured = item.valor_medido if item else ""
            status, desvio = _evaluate_param_rule(base["valor_referencia"], measured)
            rows.append({**base, "valor_medido": measured, "observacao": item.observacao if item else "", "status": item.status if item else status, "desvio": "SIM" if (item and item.status == "FORA") else desvio})
        return rows

    if module_code == "temperatura-forno-sigilatura":
        defaults = _temperatura_base_items()
        existing = {row.zona: row for row in session.scalars(select(SigilaturaTemperaturaForno).where(SigilaturaTemperaturaForno.modulo_id == modulo.id)).all()}
        rows = []
        for base in defaults:
            item = existing.get(base["zona"])
            measured = item.valor_medido if item else ""
            status, desvio = _evaluate_param_rule(base["referencia"], measured)
            rows.append(
                {
                    **base,
                    "semana": item.semana if item else "",
                    "responsavel": item.responsavel if item else (turno_obj.responsavel or ""),
                    "valor_medido": measured,
                    "observacoes": item.observacoes if item else "",
                    "status": item.status if item else status,
                    "desvio": "SIM" if (item and item.status == "FORA") else desvio,
                }
            )
        return rows

    defaults = _escorrimento_base_items()
    existing = {
        f"ESC-{(row.numero_amostra or '').zfill(2)}": row
        for row in session.scalars(select(SigilaturaEscorrimento).where(SigilaturaEscorrimento.modulo_id == modulo.id)).all()
    }
    rows = []
    for base in defaults:
        item = existing.get(base["item_key"])
        resultados = item.resultados_obtidos if item else ""
        status = "DENTRO" if str(resultados or "").strip() else "NAO_AVALIADO"
        rows.append(
            {
                **base,
                "data": turno_obj.data_referencia.strftime("%d/%m/%Y"),
                "semana": item.semana if item else "",
                "responsavel": item.responsavel if item else (turno_obj.responsavel or ""),
                "lote": item.lote if item else "",
                "real_temp_amb_auto": item.real_temp_amb_auto if item else "",
                "real_estufa_auto": item.real_estufa_auto if item else "",
                "real_temp_amb_manual": item.real_temp_amb_manual if item else "",
                "real_estufa_manual": item.real_estufa_manual if item else "",
                "resultados_obtidos": resultados,
                "acao_corretiva": item.acao_corretiva if item else "",
                "status": item.status if item else status,
                "desvio": "SIM" if (item and item.status == "FORA") else "NAO",
            }
        )
    return rows


def _module_percent(preenchidos: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round((preenchidos / total) * 100))


def build_turno_detail(session: Session, turno_obj: SigilaturaTurno) -> dict[str, Any]:
    _ensure_modulos(session, turno_obj)
    module_views = []
    total_items = 0
    total_filled = 0
    total_desvios = 0
    for code in SIG_MODULE_CODES:
        modulo = next((m for m in turno_obj.modulos if m.module_code == code), None)
        rows = _load_module_rows(session, turno_obj, code)
        progress = _module_progress_from_rows(rows)
        total = int(progress["total"])
        filled = int(progress["preenchidos"])
        desvios = int(progress["desvios"])
        status = str(progress["status"])
        if modulo:
            modulo.total = total
            modulo.preenchidos = filled
            modulo.desvios = desvios
            modulo.status = status
            modulo.updated_at = _now()
        total_items += total
        total_filled += filled
        total_desvios += desvios
        module_views.append(
            {
                "code": code,
                "title": MODULE_META[code]["title"],
                "description": MODULE_META[code]["description"],
                "status": status,
                "status_label": SIG_STATUS_LABELS.get(status, "Não iniciado"),
                "preenchidos": filled,
                "total": total,
                "percent": _module_percent(filled, total),
                "desvios": desvios,
            }
        )

    all_done = all(m["status"] == SIG_SHIFT_STATUS_CONCLUIDO for m in module_views) if module_views else False
    any_started = any(m["preenchidos"] > 0 for m in module_views)
    if all_done:
        shift_status = SIG_SHIFT_STATUS_CONCLUIDO
    elif any_started:
        shift_status = SIG_SHIFT_STATUS_PARCIAL
    else:
        shift_status = SIG_SHIFT_STATUS_EM_ANDAMENTO
    turno_obj.status_geral = shift_status
    turno_obj.updated_at = _now()
    session.commit()

    return {
        "id": turno_obj.id,
        "data": turno_obj.data_referencia,
        "data_label": turno_obj.data_referencia.strftime("%d/%m/%Y"),
        "turno": turno_obj.turno,
        "responsavel": turno_obj.responsavel or "-",
        "responsavel_pted": turno_obj.responsavel or "-",
        "responsavel_lab": turno_obj.responsavel or "-",
        "status_geral": shift_status,
        "status_geral_label": SIG_STATUS_LABELS.get(shift_status, "Em andamento"),
        "modules": module_views,
        "total_modules": len(module_views),
        "concluidos": sum(1 for m in module_views if m["status"] == SIG_SHIFT_STATUS_CONCLUIDO),
        "em_andamento": sum(1 for m in module_views if m["status"] in {SIG_SHIFT_STATUS_EM_ANDAMENTO, SIG_SHIFT_STATUS_PARCIAL}),
        "nao_iniciados": sum(1 for m in module_views if m["status"] == SIG_SHIFT_STATUS_NAO_INICIADO),
        "total_items": total_items,
        "total_filled": total_filled,
        "total_desvios": total_desvios,
        "progresso": _module_percent(total_filled, total_items) if total_items else 0,
    }


def list_turnos_history(session: Session, limit: int = 100) -> list[dict[str, Any]]:
    return [build_turno_detail(session, turno_obj) for turno_obj in list_turnos(session, limit=limit)]


def build_module_editor_state(session: Session, turno_obj: SigilaturaTurno, module_code: str) -> dict[str, Any]:
    if module_code not in SIG_MODULE_CODES:
        module_code = SIG_MODULE_CODES[0]
    detail = build_turno_detail(session, turno_obj)
    module_summary = next(m for m in detail["modules"] if m["code"] == module_code)
    rows = _load_module_rows(session, turno_obj, module_code)

    if module_code == "sigilatura":
        columns = [
            {"key": "operacao", "label": "Operação / Equipamento", "kind": "text"},
            {"key": "controle", "label": "Descrição do controle", "kind": "text"},
            {"key": "norma", "label": "Norma", "kind": "text"},
            {"key": "parametro", "label": "Parâmetro", "kind": "text"},
            {"key": "frequencia", "label": "Frequência", "kind": "text"},
            {"key": "turno_label", "label": "Turno", "kind": "text"},
            {"key": "valor", "label": "Valor", "kind": "input", "name_prefix": "value"},
            {"key": "observacao", "label": "Observação", "kind": "input", "name_prefix": "obs"},
            {"key": "status", "label": "Status", "kind": "status"},
        ]
    elif module_code == "espessura-pvc":
        columns = [
            {"key": "ponto", "label": "Espessura PVC / Ponto", "kind": "text"},
            {"key": "linha", "label": "Linha", "kind": "text"},
            {"key": "frequencia", "label": "Frequência", "kind": "text"},
            {"key": "turno_label", "label": "Turno", "kind": "text"},
            {"key": "modelo", "label": "Modelo", "kind": "text"},
            {"key": "valor_referencia", "label": "Valor referência", "kind": "text"},
            {"key": "valor_medido", "label": "Valor medido", "kind": "input", "name_prefix": "value"},
            {"key": "observacao", "label": "Observação", "kind": "input", "name_prefix": "obs"},
            {"key": "status", "label": "Status", "kind": "status"},
        ]
    elif module_code == "temperatura-forno-sigilatura":
        columns = [
            {"key": "semana", "label": "Semana", "kind": "input", "name_prefix": "week"},
            {"key": "responsavel", "label": "Responsável", "kind": "input", "name_prefix": "owner"},
            {"key": "zona", "label": "Zona", "kind": "text"},
            {"key": "referencia", "label": "Referência", "kind": "text"},
            {"key": "valor_medido", "label": "Valor medido", "kind": "input", "name_prefix": "value"},
            {"key": "observacoes", "label": "Observações", "kind": "input", "name_prefix": "obs"},
            {"key": "status", "label": "Status", "kind": "status"},
        ]
    else:
        columns = [
            {"key": "data", "label": "Data", "kind": "text"},
            {"key": "semana", "label": "Semana", "kind": "input", "name_prefix": "week"},
            {"key": "responsavel", "label": "Responsável", "kind": "input", "name_prefix": "owner"},
            {"key": "numero_amostra", "label": "Nº amostra", "kind": "text"},
            {"key": "lote", "label": "Lote", "kind": "input", "name_prefix": "batch"},
            {"key": "real_temp_amb_auto", "label": "Real temp. amb. automática", "kind": "input", "name_prefix": "taa"},
            {"key": "real_estufa_auto", "label": "Real estufa automática", "kind": "input", "name_prefix": "tea"},
            {"key": "real_temp_amb_manual", "label": "Real temp. amb. manual", "kind": "input", "name_prefix": "tam"},
            {"key": "real_estufa_manual", "label": "Real estufa manual", "kind": "input", "name_prefix": "tem"},
            {"key": "resultados_obtidos", "label": "Resultados obtidos", "kind": "input", "name_prefix": "result"},
            {"key": "acao_corretiva", "label": "Ação corretiva", "kind": "input", "name_prefix": "action"},
            {"key": "status", "label": "Status", "kind": "status"},
        ]
    return {"summary": module_summary, "rows": rows, "columns": columns}


def save_module(
    session: Session,
    turno_obj: SigilaturaTurno,
    module_code: str,
    form_data: dict[str, str],
    action: str = "salvar",
) -> None:
    modulo = next((m for m in turno_obj.modulos if m.module_code == module_code), None)
    if modulo is None:
        raise SigilaturaValidationError("Módulo inválido para este turno.")
    now = _now()

    if module_code == "sigilatura":
        defaults = _sigilatura_base_items(turno_obj.turno)
        session.query(SigilaturaResposta).filter(SigilaturaResposta.modulo_id == modulo.id).delete()
        for base in defaults:
            value = str(form_data.get(f"value_{base['item_key']}", "")).strip()
            obs = str(form_data.get(f"obs_{base['item_key']}", "")).strip()
            status, desvio = _evaluate_param_rule(base["parametro"], value)
            session.add(
                SigilaturaResposta(
                    turno_id=turno_obj.id,
                    modulo_id=modulo.id,
                    module_code=module_code,
                    item_key=base["item_key"],
                    ordem=base["ordem"],
                    operacao=base["operacao"],
                    controle=base["controle"],
                    norma=base["norma"],
                    parametro=base["parametro"],
                    frequencia=base["frequencia"],
                    turno_label=base["turno_label"],
                    valor=value or None,
                    observacao=obs or None,
                    status=status,
                    desvio=desvio,
                    created_at=now,
                    updated_at=now,
                )
            )
    elif module_code == "espessura-pvc":
        defaults = _espessura_base_items(turno_obj.turno)
        session.query(SigilaturaEspessuraPVC).filter(SigilaturaEspessuraPVC.modulo_id == modulo.id).delete()
        for base in defaults:
            measured = str(form_data.get(f"value_{base['item_key']}", "")).strip()
            obs = str(form_data.get(f"obs_{base['item_key']}", "")).strip()
            status, _ = _evaluate_param_rule(base["valor_referencia"], measured)
            session.add(
                SigilaturaEspessuraPVC(
                    turno_id=turno_obj.id,
                    modulo_id=modulo.id,
                    ponto=base["ponto"],
                    linha=base["linha"],
                    frequencia=base["frequencia"],
                    turno_label=base["turno_label"],
                    modelo=base["modelo"],
                    valor_referencia=base["valor_referencia"],
                    valor_medido=measured or None,
                    observacao=obs or None,
                    status=status,
                    created_at=now,
                    updated_at=now,
                )
            )
    elif module_code == "temperatura-forno-sigilatura":
        defaults = _temperatura_base_items()
        session.query(SigilaturaTemperaturaForno).filter(SigilaturaTemperaturaForno.modulo_id == modulo.id).delete()
        for base in defaults:
            measured = str(form_data.get(f"value_{base['item_key']}", "")).strip()
            week = str(form_data.get(f"week_{base['item_key']}", "")).strip()
            owner = str(form_data.get(f"owner_{base['item_key']}", "")).strip()
            obs = str(form_data.get(f"obs_{base['item_key']}", "")).strip()
            status, _ = _evaluate_param_rule(base["referencia"], measured)
            session.add(
                SigilaturaTemperaturaForno(
                    turno_id=turno_obj.id,
                    modulo_id=modulo.id,
                    semana=week or None,
                    responsavel=owner or None,
                    zona=base["zona"],
                    referencia=base["referencia"],
                    valor_medido=measured or None,
                    observacoes=obs or None,
                    status=status,
                    created_at=now,
                    updated_at=now,
                )
            )
    else:
        defaults = _escorrimento_base_items()
        session.query(SigilaturaEscorrimento).filter(SigilaturaEscorrimento.modulo_id == modulo.id).delete()
        for base in defaults:
            key = base["item_key"]
            week = str(form_data.get(f"week_{key}", "")).strip()
            owner = str(form_data.get(f"owner_{key}", "")).strip()
            lote = str(form_data.get(f"batch_{key}", "")).strip()
            taa = str(form_data.get(f"taa_{key}", "")).strip()
            tea = str(form_data.get(f"tea_{key}", "")).strip()
            tam = str(form_data.get(f"tam_{key}", "")).strip()
            tem = str(form_data.get(f"tem_{key}", "")).strip()
            result = str(form_data.get(f"result_{key}", "")).strip()
            corrective_action = str(form_data.get(f"action_{key}", "")).strip()
            status = "DENTRO" if result else "NAO_AVALIADO"
            session.add(
                SigilaturaEscorrimento(
                    turno_id=turno_obj.id,
                    modulo_id=modulo.id,
                    semana=week or None,
                    responsavel=owner or None,
                    numero_amostra=base["numero_amostra"],
                    lote=lote or None,
                    real_temp_amb_auto=taa or None,
                    real_estufa_auto=tea or None,
                    real_temp_amb_manual=tam or None,
                    real_estufa_manual=tem or None,
                    resultados_obtidos=result or None,
                    acao_corretiva=corrective_action or None,
                    status=status,
                    created_at=now,
                    updated_at=now,
                )
            )

    session.flush()
    detail = build_turno_detail(session, turno_obj)

    if action == "concluir":
        module = next((item for item in detail["modules"] if item["code"] == module_code), None)
        if not module:
            raise SigilaturaValidationError("Módulo inválido para este turno.")
        if module["status"] != SIG_SHIFT_STATUS_CONCLUIDO:
            raise SigilaturaValidationError("Preencha todos os itens aplicáveis para concluir setor.")


def conclude_turno(session: Session, turno_obj: SigilaturaTurno) -> None:
    turno_obj.status_geral = SIG_SHIFT_STATUS_CONCLUIDO
    turno_obj.updated_at = _now()
    session.commit()
