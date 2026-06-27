from __future__ import annotations

from hashlib import pbkdf2_hmac
from hmac import compare_digest
from os import urandom
from urllib.parse import quote, urlsplit

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


PBKDF2_ITERATIONS = 390000
SESSION_USER_ID_KEY = "user_id"
SESSION_USERNAME_KEY = "username"
SESSION_IS_ADMIN_KEY = "is_admin"


class AdminLoginRequiredError(Exception):
    def __init__(self, next_url: str):
        self.next_url = next_url


class AdminPermissionDeniedError(Exception):
    pass


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    password_value = password.strip()
    if not password_value:
        raise ValueError("Password cannot be empty.")
    salt_bytes = salt or urandom(16)
    digest = pbkdf2_hmac("sha256", password_value.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_hex, digest_hex = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    iterations = int(iterations_raw)
    calculated = pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    ).hex()
    return compare_digest(calculated, digest_hex)


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    normalized = username.strip().lower()
    if not normalized or not password:
        return None
    user = session.query(User).filter(User.username == normalized, User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def login_user(request: Request, user: User) -> None:
    request.session[SESSION_USER_ID_KEY] = user.id
    request.session[SESSION_USERNAME_KEY] = user.username
    request.session[SESSION_IS_ADMIN_KEY] = bool(user.is_admin)


def logout_user(request: Request) -> None:
    request.session.clear()


def sanitize_next_path(raw_value: str | None, default_path: str = "/dashboard") -> str:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return default_path
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return default_path
    path = parsed.path or default_path
    if not path.startswith("/"):
        return default_path
    return f"{path}?{parsed.query}" if parsed.query else path


def build_login_redirect(next_path: str) -> str:
    return f"/login?next={quote(sanitize_next_path(next_path), safe='/?=&')}"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if not user_id:
        return None
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        request.session.clear()
        return None
    if bool(request.session.get(SESSION_IS_ADMIN_KEY)) != bool(user.is_admin):
        request.session[SESSION_IS_ADMIN_KEY] = bool(user.is_admin)
    request.session[SESSION_USERNAME_KEY] = user.username
    return user


def require_admin(current_user: User | None = Depends(get_current_user)) -> User:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso administrativo restrito.")
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario sem permissao administrativa.")
    return current_user


def require_admin_page(request: Request, current_user: User | None = Depends(get_current_user)) -> User:
    if current_user is None:
        next_path = sanitize_next_path(str(request.url.path) + (f"?{request.url.query}" if request.url.query else ""), "/configuracoes")
        raise AdminLoginRequiredError(next_path)
    if not current_user.is_admin:
        raise AdminPermissionDeniedError()
    return current_user
