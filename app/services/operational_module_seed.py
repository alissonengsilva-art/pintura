from __future__ import annotations

from typing import Any

from app.services.ed_seed_data import build_seed_items


SECTOR_BOTH = "AMBOS"


def _item(
    module_code: str,
    ordem: int,
    controle: str,
    *,
    setor_tipo: str = SECTOR_BOTH,
    operacao: str | None = None,
    parametro: str | None = None,
    unidade: str | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    obrigatorio: bool = True,
    ativo: bool = True,
    frequencia: str | None = None,
    observacao: str | None = None,
) -> dict[str, Any]:
    return {
        "module_code": module_code,
        "setor_tipo": setor_tipo,
        "operacao": operacao,
        "controle": controle,
        "parametro": parametro,
        "unidade": unidade,
        "valor_min": valor_min,
        "valor_max": valor_max,
        "ordem": ordem,
        "obrigatorio": obrigatorio,
        "ativo": ativo,
        "frequencia": frequencia,
        "observacao": observacao,
    }


def _build_ed_items(*, include_extended_fields: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in build_seed_items():
        setor_padrao = str(row.get("setor_padrao") or "")
        if setor_padrao in {"PT/ED", "PTED"}:
            setor_tipo = "PTED"
        else:
            setor_tipo = "LABORATORIO"
        payload = _item(
            "ed",
            int(row["ordem_exibicao"]),
            str(row["descricao_controle"]),
            setor_tipo=setor_tipo,
            operacao=row.get("operacao_equipamento"),
            parametro=row.get("parametro"),
            frequencia=row.get("frequencia"),
            observacao=row.get("observacao"),
        )
        if include_extended_fields:
            payload.update(
                {
                    "norma": row.get("norma"),
                    "responsavel_padrao": row.get("responsavel_padrao"),
                    "turno_padrao": row.get("turno_padrao"),
                    "numero_coleta": row.get("numero_coleta"),
                    "legacy_item_ed_id": row.get("id"),
                }
            )
        items.append(payload)
    return items


def _build_non_ed_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    temperature_specs = [
        (1, 90.0, 30.0),
        (2, 90.0, 30.0),
        (3, 130.0, 30.0),
        (4, 170.0, 20.0),
        (5, 160.0, 20.0),
        (6, 180.0, 20.0),
        (7, 180.0, 20.0),
        (8, 180.0, 20.0),
        (9, 180.0, 20.0),
        (10, 180.0, 20.0),
        (11, 180.0, 20.0),
        (12, 180.0, 20.0),
    ]
    for ordem, nominal, tolerancia in temperature_specs:
        items.append(
            _item(
                "temperatura-forno-ed",
                ordem,
                f"Zona {ordem}",
                parametro=f"{int(nominal - tolerancia)} a {int(nominal + tolerancia)} °C",
                unidade="°C",
                valor_min=nominal - tolerancia,
                valor_max=nominal + tolerancia,
                frequencia="DIARIO",
            )
        )

    for ordem in range(1, 25):
        items.append(
            _item(
                "pressao-filtros-ed",
                ordem,
                f"Filtro {ordem}",
                parametro="0,1 ≤ 1,0 bar",
                unidade="bar",
                valor_min=0.1,
                valor_max=1.0,
                frequencia="DIARIO",
            )
        )

    for ordem in range(1, 30):
        items.append(
            _item(
                "tensao-retificadores-ed",
                ordem,
                f"Zona {ordem}",
                parametro="80V a 400V",
                unidade="V",
                valor_min=80.0,
                valor_max=400.0,
                frequencia="DIARIO",
            )
        )

    for ordem in range(1, 31):
        items.append(
            _item(
                "poder-penetracao",
                ordem,
                f"Ponto {ordem}",
                parametro="≥ 7,9",
                valor_min=7.9,
                frequencia="SEMANAL",
            )
        )

    for ordem in range(1, 39):
        items.append(
            _item(
                "espessura-ed",
                ordem,
                f"Ponto {ordem}",
                parametro="Faixa de atenção: 10 a 60 µm",
                unidade="µm",
                valor_min=10.0,
                valor_max=60.0,
                frequencia="DIARIO",
            )
        )

    for ordem, codigo in enumerate(["521", "226", "551", "598", "291"], start=1):
        items.append(
            _item(
                "rugosidade",
                ordem,
                f"Modelo {codigo}",
                operacao=codigo,
                parametro="≤ 14 µin ou ≤ 0.356 µm",
                unidade="µin",
                valor_max=14.0,
                frequencia="DIARIO",
            )
        )

    for ordem in range(1, 11):
        items.append(
            _item(
                "aspecto",
                ordem,
                f"Linha {ordem}",
                parametro="Registro de carroceria",
                frequencia="DIARIO",
            )
        )

    return items


def build_operational_module_seed_items() -> list[dict[str, Any]]:
    return _build_ed_items(include_extended_fields=False) + _build_non_ed_items()


def build_operational_module_seed_items_runtime() -> list[dict[str, Any]]:
    return _build_ed_items(include_extended_fields=True) + _build_non_ed_items()
