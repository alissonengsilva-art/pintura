from __future__ import annotations

import base64
import hashlib
import hmac
import json

from app.db import SessionLocal
from app.models import User

class SimpleSessionMiddleware:
    def __init__(
        self,
        app,
        *,
        secret_key: str,
        cookie_name: str = "session",
        max_age: int = 60 * 60 * 12,
        same_site: str = "lax",
        https_only: bool = False,
    ):
        self.app = app
        self.secret_key = secret_key.encode("utf-8")
        self.cookie_name = cookie_name
        self.max_age = max_age
        self.same_site = same_site
        self.https_only = https_only

    def _sign(self, payload: bytes) -> str:
        return hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()

    def _serialize(self, session_data: dict) -> str:
        payload = json.dumps(session_data, separators=(",", ":"), sort_keys=True).encode("utf-8")
        encoded = base64.urlsafe_b64encode(payload).decode("ascii")
        signature = self._sign(payload)
        return f"{encoded}.{signature}"

    def _deserialize(self, raw_value: str | None) -> dict:
        if not raw_value or "." not in raw_value:
            return {}
        encoded, provided_signature = raw_value.rsplit(".", 1)
        try:
            payload = base64.urlsafe_b64decode(encoded.encode("ascii"))
        except Exception:
            return {}
        expected_signature = self._sign(payload)
        if not hmac.compare_digest(provided_signature, expected_signature):
            return {}
        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        cookie_header = headers.get(b"cookie", b"").decode("latin-1")
        cookies = {}
        for chunk in cookie_header.split(";"):
            if "=" not in chunk:
                continue
            name, value = chunk.split("=", 1)
            cookies[name.strip()] = value.strip()

        original_session = self._deserialize(cookies.get(self.cookie_name))
        scope["session"] = dict(original_session)
        user_id = scope["session"].get("user_id")
        if user_id:
            session = SessionLocal()
            try:
                user = session.get(User, int(user_id))
                if user is None or not user.is_active:
                    scope["session"] = {}
                else:
                    scope["session"]["username"] = user.username
                    scope["session"]["is_admin"] = bool(user.is_admin)
            finally:
                session.close()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                current_session = scope.get("session", {})
                if not current_session:
                    if original_session:
                        headers_list.append(
                            (
                                b"set-cookie",
                                f"{self.cookie_name}=null; Max-Age=0; Path=/; SameSite={self.same_site}".encode("latin-1"),
                            )
                        )
                elif current_session != original_session:
                    cookie_value = (
                        f"{self.cookie_name}={self._serialize(current_session)}; "
                        f"Max-Age={self.max_age}; Path=/; HttpOnly; SameSite={self.same_site}"
                    )
                    if self.https_only:
                        cookie_value += "; Secure"
                    headers_list.append((b"set-cookie", cookie_value.encode("latin-1")))
                message["headers"] = headers_list
            await send(message)

        await self.app(scope, receive, send_wrapper)
