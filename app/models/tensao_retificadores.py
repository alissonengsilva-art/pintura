from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class TensaoRetificadoresLancamento(Base, TimestampMixin):
    __tablename__ = "tensao_retificadores_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    turno: Mapped[str] = mapped_column(String(80), nullable=False)
    modelo: Mapped[str] = mapped_column(String(120), nullable=False)
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="rascunho")
    observacoes_gerais: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_zonas_fora_padrao: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    itens: Mapped[list[TensaoRetificadoresItem]] = relationship(
        back_populates="lancamento",
        cascade="all, delete-orphan",
        order_by="TensaoRetificadoresItem.zona_numero",
    )


class TensaoRetificadoresItem(Base, TimestampMixin):
    __tablename__ = "tensao_retificadores_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(
        ForeignKey("tensao_retificadores_lancamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zona_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_tensao: Mapped[float | None] = mapped_column(Float, nullable=True)
    fora_padrao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    lancamento: Mapped[TensaoRetificadoresLancamento] = relationship(back_populates="itens")
