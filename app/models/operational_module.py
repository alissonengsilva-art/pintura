from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class OperationalModuleRecord(Base, TimestampMixin):
    __tablename__ = "operational_module_records"
    __table_args__ = (
        UniqueConstraint("module_code", "context_key", name="uq_operational_module_context"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    turno: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    context_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status_geral: Mapped[str] = mapped_column(String(20), nullable=False, default="NAO_INICIADO")
    context_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    legacy_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Vínculo com turno operacional (opcional para compatibilidade)
    shift_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_shifts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Relacionamentos
    shift: Mapped["OperationalShift | None"] = relationship(
        "OperationalShift",
        back_populates="modulos",
    )
    setores: Mapped[list[OperationalModuleSectorRecord]] = relationship(
        back_populates="registro_mestre",
        cascade="all, delete-orphan",
        order_by="OperationalModuleSectorRecord.id",
    )


class OperationalModuleSectorRecord(Base):
    __tablename__ = "operational_module_sector_records"
    __table_args__ = (
        UniqueConstraint("registro_mestre_id", "setor_tipo", name="uq_operational_module_sector"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registro_mestre_id: Mapped[int] = mapped_column(
        ForeignKey("operational_module_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    setor_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    responsavel_nome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    observacoes_setor: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_setor: Mapped[str] = mapped_column(String(20), nullable=False, default="NAO_INICIADO")
    metricas: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    iniciado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    registro_mestre: Mapped[OperationalModuleRecord] = relationship(back_populates="setores")
    respostas: Mapped[list[OperationalModuleSectorEntry]] = relationship(
        back_populates="setor_registro",
        cascade="all, delete-orphan",
        order_by="OperationalModuleSectorEntry.ordem",
    )


class OperationalModuleSectorEntry(Base, TimestampMixin):
    __tablename__ = "operational_module_sector_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setor_registro_id: Mapped[int] = mapped_column(
        ForeignKey("operational_module_sector_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    referencia: Mapped[str] = mapped_column(String(120), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valor_texto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valor_numero: Mapped[float | None] = mapped_column(Float, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    fora_padrao: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dados: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    setor_registro: Mapped[OperationalModuleSectorRecord] = relationship(back_populates="respostas")

