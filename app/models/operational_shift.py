from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


# Status do turno operacional
SHIFT_STATUS_NAO_INICIADO = "NAO_INICIADO"
SHIFT_STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"
SHIFT_STATUS_PARCIAL = "PARCIAL"
SHIFT_STATUS_CONCLUIDO = "CONCLUIDO"

SHIFT_STATUS_LABELS = {
    SHIFT_STATUS_NAO_INICIADO: "Não iniciado",
    SHIFT_STATUS_EM_ANDAMENTO: "Em andamento",
    SHIFT_STATUS_PARCIAL: "Parcial",
    SHIFT_STATUS_CONCLUIDO: "Concluído",
}

# Previsão de módulo no turno
MODULE_PREVISAO_OBRIGATORIO = "OBRIGATORIO"
MODULE_PREVISAO_PREVISTO = "PREVISTO"
MODULE_PREVISAO_NAO_PREVISTO = "NAO_PREVISTO"
MODULE_PREVISAO_SEM_EXECUCAO = "SEM_EXECUCAO"

MODULE_PREVISAO_LABELS = {
    MODULE_PREVISAO_OBRIGATORIO: "Obrigatório hoje",
    MODULE_PREVISAO_PREVISTO: "Previsto hoje",
    MODULE_PREVISAO_NAO_PREVISTO: "Não previsto hoje",
    MODULE_PREVISAO_SEM_EXECUCAO: "Sem execução hoje",
}


class OperationalShift(Base, TimestampMixin):
    """
    Turno Operacional - Entidade-mãe que agrupa todos os módulos de um dia/turno.
    
    Representa um ciclo operacional completo onde todos os 8 módulos são executados.
    O turno é a camada principal do fluxo operacional.
    """
    __tablename__ = "operational_shifts"
    __table_args__ = (
        UniqueConstraint("data_referencia", "turno", name="uq_operational_shift_context"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    turno: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    
    # Responsáveis do turno
    responsavel_pted: Mapped[str | None] = mapped_column(String(120), nullable=True)
    responsavel_lab: Mapped[str | None] = mapped_column(String(120), nullable=True)
    
    # Status geral do turno (calculado com base nos módulos)
    status_geral: Mapped[str] = mapped_column(String(20), nullable=False, default=SHIFT_STATUS_NAO_INICIADO)
    
    # Observações gerais do turno
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relacionamento com os módulos
    modulos: Mapped[list["OperationalModuleRecord"]] = relationship(
        "OperationalModuleRecord",
        back_populates="shift",
        cascade="all, delete-orphan",
        order_by="OperationalModuleRecord.id",
    )

    def __repr__(self) -> str:
        return f"<OperationalShift {self.data_referencia} turno={self.turno}>"

    @property
    def context_key(self) -> str:
        """Chave única do contexto do turno."""
        parts = [self.data_referencia.isoformat()]
        if self.turno:
            parts.append(self.turno)
        return "|".join(parts)


class OperationalShiftModule(Base):
    """
    Registro de previsão/status de um módulo dentro de um turno.
    
    Permite marcar módulos como "não previsto hoje" sem criar registro completo.
    """
    __tablename__ = "operational_shift_modules"
    __table_args__ = (
        UniqueConstraint("shift_id", "module_code", name="uq_shift_module"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    module_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    
    # Previsão do módulo no turno
    previsao: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default=MODULE_PREVISAO_PREVISTO
    )
    
    # Observação específica do módulo neste turno
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
