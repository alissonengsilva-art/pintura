from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class TemperaturaFornoLancamento(Base, TimestampMixin):
    __tablename__ = "temperatura_forno_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="rascunho")
    observacoes_gerais: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_zonas_fora_padrao: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    itens: Mapped[list[TemperaturaFornoItem]] = relationship(
        back_populates="lancamento",
        cascade="all, delete-orphan",
        order_by="TemperaturaFornoItem.zona_numero",
    )


class TemperaturaFornoItem(Base, TimestampMixin):
    __tablename__ = "temperatura_forno_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(
        ForeignKey("temperatura_forno_lancamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zona_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_temperatura: Mapped[float | None] = mapped_column(Float, nullable=True)
    faixa_min: Mapped[float] = mapped_column(Float, nullable=False)
    faixa_max: Mapped[float] = mapped_column(Float, nullable=False)
    fora_padrao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    lancamento: Mapped[TemperaturaFornoLancamento] = relationship(back_populates="itens")
