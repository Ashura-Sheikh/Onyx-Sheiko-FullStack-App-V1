"""Checks on the repository itself, so a later change can't quietly weaken them.

Threat model T10 and T12: the SQLite cache (which holds note content) and
local secrets must never be committed.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def gitignore_lines() -> set[str]:
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    return {line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")}


def test_gitignore_keeps_cache_databases_out():
    lines = gitignore_lines()
    for pattern in ("*.db", "*.sqlite", "*.sqlite3", "*.db-wal", "*.db-shm"):
        assert pattern in lines, f".gitignore must ignore {pattern}"


def test_gitignore_keeps_env_files_out():
    lines = gitignore_lines()
    assert ".env" in lines
    assert ".env.*" in lines


def test_licence_is_mit():
    first_line = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "MIT License"


def test_security_policy_and_threat_model_exist():
    assert (REPO_ROOT / "SECURITY.md").is_file()
    assert (REPO_ROOT / "docs" / "threat-model.md").is_file()


def test_release_process_is_documented():
    text = (REPO_ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    assert "## Gate items" in text
    assert "fresh clone of the tag" in text


def test_backend_and_frontend_versions_match():
    """docs/releasing.md: the tag and both version fields must agree."""
    import json
    import tomllib

    backend = tomllib.loads((REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    frontend = json.loads((REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert backend["project"]["version"] == frontend["version"]
