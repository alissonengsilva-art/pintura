from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    OperationalModuleItem,
    SIG_MODULE_CODES,
    SIG_SHIFT_STATUS_CONCLUIDO,
    SIG_SHIFT_STATUS_EM_ANDAMENTO,
    SIG_SHIFT_STATUS_NAO_INICIADO,
    SIG_SHIFT_STATUS_PARCIAL,
    SIG_STATUS_LABELS,
    SigilaturaEscorrimento,
    SigilaturaEscorrimentoImagem,
    SigilaturaEspessuraPVC,
    SigilaturaModulo,
    SigilaturaResposta,
    SigilaturaTemperaturaForno,
    SigilaturaTurno,
    Turno,
)
from app.services import module_parameter_validation, operational_module_item_service


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

SIGILATURA_BASE_BY_TURNO: dict[str, list[tuple[str, str, str, str, str]]] = {
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

SIGILATURA_TEMPERATURA_BASE: list[tuple[str, str]] = [
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


class SigilaturaValidationError(ValueError):
    pass


ESCORRIMENTO_MAX_IMAGES = 2
ESCORRIMENTO_ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _escorrimento_upload_root() -> Path:
    return settings.static_dir / "uploads" / "sigilatura" / "escorrimento"


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


def _escorrimento_images_table_available(session: Session) -> bool:
    return inspect(session.get_bind()).has_table("sigilatura_escorrimento_imagens")


def list_turno_options(session: Session) -> list[Turno]:
    return list(session.scalars(select(Turno).where(Turno.ativo.is_(True)).order_by(Turno.codigo, Turno.nome)).all())


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _text_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def _catalog_items(session: Session, module_code: str, *, turno: str | None = None) -> list[OperationalModuleItem]:
    items = operational_module_item_service.get_items_by_scope_module(
        session,
        escopo="sigilatura",
        modulo=module_code,
        aba="Manual",
    )
    if not items:
        items = operational_module_item_service.get_items_by_scope_module(
            session,
            escopo="sigilatura",
            modulo=module_code,
            aba=None,
        )
    if not turno:
        return items
    filtered = [item for item in items if not str(item.turno_padrao or "").strip() or str(item.turno_padrao).strip() == str(turno).strip()]
    return filtered or items


def _item_parameter(item: OperationalModuleItem) -> str:
    return module_parameter_validation.display_parameter(item)


def _sigilatura_base_items(turno: str, session: Session | None = None) -> list[dict[str, Any]]:
    if session is not None:
        catalog = _catalog_items(session, "sigilatura", turno=turno)
        rows = []
        for idx, item in enumerate(catalog, start=1):
            rows.append(
                {
                    "item_key": f"SIG-{item.id}",
                    "ordem": item.ordem or idx,
                    "operacao": str(item.operacao or "").strip(),
                    "controle": str(item.controle or "").strip(),
                    "norma": str(item.norma or "").strip(),
                    "parametro": _item_parameter(item),
                    "frequencia": str(item.frequencia or item.frequencia_tipo or "").strip() or "diario",
                    "turno_label": turno,
                    "item_id": item.id,
                }
            )
        return sorted(rows, key=lambda row: (int(row["ordem"]), str(row["item_key"])))

    source = SIGILATURA_BASE_BY_TURNO.get(turno, SIGILATURA_BASE_BY_TURNO["1"])
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


def _espessura_base_items(turno: str, session: Session | None = None) -> list[dict[str, Any]]:
    if session is not None:
        catalog = _catalog_items(session, "espessura-pvc", turno=turno)
        rows = []
        for idx, item in enumerate(catalog, start=1):
            item_key = f"ESP-{item.id}"
            rows.append(
                {
                    "item_key": item_key,
                    "ordem": item.ordem or idx,
                    "ponto": str(item.controle or "").strip(),
                    "linha": str(item.aba or "1").strip(),
                    "frequencia": str(item.frequencia or item.frequencia_tipo or "").strip() or "diario",
                    "turno_label": turno,
                    "modelo": str(item.operacao or "").strip() or "226",
                    "valor_referencia": _item_parameter(item),
                    "item_id": item.id,
                }
            )
        return sorted(rows, key=lambda row: (int(row["ordem"]), str(row["item_key"])))

    rows = []
    idx = 1
    for modelo in ("226", "291"):
        for linha in ("1", "2"):
            for ponto in range(1, 9):
                item_key = f"ESP-{modelo}-L{linha}-P{ponto}"
                rows.append(
                    {
                        "item_key": item_key,
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


def _temperatura_base_items(session: Session | None = None) -> list[dict[str, Any]]:
    if session is not None:
        catalog = _catalog_items(session, "temperatura-forno-sigilatura")
        rows = []
        for idx, item in enumerate(catalog, start=1):
            zona_label = str(item.controle or "").strip() or f"Zona {idx}"
            rows.append(
                {
                    "item_key": f"TEMP-{item.id}",
                    "ordem": item.ordem or idx,
                    "zona": zona_label,
                    "referencia": _item_parameter(item),
                    "item_id": item.id,
                }
            )
        return sorted(rows, key=lambda row: (int(row["ordem"]), str(row["item_key"])))

    rows = []
    for idx, (zona, referencia) in enumerate(SIGILATURA_TEMPERATURA_BASE, start=1):
        zona_label = f"Zona {zona}"
        rows.append({"item_key": f"TEMP-{idx:02d}", "ordem": idx, "zona": zona_label, "referencia": referencia})
    return rows


def _escorrimento_base_items(session: Session | None = None, turno: str | None = None) -> list[dict[str, Any]]:
    if session is not None:
        catalog = _catalog_items(session, "escorrimento", turno=turno)
        rows = []
        for idx, item in enumerate(catalog, start=1):
            rows.append(
                {
                    "item_key": f"ESC-ITEM-{item.id}",
                    "ordem": item.ordem or idx,
                    "item": str(item.controle or "").strip(),
                    "field_key": str(item.operacao or "").strip().lower().replace(" ", "_") or f"field_{idx}",
                    "item_id": item.id,
                }
            )
        return sorted(rows, key=lambda row: (int(row["ordem"]), str(row["item_key"])))

    controls = [
        ("numero_amostra", "N° AMOSTRA"),
        ("lote", "LOTE"),
        ("real_temp_amb_auto", "REAL TEMP. AMB. AUTOMÁTICA"),
        ("real_estufa_auto", "REAL ESTUFA AUTOMÁTICA"),
        ("real_temp_amb_manual", "REAL TEMP. AMB. MANUAL"),
        ("real_estufa_manual", "REAL ESTUFA MANUAL"),
        ("resultados_obtidos", "RESULTADOS OBTIDOS"),
        ("acao_corretiva", "AÇÃO CORRETIVA"),
    ]
    rows: list[dict[str, Any]] = []
    for ordem, (field_key, label) in enumerate(controls, start=1):
        rows.append(
            {
                "item_key": f"ESC-ITEM-{ordem:02d}",
                "ordem": ordem,
                "item": label,
                "field_key": field_key,
            }
        )
    return rows

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
        parts = rule.replace("°C", "").replace("MM", "").split("-")
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
    preenchidos = sum(
        1
        for row in rows
        if str(row.get("valor") or row.get("descricao") or row.get("valor_medido") or row.get("resultados_obtidos") or "").strip()
    )
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


def _find_turno_modulo(turno_obj: SigilaturaTurno, module_code: str) -> SigilaturaModulo:
    modulo = next((m for m in turno_obj.modulos if m.module_code == module_code), None)
    if modulo is None:
        raise SigilaturaValidationError("Modulo invalido para este turno.")
    return modulo


def list_escorrimento_images(session: Session, turno_obj: SigilaturaTurno) -> list[dict[str, Any]]:
    if not _escorrimento_images_table_available(session):
        return []
    modulo = _find_turno_modulo(turno_obj, "escorrimento")
    images = list(
        session.scalars(
            select(SigilaturaEscorrimentoImagem)
            .where(SigilaturaEscorrimentoImagem.modulo_id == modulo.id)
            .order_by(SigilaturaEscorrimentoImagem.id.asc())
        ).all()
    )
    result: list[dict[str, Any]] = []
    for image in images:
        image_path = str(image.file_path or "").replace("\\", "/")
        result.append(
            {
                "id": image.id,
                "url": f"/static/{image_path}",
                "file_name": image.file_name,
                "content_type": image.content_type or "",
            }
        )
    return result


def add_escorrimento_image(
    session: Session,
    turno_obj: SigilaturaTurno,
    *,
    file_bytes: bytes,
    content_type: str,
) -> dict[str, Any]:
    if not _escorrimento_images_table_available(session):
        raise SigilaturaValidationError("Estrutura de imagens nao instalada. Execute as migrations.")
    modulo = _find_turno_modulo(turno_obj, "escorrimento")
    content_type_norm = str(content_type or "").strip().lower()
    extension = ESCORRIMENTO_ALLOWED_IMAGE_TYPES.get(content_type_norm)
    if extension is None:
        raise SigilaturaValidationError("Formato de imagem invalido. Use JPG, PNG ou WEBP.")
    if not file_bytes:
        raise SigilaturaValidationError("Arquivo de imagem vazio.")

    existing_images = list(
        session.scalars(
            select(SigilaturaEscorrimentoImagem)
            .where(SigilaturaEscorrimentoImagem.modulo_id == modulo.id)
            .order_by(SigilaturaEscorrimentoImagem.id.asc())
        ).all()
    )
    if len(existing_images) >= ESCORRIMENTO_MAX_IMAGES:
        raise SigilaturaValidationError("Limite de 2 imagens atingido para o escorrimento.")

    target_dir = _escorrimento_upload_root() / str(turno_obj.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid4().hex}{extension}"
    target_file = target_dir / file_name
    relative_path = target_file.relative_to(settings.static_dir)
    target_file.write_bytes(file_bytes)

    now = _now()
    image = SigilaturaEscorrimentoImagem(
        turno_id=turno_obj.id,
        modulo_id=modulo.id,
        file_name=file_name,
        file_path=str(relative_path).replace("\\", "/"),
        content_type=content_type_norm,
        created_at=now,
        updated_at=now,
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    return {
        "id": image.id,
        "url": f"/static/{image.file_path}",
        "file_name": image.file_name,
        "content_type": image.content_type or "",
    }


def remove_escorrimento_image(session: Session, turno_obj: SigilaturaTurno, image_id: int) -> None:
    if not _escorrimento_images_table_available(session):
        raise SigilaturaValidationError("Estrutura de imagens nao instalada. Execute as migrations.")
    modulo = _find_turno_modulo(turno_obj, "escorrimento")
    image = session.scalar(
        select(SigilaturaEscorrimentoImagem)
        .where(SigilaturaEscorrimentoImagem.id == image_id)
        .where(SigilaturaEscorrimentoImagem.modulo_id == modulo.id)
    )
    if image is None:
        raise SigilaturaValidationError("Imagem nao encontrada para este turno.")

    file_path = settings.static_dir / str(image.file_path or "")
    session.delete(image)
    session.commit()
    if file_path.exists() and file_path.is_file():
        file_path.unlink()


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
        defaults = _sigilatura_base_items(turno_obj.turno, session)
        existing_by_item_id = {int(r.operational_module_item_id): r for r in modulo.respostas if r.operational_module_item_id is not None}
        existing_by_key = {r.item_key: r for r in modulo.respostas}
        rows = []
        for base in defaults:
            item = existing_by_item_id.get(int(base["item_id"])) if base.get("item_id") is not None else None
            if item is None:
                item = existing_by_key.get(base["item_key"])
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
        defaults = _espessura_base_items(turno_obj.turno, session)
        existing_rows = list(
            session.scalars(
                select(SigilaturaEspessuraPVC)
                .where(SigilaturaEspessuraPVC.modulo_id == modulo.id)
                .order_by(SigilaturaEspessuraPVC.id.asc())
            ).all()
        )
        existing_by_item_id = {
            int(row.operational_module_item_id): row
            for row in existing_rows
            if row.operational_module_item_id is not None
        }
        existing_by_key = {
            f"ESP-{(row.modelo or '').strip()}-L{row.linha}-P{row.ponto.replace('Ponto ', '')}": row for row in existing_rows
        }
        rows = []
        for index, base in enumerate(defaults):
            item = existing_by_item_id.get(int(base["item_id"])) if base.get("item_id") is not None else None
            if item is None:
                item = existing_rows[index] if index < len(existing_rows) else None
            if item is None:
                item = existing_by_key.get(base["item_key"])
            measured = item.valor_medido if item else ""
            status, desvio = _evaluate_param_rule(base["valor_referencia"], measured)
            rows.append(
                {
                    **base,
                    "modelo": item.modelo if item and item.modelo is not None else base["modelo"],
                    "valor_medido": measured,
                    "observacao": item.observacao if item else "",
                    "status": item.status if item else status,
                    "desvio": "SIM" if (item and item.status == "FORA") else desvio,
                }
            )
        return rows

    if module_code == "temperatura-forno-sigilatura":
        defaults = _temperatura_base_items(session)
        existing_rows = list(
            session.scalars(select(SigilaturaTemperaturaForno).where(SigilaturaTemperaturaForno.modulo_id == modulo.id)).all()
        )
        existing_by_item_id = {
            int(row.operational_module_item_id): row
            for row in existing_rows
            if row.operational_module_item_id is not None
        }
        existing = {row.zona: row for row in existing_rows}
        rows = []
        for base in defaults:
            item = existing_by_item_id.get(int(base["item_id"])) if base.get("item_id") is not None else None
            if item is None:
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

    defaults = _escorrimento_base_items(session, turno_obj.turno)
    existing = session.scalars(
        select(SigilaturaEscorrimento)
        .where(SigilaturaEscorrimento.modulo_id == modulo.id)
        .order_by(SigilaturaEscorrimento.id.asc())
    ).first()
    rows = []
    for base in defaults:
        field_key = str(base["field_key"])
        value = str(getattr(existing, field_key) or "").strip() if existing else ""
        status = "DENTRO" if value else "NAO_AVALIADO"
        rows.append(
            {
                **base,
                "descricao": value,
                "status": status,
                "desvio": "NAO",
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
            {"key": "operacao", "label": "operação / Equipamento", "kind": "text"},
            {"key": "controle", "label": "Descrição do controle", "kind": "text"},
            {"key": "parametro", "label": "Parâmetro", "kind": "text"},
            {"key": "turno_label", "label": "Turno", "kind": "text"},
            {"key": "valor", "label": "Valor", "kind": "input", "name_prefix": "value"},
            {"key": "observacao", "label": "Observação", "kind": "input", "name_prefix": "obs"},
            {"key": "status", "label": "Status", "kind": "status"},
        ]
    elif module_code == "espessura-pvc":
        columns = [
            {"key": "ponto", "label": "Espessura PVC / Ponto", "kind": "text"},
            {"key": "linha", "label": "Linha", "kind": "text"},
            {"key": "modelo", "label": "Modelo", "kind": "input", "name_prefix": "model"},
            {"key": "valor_referencia", "label": "Valor referência", "kind": "text"},
            {"key": "valor_medido", "label": "Valor medido", "kind": "input", "name_prefix": "value"},
            {"key": "observacao", "label": "Observação", "kind": "input", "name_prefix": "obs"},
            {"key": "status", "label": "Status", "kind": "status"},
        ]
    elif module_code == "temperatura-forno-sigilatura":
        columns = [
            {"key": "zona", "label": "Zona", "kind": "text"},
            {"key": "referencia", "label": "Referência", "kind": "text"},
            {"key": "valor_medido", "label": "Valor medido", "kind": "input", "name_prefix": "value"},
            {"key": "observacoes", "label": "Observações", "kind": "input", "name_prefix": "obs"},
            {"key": "status", "label": "Status", "kind": "status"},
        ]
    else:
        columns = [
            {"key": "item", "label": "ITEM", "kind": "text"},
            {"key": "descricao", "label": "DESCRIÇÃO", "kind": "input", "name_prefix": "value"},
        ]
    escorrimento_images = list_escorrimento_images(session, turno_obj) if module_code == "escorrimento" else []
    return {
        "summary": module_summary,
        "rows": rows,
        "columns": columns,
        "escorrimento_images": escorrimento_images,
        "escorrimento_max_images": ESCORRIMENTO_MAX_IMAGES if module_code == "escorrimento" else 0,
    }

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
        defaults = _sigilatura_base_items(turno_obj.turno, session)
        session.query(SigilaturaResposta).filter(SigilaturaResposta.modulo_id == modulo.id).delete()
        for base in defaults:
            value = str(form_data.get(f"value_{base['item_key']}", "")).strip()
            obs = str(form_data.get(f"obs_{base['item_key']}", "")).strip()
            status, desvio = _evaluate_param_rule(base["parametro"], value)
            session.add(
                SigilaturaResposta(
                    turno_id=turno_obj.id,
                    modulo_id=modulo.id,
                    operational_module_item_id=base.get("item_id"),
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
        defaults = _espessura_base_items(turno_obj.turno, session)
        session.query(SigilaturaEspessuraPVC).filter(SigilaturaEspessuraPVC.modulo_id == modulo.id).delete()
        for base in defaults:
            modelo = str(form_data.get(f"model_{base['item_key']}", base["modelo"]) or "").strip()
            measured = str(form_data.get(f"value_{base['item_key']}", "")).strip()
            obs = str(form_data.get(f"obs_{base['item_key']}", "")).strip()
            status, _ = _evaluate_param_rule(base["valor_referencia"], measured)
            session.add(
                SigilaturaEspessuraPVC(
                    turno_id=turno_obj.id,
                    modulo_id=modulo.id,
                    operational_module_item_id=base.get("item_id"),
                    ponto=base["ponto"],
                    linha=base["linha"],
                    frequencia=base["frequencia"],
                    turno_label=base["turno_label"],
                    modelo=modelo or None,
                    valor_referencia=base["valor_referencia"],
                    valor_medido=measured or None,
                    observacao=obs or None,
                    status=status,
                    created_at=now,
                    updated_at=now,
                )
            )
    elif module_code == "temperatura-forno-sigilatura":
        defaults = _temperatura_base_items(session)
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
                    operational_module_item_id=base.get("item_id"),
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
        defaults = _escorrimento_base_items(session, turno_obj.turno)
        session.query(SigilaturaEscorrimento).filter(SigilaturaEscorrimento.modulo_id == modulo.id).delete()
        payload = {
            "numero_amostra": "",
            "lote": "",
            "real_temp_amb_auto": "",
            "real_estufa_auto": "",
            "real_temp_amb_manual": "",
            "real_estufa_manual": "",
            "resultados_obtidos": "",
            "acao_corretiva": "",
        }
        for base in defaults:
            key = str(base["item_key"])
            field_key = str(base["field_key"])
            payload[field_key] = str(form_data.get(f"value_{key}", "")).strip()

        has_value = any(str(payload.get(field) or "").strip() for field in payload)
        status = "DENTRO" if has_value else "NAO_AVALIADO"
        session.add(
            SigilaturaEscorrimento(
                turno_id=turno_obj.id,
                modulo_id=modulo.id,
                operational_module_item_id=(defaults[0].get("item_id") if defaults else None),
                semana=None,
                responsavel=None,
                numero_amostra=payload["numero_amostra"] or None,
                lote=payload["lote"] or None,
                real_temp_amb_auto=payload["real_temp_amb_auto"] or None,
                real_estufa_auto=payload["real_estufa_auto"] or None,
                real_temp_amb_manual=payload["real_temp_amb_manual"] or None,
                real_estufa_manual=payload["real_estufa_manual"] or None,
                resultados_obtidos=payload["resultados_obtidos"] or None,
                acao_corretiva=payload["acao_corretiva"] or None,
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


def build_admin_parameter_rows(session: Session, module_code: str) -> list[dict[str, Any]]:
    rows = operational_module_item_service.get_items_by_scope_module(
        session,
        escopo="sigilatura",
        modulo=module_code,
        aba=None,
    )
    result: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        result.append(
            {
                "key": f"SIGCFG-{item.id}",
                "ordem": item.ordem or index,
                "operacao": item.operacao or "",
                "controle": item.controle or "",
                "parametro": _item_parameter(item),
            }
        )
    return result

def save_admin_parameter_overrides(session: Session, module_code: str, updates: list[dict[str, str]]) -> None:
    if module_code not in {"sigilatura", "espessura-pvc", "temperatura-forno-sigilatura", "escorrimento"}:
        return

    existing = list(
        session.scalars(
            select(OperationalModuleItem)
            .where(OperationalModuleItem.escopo == "sigilatura")
            .where(OperationalModuleItem.modulo == module_code)
            .order_by(OperationalModuleItem.ordem, OperationalModuleItem.id)
        ).all()
    )
    by_key = {
        (_text_key(item.operacao), _text_key(item.controle)): item
        for item in existing
    }
    now = _now()

    for idx, row in enumerate(updates, start=1):
        operacao = str(row.get("operacao") or "").strip()
        controle = str(row.get("controle") or "").strip()
        parametro = str(row.get("parametro") or "").strip()
        if not operacao or not controle:
            continue
        key = (_text_key(operacao), _text_key(controle))
        item = by_key.get(key)
        if item is None:
            item = OperationalModuleItem(
                escopo="sigilatura",
                modulo=module_code,
                aba="Manual",
                module_code=module_code,
                setor_tipo="AMBOS",
                operacao=operacao,
                controle=controle,
                parametro=parametro or None,
                parametro_exibicao=parametro or None,
                referencia_visual=parametro or None,
                tipo_validacao="texto",
                ordem=idx,
                obrigatorio=True,
                ativo=True,
                frequencia_tipo="diario",
                created_at=now,
                updated_at=now,
            )
            session.add(item)
            by_key[key] = item
            continue
        item.parametro = parametro or None
        item.parametro_exibicao = parametro or None
        item.referencia_visual = parametro or None
        item.ordem = idx
        item.ativo = True
        item.updated_at = now

    session.commit()

def conclude_turno(session: Session, turno_obj: SigilaturaTurno) -> None:
    detail = build_turno_detail(session, turno_obj)
    pending_modules = [
        module
        for module in detail.get("modules", [])
        if module.get("status") != SIG_SHIFT_STATUS_CONCLUIDO
    ]
    if pending_modules:
        pending_names = ", ".join(str(module.get("title") or module.get("code")) for module in pending_modules[:3])
        suffix = "..." if len(pending_modules) > 3 else ""
        raise SigilaturaValidationError(
            f"Nao e possivel finalizar o turno. Conclua todos os setores pendentes: {pending_names}{suffix}"
        )

    turno_obj.status_geral = SIG_SHIFT_STATUS_CONCLUIDO
    turno_obj.updated_at = _now()
    session.commit()
