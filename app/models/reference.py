from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class Responsavel(Base, TimestampMixin):
    __tablename__ = "responsaveis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id"), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    setor: Mapped["Setor | None"] = relationship()

    @property
    def setor_nome(self) -> str | None:
        return self.setor.nome if self.setor else None


class Modelo(Base, TimestampMixin):
    __tablename__ = "modelos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    grupo_retificador: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def grupo_retificador_label(self) -> str | None:
        mapping = {"grupo_1": "Grupo 1", "grupo_2": "Grupo 2", "grupo_3": "Grupo 3"}
        return mapping.get(str(self.grupo_retificador or "").strip().lower()) if self.grupo_retificador else None


class Setor(Base, TimestampMixin):
    __tablename__ = "setores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    sigla: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Turno(Base, TimestampMixin):
    __tablename__ = "turnos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
