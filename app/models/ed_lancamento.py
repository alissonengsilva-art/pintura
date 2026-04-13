from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.ed_item import ItemED


class EDLancamento(Base, TimestampMixin):
    __tablename__ = "ed_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    tipo_dia: Mapped[str] = mapped_column(String(20), nullable=False)
    setor: Mapped[str] = mapped_column(String(120), nullable=False)
    turno: Mapped[str] = mapped_column(String(80), nullable=False)
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="rascunho")
    observacoes_gerais: Mapped[str | None] = mapped_column(Text, nullable=True)

    itens: Mapped[list[EDLancamentoItem]] = relationship(
        back_populates="lancamento",
        cascade="all, delete-orphan",
        order_by="EDLancamentoItem.id",
    )


class EDLancamentoItem(Base, TimestampMixin):
    __tablename__ = "ed_lancamento_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(ForeignKey("ed_lancamentos.id", ondelete="CASCADE"), nullable=False, index=True)
    item_ed_id: Mapped[int] = mapped_column(ForeignKey("itens_ed.id"), nullable=False, index=True)
    valor_informado: Mapped[str | None] = mapped_column(String(150), nullable=True)
    observacao_item: Mapped[str | None] = mapped_column(Text, nullable=True)
    fora_parametro: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    lancamento: Mapped[EDLancamento] = relationship(back_populates="itens")
    item_ed: Mapped[ItemED] = relationship()
