from app.models.aspecto import AspectoLancamento, AspectoRegistro
from app.models.base import Base
from app.models.ed_lancamento import EDLancamento, EDLancamentoItem
from app.models.ed_item import ItemED
from app.models.espessura_ed import EspessuraEDItem, EspessuraEDLancamento
from app.models.operational_module import (
    OperationalModuleRecord,
    OperationalModuleSectorEntry,
    OperationalModuleSectorRecord,
)
from app.models.operational_item_applicability_override import (
    OperationalItemApplicabilityOverride,
    OVERRIDE_STATUS_APPLICABLE,
    OVERRIDE_STATUS_AUTOMATIC,
    OVERRIDE_STATUS_DISPENSED,
    OVERRIDE_STATUS_NOT_APPLICABLE,
)
from app.models.operational_module_item import OperationalModuleItem
from app.models.operational_shift import (
    OperationalShift,
    OperationalShiftModule,
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
from app.models.poder_penetracao import PoderPenetracaoItem, PoderPenetracaoLancamento
from app.models.pressao_filtros import PressaoFiltrosItem, PressaoFiltrosLancamento
from app.models.reference import Modelo, Responsavel, Setor, Turno
from app.models.rugosidade import RugosidadeItem, RugosidadeLancamento
from app.models.sigilatura import (
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
)
from app.models.tensao_retificadores import TensaoRetificadoresItem, TensaoRetificadoresLancamento
from app.models.temperatura_forno import TemperaturaFornoItem, TemperaturaFornoLancamento
from app.models.user import User

__all__ = [
    "Base",
    "AspectoLancamento",
    "AspectoRegistro",
    "EspessuraEDLancamento",
    "EspessuraEDItem",
    "OperationalModuleRecord",
    "OperationalModuleSectorRecord",
    "OperationalModuleSectorEntry",
    "OperationalModuleItem",
    "OperationalItemApplicabilityOverride",
    "OVERRIDE_STATUS_AUTOMATIC",
    "OVERRIDE_STATUS_APPLICABLE",
    "OVERRIDE_STATUS_NOT_APPLICABLE",
    "OVERRIDE_STATUS_DISPENSED",
    "OperationalShift",
    "OperationalShiftModule",
    "SHIFT_STATUS_NAO_INICIADO",
    "SHIFT_STATUS_EM_ANDAMENTO",
    "SHIFT_STATUS_PARCIAL",
    "SHIFT_STATUS_CONCLUIDO",
    "SHIFT_STATUS_LABELS",
    "MODULE_PREVISAO_OBRIGATORIO",
    "MODULE_PREVISAO_PREVISTO",
    "MODULE_PREVISAO_NAO_PREVISTO",
    "MODULE_PREVISAO_SEM_EXECUCAO",
    "MODULE_PREVISAO_LABELS",
    "PoderPenetracaoLancamento",
    "PoderPenetracaoItem",
    "RugosidadeLancamento",
    "RugosidadeItem",
    "Responsavel",
    "Modelo",
    "Setor",
    "Turno",
    "ItemED",
    "EDLancamento",
    "EDLancamentoItem",
    "PressaoFiltrosLancamento",
    "PressaoFiltrosItem",
    "TensaoRetificadoresLancamento",
    "TensaoRetificadoresItem",
    "TemperaturaFornoLancamento",
    "TemperaturaFornoItem",
    "SigilaturaTurno",
    "SigilaturaModulo",
    "SigilaturaResposta",
    "SigilaturaEspessuraPVC",
    "SigilaturaTemperaturaForno",
    "SigilaturaEscorrimento",
    "SIG_SHIFT_STATUS_NAO_INICIADO",
    "SIG_SHIFT_STATUS_EM_ANDAMENTO",
    "SIG_SHIFT_STATUS_PARCIAL",
    "SIG_SHIFT_STATUS_CONCLUIDO",
    "SIG_STATUS_LABELS",
    "SIG_MODULE_CODES",
    "User",
]
