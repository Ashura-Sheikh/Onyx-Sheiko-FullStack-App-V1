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
