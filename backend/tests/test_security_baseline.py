"""Security baseline tests. Each test names the threat-model row it proves
(docs/threat-model.md)."""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from onyx.__main__ import main, parse_args, uvicorn_config
from onyx.app import create_app
from onyx.auth import CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE, AuthState
from onyx.config import HOST, ConfigError, load_settings
from onyx.security import CONTENT_SECURITY_POLICY

DEV_VAULT = Path(__file__).resolve().parents[2] / "dev-vault"
PORT = 8731
BASE = f"http://127.0.0.1:{PORT}"
OK = {CSRF_HEADER: CSRF_VALUE}


@pytest.fixture
def app():
    return create_app(load_settings(DEV_VAULT, PORT))


@pytest.fixture
def client(app):
    return TestClient(app, base_url=BASE)


def sign_in(client, app) -> str:
    """Log in with the real launch code; return the session cookie value."""
    response = client.post("/api/session", json={"code": app.state.auth.launch_code}, headers=OK)
    assert response.status_code == 204
    client.cookies.clear()  # tests send the cookie explicitly
    return response.cookies[SESSION_COOKIE]


def with_session(session: str) -> dict[str, str]:
    return {**OK, "Cookie": f"{SESSION_COOKIE}={session}"}


# --- Configuration and binding -------------------------------------------------


def test_vault_is_required():
    with pytest.raises(ConfigError, match="required"):
        load_settings(None)
    with pytest.raises(ConfigError, match="required"):
        load_settings("  ")


