"""Security middleware. Plain ASGI, so it wraps every request, including ones
that never reach a route (404s, rejected requests). See docs/threat-model.md.

Order, outermost first (set in app.py):
  TrustedHostMiddleware  -> Host header allowlist (T3)
  SecurityHeaders        -> CSP and other headers on every response (T6)
  BodySizeLimit          -> refuse oversized bodies (T7)
  ApiGuard               -> /api/*: custom header + Origin (T2), session (T1)
"""

import json
from collections.abc import Iterable
from http.cookies import CookieError, SimpleCookie

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from onyx.auth import CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE, AuthState


def content_security_policy(nonce: str | None = None) -> str:
    """The CSP for a response. Only the HTML page gets a nonce, so Radix's
    <style> tags carrying it are allowed; nothing else inline ever is."""
    style = f"style-src 'self' 'nonce-{nonce}'" if nonce else "style-src 'self'"
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            style,
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )


CONTENT_SECURITY_POLICY = content_security_policy()


SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
]

# Reachable without a session: logging in, and asking whether you're logged in.
PUBLIC_API = {("POST", "/api/session"), ("GET", "/api/session")}

SAFE_METHODS = {"GET", "HEAD"}


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


async def _send_json(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class SecurityHeaders:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope["path"].startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                replaced = _HEADER_NAMES | ({b"cache-control"} if is_api else set())
                headers = [h for h in message.get("headers", []) if h[0] not in replaced]
                nonce = scope.get("state", {}).get("csp_nonce") if not is_api else None
                headers.append(
                    (b"content-security-policy", content_security_policy(nonce).encode())
                )
                headers += SECURITY_HEADERS
                if is_api:
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


_HEADER_NAMES = {name for name, _ in SECURITY_HEADERS} | {b"content-security-policy"}


class BodySizeLimit:
    """Reads the body up front (bounded) and refuses it if it's too big."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = _header(scope, b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await _send_json(send, 413, "Request body too large")
            return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await _send_json(send, 413, "Request body too large")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        sent = False

        async def replay() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class ApiGuard:
    """Deny by default: every /api/* route needs the custom header, a same-site
    request and (except PUBLIC_API) a valid session. A new route can't forget
    to opt in."""

    def __init__(self, app: ASGIApp, auth: AuthState, allowed_origins: Iterable[str]) -> None:
        self.app = app
        self.auth = auth
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        method = scope["method"]

        # T2: a cross-site page can't set a custom header without a CORS
        # preflight, and this server approves none.
        if _header(scope, CSRF_HEADER.lower().encode()) != CSRF_VALUE:
            await _send_json(send, 403, "Missing request header")
            return
        if _header(scope, b"sec-fetch-site") == "cross-site":
            await _send_json(send, 403, "Cross-site request refused")
            return
        origin = _header(scope, b"origin")
        if method not in SAFE_METHODS and origin is not None and origin not in self.allowed_origins:
            await _send_json(send, 403, "Origin not allowed")
            return

        # T1: everything except logging in needs a session.
        if (method, scope["path"]) not in PUBLIC_API:
            if not self.auth.is_valid_session(session_from_scope(scope)):
                await _send_json(send, 401, "Not signed in")
                return

        await self.app(scope, receive, send)


def session_from_scope(scope: Scope) -> str | None:
    raw = _header(scope, b"cookie")
    if not raw:
        return None
    try:
        cookie = SimpleCookie()
        cookie.load(raw)
    except CookieError:
        return None
    morsel = cookie.get(SESSION_COOKIE)
    return morsel.value if morsel else None
