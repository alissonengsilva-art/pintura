from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class PoderPenetracaoLancamento(Base, TimestampMixin):
    __tablename__ = "poder_penetracao_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    semana_referencia: Mapped[str] = mapped_column(String(20), nullable=False)
    modelo: Mapped[str] = mapped_column(String(120), nullable=False)
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    cis: Mapped[str | None] = mapped_column(String(120), nullable=True)
    velocidade: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    menor_valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_pontos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_aprovados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_reprovados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    percentual_aprovacao: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    acao_corretiva: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="rascunho")

    itens: Mapped[list[PoderPenetracaoItem]] = relationship(
        back_populates="lancamento",
        cascade="all, delete-orphan",
        order_by="PoderPenetracaoItem.ponto_numero",
    )


class PoderPenetracaoItem(Base, TimestampMixin):
    __tablename__ = "poder_penetracao_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(
        ForeignKey("poder_penetracao_lancamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ponto_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_medido: Mapped[float | None] = mapped_column(Float, nullable=True)
    aprovado: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    lancamento: Mapped[PoderPenetracaoLancamento] = relationship(back_populates="itens")
