"""add escorrimento images table

Revision ID: 20260427_0021
Revises: 20260425_0020
Create Date: 2026-04-27 10:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260427_0021"
down_revision: str | None = "20260425_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sigilatura_escorrimento_imagens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("turno_id", sa.Integer(), sa.ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modulo_id", sa.Integer(), sa.ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=180), nullable=False),
        sa.Column("file_path", sa.String(length=260), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_sigilatura_escorrimento_imagens_turno_id"), "sigilatura_escorrimento_imagens", ["turno_id"], unique=False)
    op.create_index(op.f("ix_sigilatura_escorrimento_imagens_modulo_id"), "sigilatura_escorrimento_imagens", ["modulo_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sigilatura_escorrimento_imagens_modulo_id"), table_name="sigilatura_escorrimento_imagens")
    op.drop_index(op.f("ix_sigilatura_escorrimento_imagens_turno_id"), table_name="sigilatura_escorrimento_imagens")
    op.drop_table("sigilatura_escorrimento_imagens")
