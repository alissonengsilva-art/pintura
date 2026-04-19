"""no unused tables to drop safely

Revision ID: 20260419_0013
Revises: 20260419_0012
Create Date: 2026-04-19 00:30:00
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260419_0013"
down_revision: str | None = "20260419_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Intencionalmente sem operações.
    #
    # Análise do código atual:
    # - As tabelas legacy de lançamentos/itens ainda são usadas em:
    #   - app/services/operational_module_service.py (legacy_history_builder)
    #   - app/routes/module_pages.py (/legado/{legacy_id})
    #   - serviços específicos get_lancamento/list_history
    # - As tabelas operacionais novas são usadas pelo fluxo atual de turno.
    # - As tabelas de referência e turno também seguem em uso.
    #
    # Resultado: não há tabelas seguras para drop sem remover antes o suporte legado.
    pass


def downgrade() -> None:
    pass
