"""catalog scope/modulo/aba fields for operational items

Revision ID: 20260502_0026
Revises: 20260502_0025
Create Date: 2026-05-02 12:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260502_0026"
down_revision = "20260502_0025"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("operational_module_items", "escopo"):
        op.add_column("operational_module_items", sa.Column("escopo", sa.String(length=80), nullable=True))
        op.create_index(op.f("ix_operational_module_items_escopo"), "operational_module_items", ["escopo"], unique=False)

    if not _has_column("operational_module_items", "modulo"):
        op.add_column("operational_module_items", sa.Column("modulo", sa.String(length=80), nullable=True))
        op.create_index(op.f("ix_operational_module_items_modulo"), "operational_module_items", ["modulo"], unique=False)

    if not _has_column("operational_module_items", "aba"):
        op.add_column("operational_module_items", sa.Column("aba", sa.String(length=40), nullable=True))
        op.create_index(op.f("ix_operational_module_items_aba"), "operational_module_items", ["aba"], unique=False)

    if not _has_column("operational_module_items", "referencia_visual"):
        op.add_column("operational_module_items", sa.Column("referencia_visual", sa.String(length=160), nullable=True))

    op.execute(
        """
        UPDATE operational_module_items
        SET escopo = CASE
            WHEN module_code IN ('sigilatura', 'espessura-pvc', 'temperatura-forno-sigilatura', 'escorrimento') THEN 'sigilatura'
            WHEN module_code = 'central-tintas' THEN 'central_tintas'
            ELSE 'ed'
        END
        WHERE escopo IS NULL OR escopo = ''
        """
    )

    op.execute(
        """
        UPDATE operational_module_items
        SET modulo = module_code
        WHERE modulo IS NULL OR modulo = ''
        """
    )

    op.execute(
        """
        UPDATE operational_module_items
        SET aba = CASE
            WHEN setor_tipo = 'PTED' THEN 'PTED'
            WHEN setor_tipo = 'LABORATORIO' THEN 'Laboratorio'
            WHEN setor_tipo = 'AMBOS' THEN 'Ambos'
            ELSE setor_tipo
        END
        WHERE aba IS NULL OR aba = ''
        """
    )

    op.execute(
        """
        UPDATE operational_module_items
        SET referencia_visual = COALESCE(NULLIF(parametro_exibicao, ''), NULLIF(parametro, ''))
        WHERE referencia_visual IS NULL OR referencia_visual = ''
        """
    )


def downgrade() -> None:
    if _has_column("operational_module_items", "referencia_visual"):
        op.drop_column("operational_module_items", "referencia_visual")

    if _has_column("operational_module_items", "aba"):
        op.drop_index(op.f("ix_operational_module_items_aba"), table_name="operational_module_items")
        op.drop_column("operational_module_items", "aba")

    if _has_column("operational_module_items", "modulo"):
        op.drop_index(op.f("ix_operational_module_items_modulo"), table_name="operational_module_items")
        op.drop_column("operational_module_items", "modulo")

    if _has_column("operational_module_items", "escopo"):
        op.drop_index(op.f("ix_operational_module_items_escopo"), table_name="operational_module_items")
        op.drop_column("operational_module_items", "escopo")
