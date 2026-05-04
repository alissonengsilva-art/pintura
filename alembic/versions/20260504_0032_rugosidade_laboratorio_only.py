"""scope rugosidade items to laboratorio

Revision ID: 20260504_0032
Revises: 20260503_0031
Create Date: 2026-05-04 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260504_0032"
down_revision: str | None = "20260503_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE operational_module_items
        SET setor_tipo = 'LABORATORIO',
            aba = 'Laboratorio'
        WHERE module_code = 'rugosidade'
           OR (escopo = 'ed' AND modulo = 'rugosidade')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE operational_module_items
        SET setor_tipo = 'AMBOS',
            aba = 'Ambos'
        WHERE module_code = 'rugosidade'
           OR (escopo = 'ed' AND modulo = 'rugosidade')
        """
    )
