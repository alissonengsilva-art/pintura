"""merge heads after prioridade branch

Revision ID: 20260602_0033
Revises: 20260601_0023, 20260504_0004
Create Date: 2026-06-02 09:00:00
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260602_0033"
down_revision: tuple[str, str] = ("20260601_0023", "20260504_0004")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    return None


def downgrade() -> None:
    return None
