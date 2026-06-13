from __future__ import annotations

from typing import Any


CABINE_PINTURA_ABA_TOP_COAT = "TOP COAT"
CABINE_PINTURA_ABA_TEMPERATURA_FORNO = "TEMPERATURA FORNO"
CABINE_PINTURA_ABA_DATA_PAQ = "DATA PAQ"
CABINE_PINTURA_ABAS = (
    CABINE_PINTURA_ABA_TOP_COAT,
    CABINE_PINTURA_ABA_TEMPERATURA_FORNO,
    CABINE_PINTURA_ABA_DATA_PAQ,
)


def _row(
    aba: str,
    operacao: str,
    controle: str,
    *,
    norma: str | None = None,
    parametro: str | None = None,
    responsavel: str | None = "CONDUTOR CABINE",
    turno_padrao: str | None = None,
    frequencia: str | None = None,
) -> dict[str, Any]:
    return {
        "aba": aba,
        "operacao": _normalize_cell(operacao),
        "controle": _normalize_cell(controle),
        "norma": _normalize_cell(norma),
        "parametro": _normalize_cell(parametro),
        "parametro_exibicao": _normalize_cell(parametro),
        "responsavel_padrao": _normalize_cell(responsavel),
        "turno_padrao": _normalize_cell(turno_padrao),
        "frequencia": _normalize_cell(frequencia),
    }


def _normalize_cell(value: str | None) -> str | None:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    return text or None


