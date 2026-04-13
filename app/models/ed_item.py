from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin


class ItemED(Base, TimestampMixin):
    __tablename__ = "itens_ed"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operacao_equipamento: Mapped[str] = mapped_column(String(150), nullable=False)
    descricao_controle: Mapped[str] = mapped_column(String(200), nullable=False)
    norma: Mapped[str | None] = mapped_column(String(120), nullable=True)
    parametro: Mapped[str | None] = mapped_column(String(150), nullable=True)
    frequencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    responsavel_padrao: Mapped[str | None] = mapped_column(String(120), nullable=True)
    setor_padrao: Mapped[str | None] = mapped_column(String(120), nullable=True)
    turno_padrao: Mapped[str | None] = mapped_column(String(80), nullable=True)
    numero_coleta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ordem_exibicao: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
