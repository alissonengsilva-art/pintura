from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class EspessuraEDLancamento(Base, TimestampMixin):
    __tablename__ = "espessura_ed_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    turno: Mapped[str] = mapped_column(String(80), nullable=False)
    modelo: Mapped[str] = mapped_column(String(120), nullable=False)
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    cis: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="rascunho")
    observacoes_gerais: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_pontos_preenchidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    itens: Mapped[list[EspessuraEDItem]] = relationship(
        back_populates="lancamento",
        cascade="all, delete-orphan",
        order_by="EspessuraEDItem.ponto_numero",
    )


class EspessuraEDItem(Base, TimestampMixin):
    __tablename__ = "espessura_ed_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(
        ForeignKey("espessura_ed_lancamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ponto_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_espessura: Mapped[float | None] = mapped_column(Float, nullable=True)

    lancamento: Mapped[EspessuraEDLancamento] = relationship(back_populates="itens")
