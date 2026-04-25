from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


SIG_SHIFT_STATUS_NAO_INICIADO = "NAO_INICIADO"
SIG_SHIFT_STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"
SIG_SHIFT_STATUS_PARCIAL = "PARCIAL"
SIG_SHIFT_STATUS_CONCLUIDO = "CONCLUIDO"

SIG_STATUS_LABELS = {
    SIG_SHIFT_STATUS_NAO_INICIADO: "Não iniciado",
    SIG_SHIFT_STATUS_EM_ANDAMENTO: "Em andamento",
    SIG_SHIFT_STATUS_PARCIAL: "Parcial",
    SIG_SHIFT_STATUS_CONCLUIDO: "Concluído",
}

SIG_MODULE_CODES = (
    "sigilatura",
    "espessura-pvc",
    "temperatura-forno-sigilatura",
    "escorrimento",
)


class SigilaturaTurno(Base, TimestampMixin):
    __tablename__ = "sigilatura_turnos"
    __table_args__ = (UniqueConstraint("data_referencia", "turno", name="uq_sigilatura_turno_context"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    turno: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    responsavel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status_geral: Mapped[str] = mapped_column(String(20), nullable=False, default=SIG_SHIFT_STATUS_EM_ANDAMENTO)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    modulos: Mapped[list["SigilaturaModulo"]] = relationship(
        back_populates="turno_ref",
        cascade="all, delete-orphan",
        order_by="SigilaturaModulo.id",
    )


class SigilaturaModulo(Base, TimestampMixin):
    __tablename__ = "sigilatura_modulos"
    __table_args__ = (UniqueConstraint("turno_id", "module_code", name="uq_sigilatura_modulo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False, index=True)
    module_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SIG_SHIFT_STATUS_NAO_INICIADO)
    preenchidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    desvios: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    turno_ref: Mapped["SigilaturaTurno"] = relationship(back_populates="modulos")
    respostas: Mapped[list["SigilaturaResposta"]] = relationship(
        back_populates="modulo_ref",
        cascade="all, delete-orphan",
        order_by="SigilaturaResposta.ordem",
    )


class SigilaturaResposta(Base, TimestampMixin):
    __tablename__ = "sigilatura_respostas"
    __table_args__ = (UniqueConstraint("modulo_id", "item_key", name="uq_sigilatura_resposta_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False, index=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False, index=True)
    module_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operacao: Mapped[str | None] = mapped_column(String(180), nullable=True)
    controle: Mapped[str] = mapped_column(String(220), nullable=False)
    norma: Mapped[str | None] = mapped_column(String(120), nullable=True)
    parametro: Mapped[str | None] = mapped_column(String(150), nullable=True)
    frequencia: Mapped[str | None] = mapped_column(String(60), nullable=True)
    turno_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    valor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NAO_AVALIADO")
    desvio: Mapped[str] = mapped_column(String(3), nullable=False, default="NAO")

    modulo_ref: Mapped["SigilaturaModulo"] = relationship(back_populates="respostas")


class SigilaturaEspessuraPVC(Base, TimestampMixin):
    __tablename__ = "sigilatura_espessura_pvc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False, index=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False, index=True)
    ponto: Mapped[str] = mapped_column(String(60), nullable=False)
    linha: Mapped[str] = mapped_column(String(20), nullable=False)
    frequencia: Mapped[str | None] = mapped_column(String(60), nullable=True)
    turno_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    valor_referencia: Mapped[str | None] = mapped_column(String(80), nullable=True)
    valor_medido: Mapped[str | None] = mapped_column(String(80), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NAO_AVALIADO")


class SigilaturaTemperaturaForno(Base, TimestampMixin):
    __tablename__ = "sigilatura_temperatura_forno"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False, index=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False, index=True)
    semana: Mapped[str | None] = mapped_column(String(40), nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    zona: Mapped[str] = mapped_column(String(40), nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(80), nullable=True)
    valor_medido: Mapped[str | None] = mapped_column(String(80), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NAO_AVALIADO")


class SigilaturaEscorrimento(Base, TimestampMixin):
    __tablename__ = "sigilatura_escorrimento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False, index=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False, index=True)
    semana: Mapped[str | None] = mapped_column(String(40), nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    numero_amostra: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lote: Mapped[str | None] = mapped_column(String(60), nullable=True)
    real_temp_amb_auto: Mapped[str | None] = mapped_column(String(60), nullable=True)
    real_estufa_auto: Mapped[str | None] = mapped_column(String(60), nullable=True)
    real_temp_amb_manual: Mapped[str | None] = mapped_column(String(60), nullable=True)
    real_estufa_manual: Mapped[str | None] = mapped_column(String(60), nullable=True)
    resultados_obtidos: Mapped[str | None] = mapped_column(Text, nullable=True)
    acao_corretiva: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NAO_AVALIADO")

