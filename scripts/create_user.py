from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import SessionLocal
from app.models import User
from app.services.auth_service import hash_password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cria um usuario interno.")
    parser.add_argument("username", nargs="?", help="Login do usuario. Ex.: admin")
    parser.add_argument("password", nargs="?", help="Senha em texto puro.")
    parser.add_argument("full_name", nargs="?", help="Nome completo do usuario.")
    parser.add_argument(
        "--admin",
        choices=["true", "false"],
        default="true",
        help="Define se o usuario sera administrador (padrao: true).",
    )
    return parser


def prompt_missing_args(args):
    if not args.username:
        args.username = input("Usuario: ").strip()
    if not args.full_name:
        args.full_name = input("Nome completo: ").strip()
    if not args.password:
        args.password = getpass.getpass("Senha: ").strip()
    if args.admin is None:
        admin_raw = input("Administrador? (s/n): ").strip().lower()
        args.admin = "true" if admin_raw in {"s", "sim", "y", "yes"} else "false"
    return args


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args = prompt_missing_args(args)

    session = SessionLocal()
    try:
        username = args.username.strip().lower()
        existing_user = session.query(User).filter(User.username == username).first()
        if existing_user is not None:
            print(f"Usuario '{username}' ja existe.")
            return 1

        user = User(
            username=username,
            full_name=args.full_name.strip(),
            password_hash=hash_password(args.password),
            is_admin=args.admin == "true",
            is_active=True,
        )
        session.add(user)
        session.commit()
        print(f"Usuario '{username}' criado com sucesso.")
        print(f"is_admin={user.is_admin}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
