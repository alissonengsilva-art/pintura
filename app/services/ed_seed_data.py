from __future__ import annotations

from typing import Any

DEFAULT_RESPONSAVEIS = [
    {"nome": "Laboratório", "descricao": "Equipe de laboratório responsável por análises recorrentes.", "ativo": True},
    {"nome": "Condutor PT/ED", "descricao": "Condutor do processo de pré-tratamento e ED.", "ativo": True},
    {"nome": "Fornecedor/Laboratório", "descricao": "Atuação compartilhada entre fornecedor e laboratório.", "ativo": True},
]

DEFAULT_SETORES = [
    {"nome": "Laboratório", "sigla": "LAB", "ativo": True},
    {"nome": "PT/ED", "sigla": "PTED", "ativo": True},
    {"nome": "Fornecedor", "sigla": "FORN", "ativo": True},
]

DEFAULT_TURNOS = [
    {"nome": "Turno 1", "codigo": "1", "ativo": True},
    {"nome": "Turno 2", "codigo": "2", "ativo": True},
    {"nome": "Turno 3", "codigo": "3", "ativo": True},
    {"nome": "Rotina diária", "codigo": "1XDIA", "ativo": True},
    {"nome": "Uma vez por turno", "codigo": "1XTURNO", "ativo": True},
    {"nome": "Duas vezes por turno", "codigo": "2XTURNO", "ativo": True},
    {"nome": "Uma vez por semana", "codigo": "1XSEMANA", "ativo": True},
    {"nome": "Duas vezes por semana", "codigo": "2XSEMANA", "ativo": True},
    {"nome": "Uma vez a cada duas semanas", "codigo": "1X2SEMANAS", "ativo": True},
    {"nome": "Uma vez por mês", "codigo": "1XMES", "ativo": True},
]

