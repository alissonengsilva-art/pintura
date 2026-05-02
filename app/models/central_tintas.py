from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


CENTRAL_TINTAS_STATUS_EM_ANDAMENTO = "em_andamento"
CENTRAL_TINTAS_STATUS_CONCLUIDO = "concluido"


class CentralTintasRelatorio(Base, TimestampMixin):
    __tablename__ = "central_tintas_relatorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_controle: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    semana: Mapped[str] = mapped_column(String(20), nullable=False)
    mes: Mapped[str] = mapped_column(String(20), nullable=False)
    responsavel: Mapped[str] = mapped_column(String(120), nullable=False)
    turno: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CENTRAL_TINTAS_STATUS_EM_ANDAMENTO, index=True)
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    itens: Mapped[list["CentralTintasItem"]] = relationship(
        back_populates="relatorio",
        cascade="all, delete-orphan",
        order_by="CentralTintasItem.id",
    )


class CentralTintasItem(Base, TimestampMixin):
    __tablename__ = "central_tintas_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    central_tintas_id: Mapped[int] = mapped_column(
        ForeignKey("central_tintas_relatorios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operational_module_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_module_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    controle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parametro: Mapped[str | None] = mapped_column(String(120), nullable=True)
    valor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tinta: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lote: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ph: Mapped[str | None] = mapped_column(String(40), nullable=True)
    viscosidade: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sujidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    acoes_corretivas: Mapped[str | None] = mapped_column(Text, nullable=True)

    relatorio: Mapped[CentralTintasRelatorio] = relationship(back_populates="itens")


class CentralTintasRegistro(Base, TimestampMixin):
    __tablename__ = "central_tintas_registros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    responsavel: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    turno: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    tinta: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lote: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ph: Mapped[str | None] = mapped_column(String(40), nullable=True)
    viscosidade: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sujidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    acoes_corretivas: Mapped[str | None] = mapped_column(Text, nullable=True)
