"""mark complex parameter rules as textual references

Revision ID: 20260502_0025
Revises: 20260502_0024
Create Date: 2026-05-02 13:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260502_0025"
down_revision = "20260502_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE operational_module_items
            SET tipo_validacao = 'texto'
            WHERE (
                COALESCE(parametro_exibicao, parametro, '') LIKE '%(%'
                OR COALESCE(parametro_exibicao, parametro, '') LIKE '% a %'
                OR COALESCE(parametro_exibicao, parametro, '') LIKE '%min%'
            )
            AND COALESCE(parametro_exibicao, parametro, '') <> ''
            """
        )
    )


def downgrade() -> None:
    return None