ED_SEED_ROWS: list[dict[str, Any]] = [
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "RESIDUO SECO (NVC)", "norma": "SGU JPM16", "parametro": "22 - 26 %", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "CINZAS", "norma": "SGU JPM08", "parametro": "1,9 - 3,4%", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "RELACAO P/B", "norma": "SGU JPM19", "parametro": "10,0 - 16,0", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "PH", "norma": "SGU JPM06", "parametro": "5,3 - 6,3", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "CONDUTIVIDADE", "norma": "SGU JPM09", "parametro": "1300 - 2400 mS", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TEMPERATURA DO BANHO", "norma": None, "parametro": "<35ºC", "frequencia": "2XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TEMPERATURA DO BANHO", "norma": None, "parametro": "<35ºC", "frequencia": "2XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1", "numero_coleta": 2},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TEMPERATURA DO BANHO", "norma": None, "parametro": "<35ºC", "frequencia": "2XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "2", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TEMPERATURA DO BANHO", "norma": None, "parametro": "<35ºC", "frequencia": "2XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "2", "numero_coleta": 2},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TEMPERATURA DO BANHO", "norma": None, "parametro": "<35ºC", "frequencia": "2XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "3", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TEMPERATURA DO BANHO", "norma": None, "parametro": "<35ºC", "frequencia": "2XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "3", "numero_coleta": 2},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TENSÃO DOS RETIFICADORES", "norma": None, "parametro": "80 - 400V", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TENSÃO DOS RETIFICADORES", "norma": None, "parametro": "80 - 400V", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "2", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "TENSÃO DOS RETIFICADORES", "norma": None, "parametro": "80 - 400V", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "3", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "PRESSÃO NOS FILTROS", "norma": None, "parametro": "DP<=1", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "PRESSÃO NOS FILTROS", "norma": None, "parametro": "DP<=1", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "2", "numero_coleta": 1},
    {"operacao_equipamento": "BANHO DE TINTA", "descricao_controle": "PRESSÃO NOS FILTROS", "norma": None, "parametro": "DP<=1", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "3", "numero_coleta": 1},
    {"operacao_equipamento": "ANOLITO", "descricao_controle": "pH", "norma": "SGU JPM06", "parametro": "1,5 - 3,5", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "ANOLITO", "descricao_controle": "CONDUTIVIDADE", "norma": "SGU JPM09", "parametro": "500 - 5000 mS", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "ANOLITO", "descricao_controle": "VAZÃO CELULAS DIÁLISE", "norma": "SGU JPM24", "parametro": "≥2,5 L/min (≥ 150 L/h)", "frequencia": "1X2SEMANAS", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1X2SEMANAS", "numero_coleta": 1},
    {"operacao_equipamento": "ANOLITO", "descricao_controle": "CONSUMO DE CORRENTE CELULAS DIALISE", "norma": None, "parametro": "<200 A", "frequencia": "1XMES", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1XMES", "numero_coleta": 1},
    {"operacao_equipamento": "UF1", "descricao_controle": "pH", "norma": "SGU JPM06", "parametro": "5,0 - 6,0", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF1", "descricao_controle": "CONDUTIVIDADE", "norma": "SGU JPM09", "parametro": "500 - 1200 mS", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF1", "descricao_controle": "RESIDUO SECO (NVC)", "norma": "SGU JPM16", "parametro": "<1,5%", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF2", "descricao_controle": "pH", "norma": "SGU JPM06", "parametro": "5,0 - 6,0", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF2", "descricao_controle": "CONDUTIVIDADE", "norma": "SGU JPM09", "parametro": "500 - 1200 mS", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF2", "descricao_controle": "RESIDUO SECO (NVC)", "norma": "SGU JPM16", "parametro": "<1,5%", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF3", "descricao_controle": "pH", "norma": "SGU JPM06", "parametro": "5,0 - 6,0", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF3", "descricao_controle": "CONDUTIVIDADE", "norma": "SGU JPM09", "parametro": "500 - 1200 mS", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF3", "descricao_controle": "RESIDUO SECO (NVC)", "norma": "SGU JPM16", "parametro": "<1,5%", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "UF1, 2 e 3", "descricao_controle": "VAZÃO", "norma": "SGU JPM24", "parametro": "≥ 400 x 0,8 l/h (≥ 3,2 m³/h)", "frequencia": "1XDIA", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "ÁGUA DEMI", "descricao_controle": "CONDUTIVIDADE", "norma": "SGU JPM09", "parametro": "≤10µS", "frequencia": "1XDIA", "responsavel_padrao": "Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "FORNO ED", "descricao_controle": "TEMPERATURA INTERNA", "norma": None, "parametro": "<220ºC", "frequencia": "2XSEMANA", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "2XSEMANA", "numero_coleta": 1},
    {"operacao_equipamento": "FORNO ED", "descricao_controle": "CURVA DE COZIMENTO (DATAPAQ)", "norma": None, "parametro": ">20min a 160ºC", "frequencia": "1XSEMANA", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1XSEMANA", "numero_coleta": 1},
    {"operacao_equipamento": "CARACTERISTICA FILME DE CATAFORESE", "descricao_controle": "RUGOSIDADE CAPO E PORTAS (PPG)", "norma": "3 CARROS POR MODELO (ALTERNANDO OS MODELOS)", "parametro": "<=14u inch", "frequencia": "1XDIA", "responsavel_padrao": "Fornecedor/Laboratório", "turno_padrao": "1XDIA", "numero_coleta": 1},
    {"operacao_equipamento": "CARACTERISTICA FILME DE CATAFORESE", "descricao_controle": "COLATURA E GOTA - APARENCIA EXTERNA", "norma": "3 CARROS POR MODELO (ALTERNANDO OS MODELOS)", "parametro": "Menor melhor", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1", "numero_coleta": 1},
    {"operacao_equipamento": "CARACTERISTICA FILME DE CATAFORESE", "descricao_controle": "COLATURA E GOTA - APARENCIA EXTERNA", "norma": "3 CARROS POR MODELO (ALTERNANDO OS MODELOS)", "parametro": "Menor melhor", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "2", "numero_coleta": 1},
    {"operacao_equipamento": "CARACTERISTICA FILME DE CATAFORESE", "descricao_controle": "COLATURA E GOTA - APARENCIA EXTERNA", "norma": "3 CARROS POR MODELO (ALTERNANDO OS MODELOS)", "parametro": "Menor melhor", "frequencia": "1XTURNO", "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "3", "numero_coleta": 1},
    {"operacao_equipamento": "CARACTERISTICA FILME DE CATAFORESE", "descricao_controle": "ESPESSURA", "norma": None, "parametro": None, "frequencia": None, "responsavel_padrao": "Condutor PT/ED", "turno_padrao": "1", "numero_coleta": 1},
]


def infer_setor_padrao(responsavel_padrao: str | None) -> str | None:
    if not responsavel_padrao:
        return None
    if responsavel_padrao == "Laboratório":
        return "Laboratório"
    if responsavel_padrao == "Condutor PT/ED":
        return "PT/ED"
    if responsavel_padrao == "Fornecedor/Laboratório":
        return "Fornecedor"
    return responsavel_padrao


def build_seed_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in enumerate(ED_SEED_ROWS, start=1):
        item = dict(row)
        item["setor_padrao"] = infer_setor_padrao(item.get("responsavel_padrao"))
        item["ativo"] = True
        item["ordem_exibicao"] = index
        item["observacao"] = None
        items.append(item)
    return items
