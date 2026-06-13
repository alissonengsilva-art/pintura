from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


CABINE_PINTURA_STATUS_EM_ANDAMENTO = "em_andamento"
CABINE_PINTURA_STATUS_CONCLUIDO = "concluido"


class CabinePinturaRelatorio(Base, TimestampMixin):
    __tablename__ = "cabine_pintura_relatorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_controle: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    semana: Mapped[str] = mapped_column(String(20), nullable=False)
    mes: Mapped[str] = mapped_column(String(20), nullable=False)
    responsavel: Mapped[str] = mapped_column(String(120), nullable=False)
    turno: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CABINE_PINTURA_STATUS_EM_ANDAMENTO,
        index=True,
    )
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    itens: Mapped[list["CabinePinturaItem"]] = relationship(
        back_populates="relatorio",
        cascade="all, delete-orphan",
        order_by="CabinePinturaItem.id",
    )


class CabinePinturaItem(Base, TimestampMixin):
    __tablename__ = "cabine_pintura_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cabine_pintura_id: Mapped[int] = mapped_column(
        ForeignKey("cabine_pintura_relatorios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operational_module_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_module_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    modulo: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    operacao_equipamento: Mapped[str | None] = mapped_column(String(160), nullable=True)
    descricao_controle: Mapped[str | None] = mapped_column(String(220), nullable=True)
    norma: Mapped[str | None] = mapped_column(String(160), nullable=True)
    parametro: Mapped[str | None] = mapped_column(String(180), nullable=True)
    valor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    relatorio: Mapped[CabinePinturaRelatorio] = relationship(back_populates="itens")
