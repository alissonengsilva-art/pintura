"""add grupo_retificador to modelos

Revision ID: 20260603_0034
Revises: 20260602_0033
Create Date: 2026-06-01 21:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260603_0034"
down_revision = "20260602_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("modelos", sa.Column("grupo_retificador", sa.String(length=20), nullable=True))
    op.create_index("ix_modelos_grupo_retificador", "modelos", ["grupo_retificador"], unique=False)

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE modelos
            SET grupo_retificador = CASE
                WHEN LOWER(COALESCE(codigo, '')) IN ('598') OR LOWER(COALESCE(nome, '')) IN ('commander') THEN 'grupo_1'
                WHEN LOWER(COALESCE(codigo, '')) IN ('551') OR LOWER(COALESCE(nome, '')) IN ('compass') THEN 'grupo_1'
                WHEN LOWER(COALESCE(codigo, '')) IN ('521') OR LOWER(COALESCE(nome, '')) IN ('ranegade', 'renegade') THEN 'grupo_2'
                WHEN LOWER(COALESCE(codigo, '')) IN ('291') OR LOWER(COALESCE(nome, '')) IN ('rampage') THEN 'grupo_3'
                WHEN LOWER(COALESCE(codigo, '')) IN ('226') OR LOWER(COALESCE(nome, '')) IN ('toro') THEN 'grupo_3'
                ELSE grupo_retificador
            END
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_modelos_grupo_retificador", table_name="modelos")
    op.drop_column("modelos", "grupo_retificador")
