"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def private_cache_dir(tmp_path, monkeypatch):
    """Every test (and any server process a test starts) uses its own cache
    folder, never the real ~/Library/Caches or ~/.cache."""
    cache = tmp_path / "onyx-cache"
    monkeypatch.setenv("ONYX_CACHE_DIR", str(cache))
    return cache


FAKE_INDEX = (
    "<!doctype html><html><head>"
    '<meta name="csp-nonce" content="__CSP_NONCE__" />'
    '<script type="module" src="/assets/app.js"></script>'
    '</head><body><div id="root"></div></body></html>'
)


@pytest.fixture(autouse=True)
def fake_frontend_dist(tmp_path, monkeypatch):
    """A tiny built frontend, so tests don't depend on whether
    frontend/dist happens to be built on this machine."""
    from onyx import config

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(FAKE_INDEX)
    (dist / "assets" / "app.js").write_text("console.log('app')")
    (dist / "favicon.svg").write_text("<svg/>")
    monkeypatch.setattr(config, "DEFAULT_FRONTEND_DIST", dist)
    return dist
