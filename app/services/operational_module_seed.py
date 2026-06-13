from __future__ import annotations

from typing import Any

from app.services.cabine_pintura_seed import build_cabine_pintura_seed_items
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
    tipo_validacao: str | None = None,
    obrigatorio: bool = True,
    ativo: bool = True,
    frequencia: str | None = None,
    prioridade: str | None = None,
    observacao: str | None = None,
) -> dict[str, Any]:
    validation_type = tipo_validacao
    if validation_type is None:
        if valor_min is not None and valor_max is not None:
            validation_type = "range"
        elif valor_min is not None:
            validation_type = "min"
        elif valor_max is not None:
            validation_type = "max"
        else:
            validation_type = "nenhum"
    return {
        "module_code": module_code,
        "setor_tipo": setor_tipo,
        "operacao": operacao,
        "controle": controle,
        "parametro": parametro,
        "parametro_exibicao": parametro,
        "unidade": unidade,
        "valor_min": valor_min,
        "valor_max": valor_max,
        "limite_minimo": valor_min,
        "limite_maximo": valor_max,
        "tipo_validacao": validation_type,
        "ordem": ordem,
        "obrigatorio": obrigatorio,
        "ativo": ativo,
        "frequencia": frequencia,
        "prioridade": str(prioridade or "medio").strip().lower() or "medio",
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
                setor_tipo="LABORATORIO",
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

    central_tintas_specs = [
        ("VERNIZ 1 PPG", "TEMPERATURA", "<23°C"),
        ("VERNIZ 1 PPG", "VISCOSIDADE", "35 - 37"),
        ("VERNIZ 1 PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("VERNIZ 2 AXALTA", "TEMPERATURA", "<25°C"),
        ("VERNIZ 2 AXALTA", "VISCOSIDADE", "29 - 31"),
        ("VERNIZ 2 AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("B1 UNIVERSAL PPG", "TEMPERATURA", "20 - 28°C"),
        ("B1 UNIVERSAL PPG", "VISCOSIDADE", "80 - 100"),
        ("B1 UNIVERSAL PPG", "pH", "8,4 - 8,8"),
        ("B1 UNIVERSAL PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("B0 MEDIUM AXALTA", "TEMPERATURA", "22 - 28°C"),
        ("B0 MEDIUM AXALTA", "VISCOSIDADE", "110 - 140"),
        ("B0 MEDIUM AXALTA", "pH", "8,4 - 8,8"),
        ("B0 MEDIUM AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("BRANCO AMBIENTE AXALTA", "TEMPERATURA", "20 - 28°C"),
        ("BRANCO AMBIENTE AXALTA", "VISCOSIDADE", "110 - 190"),
        ("BRANCO AMBIENTE AXALTA", "pH", "8,0 - 9,0"),
        ("BRANCO AMBIENTE AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("PRETO SHADOW AXALTA", "TEMPERATURA", "20 - 28°C"),
        ("PRETO SHADOW AXALTA", "VISCOSIDADE", "110 - 140"),
        ("PRETO SHADOW AXALTA", "pH", "8,2 - 8,6"),
        ("PRETO SHADOW AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("PRETO SHADOW PPG", "TEMPERATURA", "20 - 28°C"),
        ("PRETO SHADOW PPG", "VISCOSIDADE", "85 - 95"),
        ("PRETO SHADOW PPG", "pH", "8,4 - 9,2"),
        ("PRETO SHADOW PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("VERMELHO COLORADO PPG", "TEMPERATURA", "20 - 28°C"),
        ("VERMELHO COLORADO PPG", "VISCOSIDADE", "85 - 95"),
        ("VERMELHO COLORADO PPG", "pH", "8,4 - 8,8"),
        ("VERMELHO COLORADO PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("PRETO CARBON PPG", "TEMPERATURA", "20 - 28°C"),
        ("PRETO CARBON PPG", "VISCOSIDADE", "60 - 80"),
        ("PRETO CARBON PPG", "pH", "8,4 - 8,8"),
        ("PRETO CARBON PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("BRANCO POLAR AXALTA", "TEMPERATURA", "20 - 28°C"),
        ("BRANCO POLAR AXALTA", "VISCOSIDADE", "80 - 90"),
        ("BRANCO POLAR AXALTA", "pH", "8,4 - 8,8"),
        ("BRANCO POLAR AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("BILLET SILVER PPG", "TEMPERATURA", "20 - 28°C"),
        ("BILLET SILVER PPG", "VISCOSIDADE", "80 - 100"),
        ("BILLET SILVER PPG", "pH", "8,4 - 8,9"),
        ("BILLET SILVER PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("JAZZ BLUE PPG", "TEMPERATURA", "20 - 28°C"),
        ("JAZZ BLUE PPG", "VISCOSIDADE", "80 - 100"),
        ("JAZZ BLUE PPG", "pH", "8,4 - 8,8"),
        ("JAZZ BLUE PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("GRANITE CRYSTAL PPG", "TEMPERATURA", "20 - 28°C"),
        ("GRANITE CRYSTAL PPG", "VISCOSIDADE", "80 - 100"),
        ("GRANITE CRYSTAL PPG", "pH", "8,4 - 8,8"),
        ("GRANITE CRYSTAL PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("STING GRAY AXALTA", "TEMPERATURA", "20 - 28°C"),
        ("STING GRAY AXALTA", "VISCOSIDADE", "80 - 100"),
        ("STING GRAY AXALTA", "pH", "8,4 - 8,8"),
        ("STING GRAY AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("SLASH GOLD PPG", "TEMPERATURA", "20 - 28°C"),
        ("SLASH GOLD PPG", "VISCOSIDADE", "80 - 100"),
        ("SLASH GOLD PPG", "pH", "8,4 - 8,8"),
        ("SLASH GOLD PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("MAXIMUM STEEL PPG", "TEMPERATURA", "20 - 28°C"),
        ("MAXIMUM STEEL PPG", "VISCOSIDADE", "80 - 100"),
        ("MAXIMUM STEEL PPG", "pH", "8,4 - 8,8"),
        ("MAXIMUM STEEL PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("PUNK ORANGE AXALTA", "TEMPERATURA", "20 - 28°C"),
        ("PUNK ORANGE AXALTA", "VISCOSIDADE", "80 - 100"),
        ("PUNK ORANGE AXALTA", "pH", "8,4 - 8,9"),
        ("PUNK ORANGE AXALTA", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("VERDE RECON PPG", "TEMPERATURA", "20 - 28°C"),
        ("VERDE RECON PPG", "VISCOSIDADE", "75 - 85"),
        ("VERDE RECON PPG", "pH", "8,4 - 8,8"),
        ("VERDE RECON PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
        ("MONOCOAT PPG", "TEMPERATURA", "<23°C"),
        ("MONOCOAT PPG", "VISCOSIDADE", "27 - 32"),
        ("MONOCOAT PPG", "DP FILTRO DE ENVIO", "0 - 3 bar"),
    ]
    for ordem, (operacao, controle, parametro) in enumerate(central_tintas_specs, start=1):
        payload = _item(
            "central-tintas",
            ordem,
            controle,
            operacao=operacao,
            parametro=parametro,
            frequencia="DIARIO",
            prioridade="medio",
        )
        payload.update(
            {
                "escopo": "central_tintas",
                "modulo": "central-tintas",
                "aba": "Ambos",
                "responsavel_padrao": "Central de Tintas",
                "turno_padrao": "TODOS",
            }
        )
        items.append(payload)

    return items


def build_operational_module_seed_items() -> list[dict[str, Any]]:
    return _build_ed_items(include_extended_fields=False) + _build_non_ed_items() + build_cabine_pintura_seed_items()


def build_operational_module_seed_items_runtime() -> list[dict[str, Any]]:
    return _build_ed_items(include_extended_fields=True) + _build_non_ed_items() + build_cabine_pintura_seed_items()
