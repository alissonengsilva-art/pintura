"""create users table for simple admin access

Revision ID: 20260420_0017
Revises: 20260420_0016
Create Date: 2026-04-20 00:30:00
"""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import pbkdf2_hmac

import sqlalchemy as sa
from alembic import op


revision: str = "20260420_0017"
down_revision: str | None = "20260420_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PBKDF2_ITERATIONS = 390000


def _hash_password(password: str) -> str:
    salt = bytes.fromhex("3d57e6ed8df7d4558c6e141ad5b12c31")
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    users_table = sa.table(
        "users",
        sa.column("username", sa.String()),
        sa.column("full_name", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("is_admin", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )

    op.bulk_insert(
        users_table,
        [
            {
                "username": "admin",
                "full_name": "Administrador",
                "password_hash": _hash_password("admin123"),
                "is_admin": True,
                "is_active": True,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("users")