def build_cabine_pintura_seed_items() -> list[dict[str, Any]]:
    rows = [
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "BALANCEAMENTO DA CABINE", norma="CICLO AM I023", parametro="<0,3m/s", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "BALANCEAMENTO DA CABINE", norma="CICLO AM I023", parametro="<0,3m/s", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "BALANCEAMENTO DA CABINE", norma="CICLO AM I023", parametro="<0,3m/s", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "VELOCIDADE ABATIMENTO DO AR", norma="CICLO AM I112", parametro="INTERNO=0,2 a 0,45m/s EXTERNO=0,4 a 0,65m/s", turno_padrao="2", frequencia="1XDIA"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "VELOCIDADE ABATIMENTO DO AR", norma="CICLO AM I112", parametro="Interno 0,4 a 0,65m/s - externo 0,2 a 0,45m/s", frequencia="1X2SEMANAS"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "ESPESSURA TINTA", frequencia="1X2SEMANAS"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "TEMPERATURA CABINE BC01", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "TEMPERATURA CABINE BC01", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "TEMPERATURA CABINE BC01", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "TEMPERATURA CABINE BC02", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "TEMPERATURA CABINE BC02", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "TEMPERATURA CABINE BC02", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "UMIDADE CABINE BC01", norma="CICLO AM I085", parametro="50 a 70%", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "UMIDADE CABINE BC01", norma="CICLO AM I085", parametro="50 a 70%", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "UMIDADE CABINE BC02", norma="CICLO AM I085", parametro="50 a 75%", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "UMIDADE CABINE BC02", norma="CICLO AM I085", parametro="50 a 70%", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "UMIDADE CABINE BC02", norma="CICLO AM I085", parametro="50 a 70%", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO TINTA", "UMIDADE CABINE BC03", norma="CICLO AM I085", parametro="50 a 70%", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APASSIVAMENTO FLASH OFF", "TEMPERATURA ZONA DE CONVECÇÃO", norma="CICLO I090", parametro="32 a 42ºC", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APASSIVAMENTO FLASH OFF", "TEMPERATURA ZONA DE CONVECÇÃO", norma="CICLO I090", parametro="32 a 42ºC", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APASSIVAMENTO FLASH OFF", "TEMPERATURA ZONA DE CONVECÇÃO", norma="CICLO I090", parametro="32 a 42ºC", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "BALANCEAMENTO DA CABINE", norma="CICLO AM I023", parametro="<0,3m/s", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "BALANCEAMENTO DA CABINE", norma="CICLO AM I023", parametro="<0,3m/s", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "BALANCEAMENTO DA CABINE", norma="CICLO AM I023", parametro="<0,3m/s", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "RELAÇÃO DE CATALIZADOR", norma="Automático", parametro="OK/KO", turno_padrao="1", responsavel="AUTOMÁTICO", frequencia="ALARME"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "RELAÇÃO DE CATALIZADOR", norma="CICLO AM I100", parametro="OK/KO", turno_padrao="1", frequencia="1XMES"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "ESPESSURA VERNIZ", parametro=">=35um", frequencia="1X2SEMANAS"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "TEMPERATURA CABINE CC03", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "TEMPERATURA CABINE CC03", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "TEMPERATURA CABINE CC03", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "TEMPERATURA CABINE CC04", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "TEMPERATURA CABINE CC04", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "TEMPERATURA CABINE CC04", norma="CICLO AM I085", parametro="20 a 28ºC", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "UMIDADE CABINE CC03", norma="CICLO AM I085", parametro="50 a 80%", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "UMIDADE CABINE CC03", norma="CICLO AM I085", parametro="50 a 80%", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "UMIDADE CABINE CC03", norma="CICLO AM I085", parametro="50 a 80%", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "UMIDADE CABINE CC04", norma="CICLO AM I085", parametro="50 a 80%", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "UMIDADE CABINE CC04", norma="CICLO AM I085", parametro="50 a 80%", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "APLICAÇÃO VERNIZ 2K", "UMIDADE CABINE CC04", norma="CICLO AM I085", parametro="50 a 80%", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA QUEIMADOR G1", parametro="50 a 53 Hz", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA QUEIMADOR G1", parametro="50 a 53 Hz", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA QUEIMADOR G1", parametro="50 a 53 Hz", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA QUEIMADOR G2", parametro="50 a 53 Hz", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA QUEIMADOR G2", parametro="50 a 53 Hz", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA QUEIMADOR G2", parametro="50 a 53 Hz", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA EXAUSTOR E1S8", parametro="52 a 55Hz", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA EXAUSTOR E1S8", parametro="52 a 55Hz", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "FREQUÊNCIA EXAUSTOR E1S8", parametro="52 a 55Hz", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "FLASH OFF", "SISTEMA SECADOR DE AR", parametro="LIGADO", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BC1", "INEFICIENCIA ALTA TENSÃO", parametro="OK/KO", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BC2 EXTERNO", "INEFICIENCIA ALTA TENSÃO", parametro="OK/KO", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BC/CC", "LIMPEZA DAS BARREIRAS", norma="10h00", parametro="DE 05h/05h", turno_padrao="1", frequencia="2XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BC/CC", "LIMPEZA DAS BARREIRAS", norma="15h00", parametro="DE 05h/05h", turno_padrao="1", frequencia="2XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BC/CC", "LIMPEZA DAS BARREIRAS", norma="20h00", parametro="DE 05h/05h", turno_padrao="2", frequencia="2XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BC/CC", "LIMPEZA DAS BARREIRAS", norma="00h00", parametro="DE 05h/05h", turno_padrao="2", frequencia="2XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BC/CC", "LIMPEZA DAS BARREIRAS", norma="05h00", parametro="DE 05h00", turno_padrao="3", frequencia="2XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "PLC-CABINE", "TEMPERATURA DO COOLER PÓS FLASH OFF", parametro=">23°C", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "PLC-CABINE", "TEMPERATURA DO COOLER PÓS FLASH OFF", parametro=">23°C", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "PLC-CABINE", "TEMPERATURA DO COOLER PÓS FLASH OFF", parametro=">23°C", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "PLC-PMR", "PRESSÃO DO CO-SOLVENTE", parametro=">4 BAR", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "PLC-PMR", "PRESSÃO DO CO-SOLVENTE", parametro=">4 BAR", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "PLC-PMR", "PRESSÃO DO CO-SOLVENTE", parametro=">4 BAR", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC1", "VERIFICAR LENÇOL DE ÁGUA", parametro="OK/KO", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC1", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC1", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC2 INTERNO", "VERIFICAR LENÇOL DE ÁGUA", parametro="OK/KO", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC2 INTERNO", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC2 INTERNO", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC2 EXTERNO", "VERIFICAR LENÇOL DE ÁGUA", parametro="OK/KO", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC2 EXTERNO", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE BC2 EXTERNO", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE CC INTERNO", "VERIFICAR LENÇOL DE ÁGUA", parametro="OK/KO", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE CC INTERNO", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE CC INTERNO", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE CC EXTERNO", "VERIFICAR LENÇOL DE ÁGUA", parametro="OK/KO", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE CC EXTERNO", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "CABINE CC EXTERNO", "VERIFICAR LENÇOL DE ÁGUA", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BASE/CC", "VERIFICAR BATEDORES DAS ESTAÇÕES", parametro="OK/KO", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BASE/CC", "VERIFICAR BATEDORES DAS ESTAÇÕES", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TOP_COAT, "BASE/CC", "VERIFICAR BATEDORES DAS ESTAÇÕES", turno_padrao="3", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO TOP COAT", "ZONA 1.1", norma="ÚLTIMO SET POINT", parametro="120 +- 15"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO TOP COAT", "ZONA 2.1", norma="ÚLTIMO SET POINT", parametro="150 +- 15"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO TOP COAT", "ZONA 3.1", norma="ÚLTIMO SET POINT", parametro="145 +- 15"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO TOP COAT", "ZONA 4.1", norma="ÚLTIMO SET POINT", parametro="145 +- 15"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO TOP COAT", "ZONA 5.1", norma="ÚLTIMO SET POINT", parametro="120 +- 15"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO", "SET-POINT DE TEMPERATURA ITO A", parametro="615°C", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO", "SET-POINT DE TEMPERATURA ITO B", parametro="615°C", turno_padrao="1", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO", "SET-POINT DE TEMPERATURA ITO A", parametro="615°C", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO", "SET-POINT DE TEMPERATURA ITO B", parametro="615°C", turno_padrao="2", frequencia="1XTURNO"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO TCA", "TEMPERATURA INTERNA", norma="CICLO I090", parametro="<200ºC", frequencia="2XSEMANA"),
        _row(CABINE_PINTURA_ABA_TEMPERATURA_FORNO, "FORNO TCB", "TEMPERATURA INTERNA", norma="CICLO I090", parametro="<200ºC", frequencia="2XSEMANA"),
        _row(CABINE_PINTURA_ABA_DATA_PAQ, "FORNO TCA", "CURVA DE COZIMENTO", norma="SGU JPM22", parametro=">20min a 140ºC", frequencia="1XSEMANA"),
        _row(CABINE_PINTURA_ABA_DATA_PAQ, "FORNO TCB", "CURVA DE COZIMENTO", norma="SGU JPM22", parametro=">20min a 140ºC", frequencia="1XSEMANA"),
    ]
    result: list[dict[str, Any]] = []
    for ordem, row in enumerate(rows, start=1):
        result.append(
            {
                "escopo": "cabine_pintura",
                "modulo": "cabine-pintura",
                "module_code": "cabine-pintura",
                "setor_tipo": "AMBOS",
                "aba": row["aba"],
                "operacao": row["operacao"],
                "controle": row["controle"],
                "norma": row["norma"],
                "parametro": row["parametro"],
                "parametro_exibicao": row["parametro_exibicao"],
                "tipo_validacao": "nenhum",
                "ordem": ordem,
                "obrigatorio": True,
                "ativo": True,
                "frequencia": row["frequencia"],
                "frequencia_tipo": "diario",
                "prioridade": "medio",
                "responsavel_padrao": row["responsavel_padrao"],
                "turno_padrao": row["turno_padrao"],
                "observacao": None,
            }
        )
    return result
