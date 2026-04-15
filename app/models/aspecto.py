from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class AspectoLancamento(Base, TimestampMixin):
    __tablename__ = "aspecto_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    turno: Mapped[str] = mapped_column(String(80), nullable=False)
    modelo: Mapped[str] = mapped_column(String(120), nullable=False)
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    total_registros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    registros: Mapped[list[AspectoRegistro]] = relationship(
        back_populates="lancamento",
        cascade="all, delete-orphan",
        order_by="AspectoRegistro.id",
    )


class AspectoRegistro(Base, TimestampMixin):
    __tablename__ = "aspecto_registros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(
        ForeignKey("aspecto_lancamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    turno: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    modelo: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    responsavel_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    cis: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    cod_posicao: Mapped[str] = mapped_column(String(80), nullable=False)
    local: Mapped[str] = mapped_column(String(120), nullable=False)
    anomalia: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    lado: Mapped[str] = mapped_column(String(40), nullable=False)
    geracao: Mapped[str] = mapped_column(String(80), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    lancamento: Mapped[AspectoLancamento] = relationship(back_populates="registros")
