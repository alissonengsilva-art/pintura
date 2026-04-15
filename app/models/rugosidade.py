from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class RugosidadeLancamento(Base, TimestampMixin):
    __tablename__ = "rugosidade_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    sequencia: Mapped[str] = mapped_column(String(40), nullable=False)
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="rascunho")
    observacoes_gerais: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_modelos_fora_padrao: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    itens: Mapped[list[RugosidadeItem]] = relationship(
        back_populates="lancamento",
        cascade="all, delete-orphan",
        order_by="RugosidadeItem.modelo_codigo",
    )


class RugosidadeItem(Base, TimestampMixin):
    __tablename__ = "rugosidade_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(
        ForeignKey("rugosidade_lancamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    modelo_codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    valor_rugosidade: Mapped[float | None] = mapped_column(Float, nullable=True)
    limite_referencia: Mapped[float] = mapped_column(Float, nullable=False, default=14.0)
    fora_padrao: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    lancamento: Mapped[RugosidadeLancamento] = relationship(back_populates="itens")
