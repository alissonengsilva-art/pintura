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
    parser = argparse.ArgumentParser(description="Redefine a senha de um usuario interno.")
    parser.add_argument("username", nargs="?", help="Login do usuario. Ex.: admin")
    parser.add_argument("password", nargs="?", help="Nova senha em texto puro.")
    parser.add_argument(
        "--admin",
        choices=["true", "false"],
        default=None,
        help="Opcional: define se o usuario sera administrador.",
    )
    return parser


def prompt_missing_args(args):
    if not args.username:
        args.username = input("Usuario: ").strip()
    if not args.password:
        args.password = getpass.getpass("Nova senha: ").strip()
    if args.admin is None:
        admin_raw = input("Alterar admin? (true/false ou enter para manter): ").strip().lower()
        if admin_raw in {"true", "false"}:
            args.admin = admin_raw
    return args


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args = prompt_missing_args(args)

    session = SessionLocal()
    try:
        username = args.username.strip().lower()
        user = session.query(User).filter(User.username == username).first()
        if user is None:
            print(f"Usuario '{username}' nao encontrado.")
            return 1

        user.password_hash = hash_password(args.password)
        if args.admin is not None:
            user.is_admin = args.admin == "true"

        session.commit()
        print(f"Senha atualizada com sucesso para '{username}'.")
        print(f"is_admin={user.is_admin}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