def test_vault_must_be_an_existing_folder(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_settings(tmp_path / "missing")
    a_file = tmp_path / "file.md"
    a_file.write_text("x")
    with pytest.raises(ConfigError, match="not a folder"):
        load_settings(a_file)


def test_port_range_is_checked():
    with pytest.raises(ConfigError, match="Port"):
        load_settings(DEV_VAULT, 80)


def test_main_refuses_to_start_without_a_vault(monkeypatch, capsys):
    monkeypatch.delenv("ONYX_VAULT", raising=False)
    assert main([]) == 2
    assert "vault folder is required" in capsys.readouterr().err


def test_server_always_binds_to_localhost(app):
    config = uvicorn_config(app, load_settings(DEV_VAULT, PORT))
    assert config.host == HOST == "127.0.0.1"


def test_there_is_no_host_option():
    with pytest.raises(SystemExit):
        parse_args(["--vault", str(DEV_VAULT), "--host", "0.0.0.0"])  # noqa: S104


# --- T3: Host header (DNS rebinding) ------------------------------------------


@pytest.mark.parametrize("path", ["/api/health", "/api/session", "/anything"])
def test_foreign_host_is_rejected(client, path):
    response = client.get(path, headers={**OK, "Host": f"evil.example:{PORT}"})
    assert response.status_code == 400


def test_localhost_name_is_accepted(app):
    client = TestClient(app, base_url=f"http://localhost:{PORT}")
    assert client.get("/api/session", headers=OK).json() == {"authenticated": False}


# --- T1: a session is required -------------------------------------------------


def test_api_needs_a_session(client):
    assert client.get("/api/health", headers=OK).status_code == 401


def test_a_made_up_session_is_rejected(client):
    assert client.get("/api/health", headers=with_session("not-a-real-session")).status_code == 401


def test_signed_in_request_works(client, app):
    session = sign_in(client, app)
    response = client.get("/api/health", headers=with_session(session))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_route_still_needs_a_session(client):
    """Deny by default: a route that doesn't exist (or forgot to opt in) is still guarded."""
    assert client.get("/api/not-a-route", headers=OK).status_code == 401


# --- T2: CSRF ------------------------------------------------------------------


def test_custom_header_is_required(client, app):
    session = sign_in(client, app)
    cookie = {"Cookie": f"{SESSION_COOKIE}={session}"}
    assert client.get("/api/health", headers=cookie).status_code == 403
    assert client.get("/api/health", headers={**cookie, CSRF_HEADER: "0"}).status_code == 403


def test_sign_in_also_needs_the_header(client, app):
    response = client.post("/api/session", json={"code": app.state.auth.launch_code})
    assert response.status_code == 403
    # ...and the code wasn't used up by the refused attempt.
    assert (
        client.post(
            "/api/session", json={"code": app.state.auth.launch_code}, headers=OK
        ).status_code
        == 204
    )


def test_foreign_origin_is_refused(client, app):
    response = client.post(
        "/api/session",
        json={"code": app.state.auth.launch_code},
        headers={**OK, "Origin": "http://evil.example"},
    )
    assert response.status_code == 403


def test_own_origin_is_allowed(client, app):
    response = client.post(
        "/api/session", json={"code": app.state.auth.launch_code}, headers={**OK, "Origin": BASE}
    )
    assert response.status_code == 204


def test_cross_site_fetch_is_refused(client, app):
    session = sign_in(client, app)
    headers = {**with_session(session), "Sec-Fetch-Site": "cross-site"}
    assert client.get("/api/health", headers=headers).status_code == 403


def test_preflight_is_never_approved(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers


# --- T4: launch code and session handling --------------------------------------


def test_wrong_launch_code_is_refused(client):
    assert client.post("/api/session", json={"code": "wrong"}, headers=OK).status_code == 401


def test_launch_code_works_only_once(client, app):
    code = app.state.auth.launch_code
    assert client.post("/api/session", json={"code": code}, headers=OK).status_code == 204
    assert client.post("/api/session", json={"code": code}, headers=OK).status_code == 401


def test_session_cookie_attributes(client, app):
    response = client.post("/api/session", json={"code": app.state.auth.launch_code}, headers=OK)
    set_cookie = response.headers["set-cookie"].lower()
    assert set_cookie.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie
    assert "path=/" in set_cookie


def test_session_in_a_url_is_ignored(client, app):
    session = sign_in(client, app)
    for name in ("session", "token", SESSION_COOKIE):
        assert client.get(f"/api/health?{name}={session}", headers=OK).status_code == 401


def test_sign_out_ends_the_session(client, app):
    session = sign_in(client, app)
    assert client.delete("/api/session", headers=with_session(session)).status_code == 204
    assert client.get("/api/health", headers=with_session(session)).status_code == 401


def test_restart_ends_sessions(client, app):
    session = sign_in(client, app)
    restarted = TestClient(create_app(load_settings(DEV_VAULT, PORT)), base_url=BASE)
    assert restarted.get("/api/health", headers=with_session(session)).status_code == 401


def test_session_status(client, app):
    assert client.get("/api/session", headers=OK).json() == {"authenticated": False}
    session = sign_in(client, app)
    assert client.get("/api/session", headers=with_session(session)).json() == {
        "authenticated": True
    }


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_launch_code_expires():
    clock = FakeClock()
    auth = AuthState(launch_code_ttl=60, session_ttl=3600, clock=clock)
    clock.now += 61
    assert auth.redeem_launch_code(auth.launch_code) is None


def test_session_expires():
    clock = FakeClock()
    auth = AuthState(launch_code_ttl=60, session_ttl=3600, clock=clock)
    session = auth.redeem_launch_code(auth.launch_code)
    assert auth.is_valid_session(session)
    clock.now += 3601
    assert not auth.is_valid_session(session)


def test_codes_and_sessions_are_long_random_values():
    first = AuthState(60, 3600)
    second = AuthState(60, 3600)
    assert first.launch_code != second.launch_code
    assert len(first.launch_code) >= 43  # 32 random bytes, base64url


# --- T7: request size and validation --------------------------------------------


def test_oversized_body_is_refused(client):
    body = b'{"code": "' + b"x" * (1024 * 1024) + b'"}'
    response = client.post(
        "/api/session", content=body, headers={**OK, "Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_oversized_body_without_length_is_refused(client):
    def chunks():
        for _ in range(17):
            yield b"x" * 65536  # 1.06 MiB in total, sent without Content-Length

    response = client.post(
        "/api/session", content=chunks(), headers={**OK, "Content-Type": "application/json"}
    )
    assert response.status_code == 413


@pytest.mark.parametrize(
    "body",
    [{}, {"code": ""}, {"code": "x" * 129}, {"code": "x", "extra": 1}, {"code": 123}],
)
def test_invalid_sign_in_body_is_refused(client, body):
    assert client.post("/api/session", json=body, headers=OK).status_code == 422


# --- T6 (server side): security headers ----------------------------------------


@pytest.mark.parametrize(
    ("path", "status"), [("/api/health", 401), ("/api/session", 200), ("/api/missing", 401)]
)
def test_security_headers_on_every_response(client, path, status):
    response = client.get(path, headers=OK)
    assert response.status_code == status
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"


def test_csp_forbids_inline_scripts_and_styles():
    directives = dict(d.split(" ", 1) for d in CONTENT_SECURITY_POLICY.split("; "))
    assert directives["script-src"] == "'self'"
    assert directives["style-src"] == "'self'"
    assert directives["frame-ancestors"] == "'none'"
    assert "unsafe" not in CONTENT_SECURITY_POLICY


def test_api_responses_are_not_cached(client):
    assert client.get("/api/session", headers=OK).headers["cache-control"] == "no-store"


def test_interactive_docs_are_disabled(client):
    """/docs and friends fall through to the app's own page, never Swagger."""
    for path in ("/docs", "/redoc", "/openapi.json"):
        body = client.get(path).text.lower()
        assert "swagger" not in body
        assert "redoc" not in body
        assert '"openapi"' not in body


# --- T9: no secrets in logs --------------------------------------------------------


def test_launch_code_and_session_never_logged(client, app, caplog):
    caplog.set_level(logging.DEBUG)
    code = app.state.auth.launch_code
    client.post("/api/session", json={"code": "wrong"}, headers=OK)
    session = sign_in(client, app)
    client.get("/api/health", headers=with_session(session))
    client.delete("/api/session", headers=with_session(session))
    assert code not in caplog.text
    assert session not in caplog.text


# --- Startup output ------------------------------------------------------------


def test_launch_code_is_printed_immediately_when_output_is_piped():
    """Regression: Python buffers stdout when it isn't a terminal (an IDE task,
    a pipe), so without flushing, the launch code didn't appear until the
    server stopped. Found by running the real server, not the test client."""
    import os
    import select
    import socket
    import subprocess  # noqa: S404 - starts this project's own server
    import sys
    import time

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(  # noqa: S603 - fixed arguments, no shell
        [sys.executable, "-m", "onyx", "--vault", str(DEV_VAULT), "--port", str(port)],
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Read with a real timeout: if the lines are buffered, nothing arrives
        # and the test fails after 15 seconds instead of hanging.
        output = b""
        deadline = time.monotonic() + 15
        while output.count(b"\n") < 4:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([proc.stdout], [], [], remaining)
            if ready:
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk:
                    break
                output += chunk
        lines = output.decode().splitlines()
        assert len(lines) >= 4, "address, vault, cache and launch code arrive while the server runs"
        assert lines[0] == f"Onyx Sheiko: http://127.0.0.1:{port}"
        assert lines[2].startswith("Cache: ")
        assert lines[3].startswith("Launch code (one use, 10 minutes): ")
        assert proc.poll() is None, "server is still running"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
