"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def private_cache_dir(tmp_path, monkeypatch):
    """Every test (and any server process a test starts) uses its own cache
    folder, never the real ~/Library/Caches or ~/.cache."""
    cache = tmp_path / "onyx-cache"
    monkeypatch.setenv("ONYX_CACHE_DIR", str(cache))
    return cache
