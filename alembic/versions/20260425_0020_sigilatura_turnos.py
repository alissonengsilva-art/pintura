"""add sigilatura turnos independent flow tables

Revision ID: 20260425_0020
Revises: 20260421_0019
Create Date: 2026-04-25 09:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260425_0020"
down_revision: str | None = "20260421_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sigilatura_turnos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("turno", sa.String(length=20), nullable=False),
        sa.Column("responsavel", sa.String(length=120), nullable=True),
        sa.Column("status_geral", sa.String(length=20), nullable=False, server_default="EM_ANDAMENTO"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("data_referencia", "turno", name="uq_sigilatura_turno_context"),
    )
    op.create_index(op.f("ix_sigilatura_turnos_data_referencia"), "sigilatura_turnos", ["data_referencia"], unique=False)
    op.create_index(op.f("ix_sigilatura_turnos_turno"), "sigilatura_turnos", ["turno"], unique=False)

    op.create_table(
        "sigilatura_modulos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("turno_id", sa.Integer(), sa.ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_code", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="NAO_INICIADO"),
        sa.Column("preenchidos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("desvios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("turno_id", "module_code", name="uq_sigilatura_modulo"),
    )
    op.create_index(op.f("ix_sigilatura_modulos_turno_id"), "sigilatura_modulos", ["turno_id"], unique=False)
    op.create_index(op.f("ix_sigilatura_modulos_module_code"), "sigilatura_modulos", ["module_code"], unique=False)

    op.create_table(
        "sigilatura_respostas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("turno_id", sa.Integer(), sa.ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modulo_id", sa.Integer(), sa.ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_code", sa.String(length=80), nullable=False),
        sa.Column("item_key", sa.String(length=120), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("operacao", sa.String(length=180), nullable=True),
        sa.Column("controle", sa.String(length=220), nullable=False),
        sa.Column("norma", sa.String(length=120), nullable=True),
        sa.Column("parametro", sa.String(length=150), nullable=True),
        sa.Column("frequencia", sa.String(length=60), nullable=True),
        sa.Column("turno_label", sa.String(length=20), nullable=True),
        sa.Column("valor", sa.String(length=120), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="NAO_AVALIADO"),
        sa.Column("desvio", sa.String(length=3), nullable=False, server_default="NAO"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("modulo_id", "item_key", name="uq_sigilatura_resposta_item"),
    )
    op.create_index(op.f("ix_sigilatura_respostas_turno_id"), "sigilatura_respostas", ["turno_id"], unique=False)
    op.create_index(op.f("ix_sigilatura_respostas_modulo_id"), "sigilatura_respostas", ["modulo_id"], unique=False)
    op.create_index(op.f("ix_sigilatura_respostas_module_code"), "sigilatura_respostas", ["module_code"], unique=False)

    op.create_table(
        "sigilatura_espessura_pvc",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("turno_id", sa.Integer(), sa.ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modulo_id", sa.Integer(), sa.ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ponto", sa.String(length=60), nullable=False),
        sa.Column("linha", sa.String(length=20), nullable=False),
        sa.Column("frequencia", sa.String(length=60), nullable=True),
        sa.Column("turno_label", sa.String(length=20), nullable=True),
        sa.Column("modelo", sa.String(length=40), nullable=True),
        sa.Column("valor_referencia", sa.String(length=80), nullable=True),
        sa.Column("valor_medido", sa.String(length=80), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="NAO_AVALIADO"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_sigilatura_espessura_pvc_turno_id"), "sigilatura_espessura_pvc", ["turno_id"], unique=False)
    op.create_index(op.f("ix_sigilatura_espessura_pvc_modulo_id"), "sigilatura_espessura_pvc", ["modulo_id"], unique=False)

    op.create_table(
        "sigilatura_temperatura_forno",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("turno_id", sa.Integer(), sa.ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modulo_id", sa.Integer(), sa.ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("semana", sa.String(length=40), nullable=True),
        sa.Column("responsavel", sa.String(length=120), nullable=True),
        sa.Column("zona", sa.String(length=40), nullable=False),
        sa.Column("referencia", sa.String(length=80), nullable=True),
        sa.Column("valor_medido", sa.String(length=80), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="NAO_AVALIADO"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_sigilatura_temperatura_forno_turno_id"), "sigilatura_temperatura_forno", ["turno_id"], unique=False)
    op.create_index(op.f("ix_sigilatura_temperatura_forno_modulo_id"), "sigilatura_temperatura_forno", ["modulo_id"], unique=False)

    op.create_table(
        "sigilatura_escorrimento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("turno_id", sa.Integer(), sa.ForeignKey("sigilatura_turnos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modulo_id", sa.Integer(), sa.ForeignKey("sigilatura_modulos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("semana", sa.String(length=40), nullable=True),
        sa.Column("responsavel", sa.String(length=120), nullable=True),
        sa.Column("numero_amostra", sa.String(length=40), nullable=True),
        sa.Column("lote", sa.String(length=60), nullable=True),
        sa.Column("real_temp_amb_auto", sa.String(length=60), nullable=True),
        sa.Column("real_estufa_auto", sa.String(length=60), nullable=True),
        sa.Column("real_temp_amb_manual", sa.String(length=60), nullable=True),
        sa.Column("real_estufa_manual", sa.String(length=60), nullable=True),
        sa.Column("resultados_obtidos", sa.Text(), nullable=True),
        sa.Column("acao_corretiva", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="NAO_AVALIADO"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_sigilatura_escorrimento_turno_id"), "sigilatura_escorrimento", ["turno_id"], unique=False)
    op.create_index(op.f("ix_sigilatura_escorrimento_modulo_id"), "sigilatura_escorrimento", ["modulo_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sigilatura_escorrimento_modulo_id"), table_name="sigilatura_escorrimento")
    op.drop_index(op.f("ix_sigilatura_escorrimento_turno_id"), table_name="sigilatura_escorrimento")
    op.drop_table("sigilatura_escorrimento")

    op.drop_index(op.f("ix_sigilatura_temperatura_forno_modulo_id"), table_name="sigilatura_temperatura_forno")
    op.drop_index(op.f("ix_sigilatura_temperatura_forno_turno_id"), table_name="sigilatura_temperatura_forno")
    op.drop_table("sigilatura_temperatura_forno")

    op.drop_index(op.f("ix_sigilatura_espessura_pvc_modulo_id"), table_name="sigilatura_espessura_pvc")
    op.drop_index(op.f("ix_sigilatura_espessura_pvc_turno_id"), table_name="sigilatura_espessura_pvc")
    op.drop_table("sigilatura_espessura_pvc")

    op.drop_index(op.f("ix_sigilatura_respostas_module_code"), table_name="sigilatura_respostas")
    op.drop_index(op.f("ix_sigilatura_respostas_modulo_id"), table_name="sigilatura_respostas")
    op.drop_index(op.f("ix_sigilatura_respostas_turno_id"), table_name="sigilatura_respostas")
    op.drop_table("sigilatura_respostas")

    op.drop_index(op.f("ix_sigilatura_modulos_module_code"), table_name="sigilatura_modulos")
    op.drop_index(op.f("ix_sigilatura_modulos_turno_id"), table_name="sigilatura_modulos")
    op.drop_table("sigilatura_modulos")

    op.drop_index(op.f("ix_sigilatura_turnos_turno"), table_name="sigilatura_turnos")
    op.drop_index(op.f("ix_sigilatura_turnos_data_referencia"), table_name="sigilatura_turnos")
    op.drop_table("sigilatura_turnos")

