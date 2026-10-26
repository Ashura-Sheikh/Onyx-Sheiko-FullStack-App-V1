"""Login for a local, single-user app (threat model T1, T2, T4).

1. When the server starts it prints a one-time **launch code** in the terminal.
2. The browser sends it once to POST /api/session. If it's right, the code is
   used up and the browser gets a session cookie (HttpOnly, SameSite=Strict).
3. Every other /api/* request needs that cookie **and** the custom header
   below. Browsers can't add a custom header to a cross-site request without
   a CORS preflight, which this server never approves.

Codes and sessions are random 256-bit values compared in constant time. Only
a SHA-256 hash of each session is kept, in memory, so sessions end when the
server stops. Nothing here is ever logged, and no token is ever accepted from
a URL.
"""

import hashlib
import secrets
import threading
import time
from collections.abc import Callable

SESSION_COOKIE = "onyx_session"
CSRF_HEADER = "X-Onyx-Request"
CSRF_VALUE = "1"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AuthState:
    """The launch code and live sessions for one server run."""

    def __init__(
        self,
        launch_code_ttl: int,
        session_ttl: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._session_ttl = session_ttl
        self._sessions: dict[str, float] = {}  # sha256(session) -> expiry
        self.launch_code = secrets.token_urlsafe(32)
        self._code_hash: str | None = _hash(self.launch_code)
        self._code_expires = clock() + launch_code_ttl

    def redeem_launch_code(self, code: str) -> str | None:
        """Exchange the launch code for a new session token, once.

        Returns None if the code is wrong, expired or already used.
        """
        with self._lock:
            if self._code_hash is None or self._clock() > self._code_expires:
                return None
            if not secrets.compare_digest(_hash(code), self._code_hash):
                return None
            self._code_hash = None  # single use
            session = secrets.token_urlsafe(32)
            self._sessions[_hash(session)] = self._clock() + self._session_ttl
            return session

    def is_valid_session(self, session: str | None) -> bool:
        if not session:
            return False
        key = _hash(session)
        with self._lock:
            expiry = self._sessions.get(key)
            if expiry is None:
                return False
            if self._clock() > expiry:
                del self._sessions[key]
                return False
            return True

    def end_session(self, session: str | None) -> None:
        if session:
            with self._lock:
                self._sessions.pop(_hash(session), None)
