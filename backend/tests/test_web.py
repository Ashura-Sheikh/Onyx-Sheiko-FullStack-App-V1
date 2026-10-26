"""Serving the built frontend under the CSP, with a fresh nonce per page
(threat model T6, decision A in issue #7)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from onyx.app import create_app
from onyx.auth import CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE
from onyx.config import load_settings
from onyx.security import CONTENT_SECURITY_POLICY, content_security_policy

DEV_VAULT = Path(__file__).resolve().parents[2] / "dev-vault"
BASE = "http://127.0.0.1:8731"
NONCE_IN_META = re.compile(r'<meta name="csp-nonce" content="([^"]+)" />')


@pytest.fixture
def client():
    return TestClient(create_app(load_settings(DEV_VAULT)), base_url=BASE)


def page_nonce(response) -> str:
    match = NONCE_IN_META.search(response.text)
    assert match, "page has a nonce meta tag"
    return match.group(1)


def test_page_gets_a_nonce_in_meta_and_csp(client):
    response = client.get("/")
    assert response.status_code == 200
    nonce = page_nonce(response)
    assert len(nonce) >= 22  # 128 random bits
    assert "__CSP_NONCE__" not in response.text
    csp = response.headers["content-security-policy"]
    assert csp == content_security_policy(nonce)
    assert f"style-src 'self' 'nonce-{nonce}'" in csp
    assert "script-src 'self';" in csp
    assert "unsafe" not in csp


def test_every_page_load_gets_a_new_nonce(client):
    nonces = {page_nonce(client.get("/")) for _ in range(5)}
    assert len(nonces) == 5


def test_page_is_never_cached(client):
    assert client.get("/").headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", ["/notes", "/tasks/board", "/index.html", "/docs"])
def test_app_routes_get_the_page(client, path):
    response = client.get(path)
    assert response.status_code == 200
    page_nonce(response)


def test_built_files_are_served_without_a_nonce(client):
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('app')"
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert client.get("/favicon.svg").text == "<svg/>"


def test_api_csp_never_has_a_nonce(client):
    client.get("/")  # a page load first must not leak its nonce into API responses
    response = client.get("/api/session", headers={CSRF_HEADER: CSRF_VALUE})
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


def test_unknown_api_path_is_not_the_page(client):
    app = client.app
    code = app.state.auth.launch_code
    session = client.post(
        "/api/session", json={"code": code}, headers={CSRF_HEADER: CSRF_VALUE}
    ).cookies[SESSION_COOKIE]
    client.cookies.clear()
    headers = {CSRF_HEADER: CSRF_VALUE, "Cookie": f"{SESSION_COOKIE}={session}"}
    for path in ("/api/no-such-route", "/api/notes/x.md"):
        response = client.get(path, headers=headers)
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize(
    "path",
    ["/..%2F..%2Fsecret.txt", "/assets/..%2F..%2Fsecret.txt", "/.env", "/assets/.hidden.js"],
)
def test_nothing_outside_dist_or_hidden_is_served(client, fake_frontend_dist, path):
    (fake_frontend_dist.parent / "secret.txt").write_text("SECRET OUTSIDE DIST")
    (fake_frontend_dist / ".env").write_text("HIDDEN")
    (fake_frontend_dist / "assets" / ".hidden.js").write_text("HIDDEN")
    response = client.get(path)
    assert "SECRET OUTSIDE DIST" not in response.text
    assert "HIDDEN" not in response.text


def test_symlink_out_of_dist_is_not_followed(client, fake_frontend_dist):
    (fake_frontend_dist.parent / "secret.txt").write_text("SECRET OUTSIDE DIST")
    (fake_frontend_dist / "assets" / "leak.js").symlink_to(fake_frontend_dist.parent / "secret.txt")
    assert "SECRET OUTSIDE DIST" not in client.get("/assets/leak.js").text


def test_unbuilt_frontend_says_so(fake_frontend_dist):
    for file in fake_frontend_dist.rglob("*"):
        if file.is_file():
            file.unlink()
    client = TestClient(create_app(load_settings(DEV_VAULT)), base_url=BASE)
    response = client.get("/")
    assert response.status_code == 503
    assert "npm run build" in response.text


def test_index_without_the_placeholder_is_refused(fake_frontend_dist):
    (fake_frontend_dist / "index.html").write_text("<html>no placeholder</html>")
    with pytest.raises(RuntimeError, match="placeholder"):
        create_app(load_settings(DEV_VAULT))


def test_symlink_present_at_startup_is_not_served(fake_frontend_dist):
    """The file list is made at startup; a link already there must be left out."""
    (fake_frontend_dist.parent / "secret.txt").write_text("SECRET OUTSIDE DIST")
    (fake_frontend_dist / "assets" / "leak.js").symlink_to(fake_frontend_dist.parent / "secret.txt")
    (fake_frontend_dist / ".env").write_text("HIDDEN")
    client = TestClient(create_app(load_settings(DEV_VAULT)), base_url=BASE)
    assert "SECRET OUTSIDE DIST" not in client.get("/assets/leak.js").text
    assert "HIDDEN" not in client.get("/.env").text
    assert client.get("/assets/app.js").text == "console.log('app')"


def test_files_are_served_by_exact_listed_path_only(client):
    # ("/assets/./app.js" isn't here: clients remove "./" before sending, so it
    # arrives as the real path.)
    for path in ("/assets//app.js", "/ASSETS/app.js", "/assets/app.js/"):
        assert client.get(path).text != "console.log('app')"
