from sqlalchemy import Boolean, Float, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin


class OperationalModuleItem(Base, TimestampMixin):
    __tablename__ = "operational_module_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escopo: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    modulo: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    aba: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    module_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    setor_tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    operacao: Mapped[str | None] = mapped_column(String(150), nullable=True)
    controle: Mapped[str] = mapped_column(String(200), nullable=False)
    norma: Mapped[str | None] = mapped_column(String(120), nullable=True)
    parametro: Mapped[str | None] = mapped_column(String(150), nullable=True)
    unidade: Mapped[str | None] = mapped_column(String(40), nullable=True)
    valor_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    valor_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    tipo_validacao: Mapped[str] = mapped_column(String(30), default="nenhum", nullable=False)
    limite_minimo: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    limite_maximo: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    parametro_exibicao: Mapped[str | None] = mapped_column(String(120), nullable=True)
    referencia_visual: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    frequencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequencia_tipo: Mapped[str] = mapped_column(String(20), default="diario", nullable=False)
    dia_semana: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dia_mes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsavel_padrao: Mapped[str | None] = mapped_column(String(120), nullable=True)
    turno_padrao: Mapped[str | None] = mapped_column(String(80), nullable=True)
    numero_coleta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_item_ed_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
