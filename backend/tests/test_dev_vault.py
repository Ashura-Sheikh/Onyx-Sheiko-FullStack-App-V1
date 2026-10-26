"""Guards on dev-vault/, the made-up vault used for development and tests.

Threat model T11: this repository is public, so nothing real may ever be in it.
Every file must be marked as synthetic, and nothing that looks like real
personal data (absolute paths, email addresses, outside URLs) is allowed.
The task files are also checked for the stage rules the app will enforce.
"""

import re
from pathlib import Path

import pytest

VAULT = Path(__file__).resolve().parents[2] / "dev-vault"
STAGES = ["open", "in-progress", "in-review", "done"]

ABSOLUTE_PATH = re.compile(r"(/Users/|/home/|/root/|[A-Za-z]:\\\\|~/)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL = re.compile(r"https?://([^/\s)>\"']+)", re.IGNORECASE)
HISTORY_LINE = re.compile(r"^- (\S+) — (created|[a-z-]+) → ([a-z-]+)( \(signed off by owner\))?$")


def all_files() -> list[Path]:
    return sorted(p for p in VAULT.rglob("*") if p.is_file())


def frontmatter(text: str) -> dict[str, str]:
    """Top-level `key: value` pairs from a simple frontmatter block."""
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fields = {}
    for line in text[4:end].splitlines():
        if line and not line.startswith(" ") and ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def test_vault_exists_with_enough_content():
    files = all_files()
    tasks = list((VAULT / "Tasks").glob("*.md"))
    assert 10 <= len(files) - len(tasks) <= 20, "10 to 20 notes"
    assert 10 <= len(tasks) <= 15, "10 to 15 tasks"


def test_only_markdown_files():
    others = [p.relative_to(VAULT) for p in all_files() if p.suffix != ".md"]
    assert others == []


def test_no_obsidian_settings_folder():
    assert not (VAULT / ".obsidian").exists()


@pytest.mark.parametrize("path", all_files(), ids=lambda p: str(p.relative_to(VAULT)))
def test_file_is_marked_synthetic(path):
    assert frontmatter(path.read_text(encoding="utf-8")).get("synthetic") == "true"


@pytest.mark.parametrize("path", all_files(), ids=lambda p: str(p.relative_to(VAULT)))
def test_file_has_no_real_looking_data(path):
    text = path.read_text(encoding="utf-8")
    assert not ABSOLUTE_PATH.search(text), "absolute path"
    assert not EMAIL.search(text), "email address"
    for host in URL.findall(text):
        host = host.lower()
        assert host == "example.com" or host.endswith(".example.com"), f"URL to {host}"


@pytest.mark.parametrize("path", sorted((VAULT / "Tasks").glob("*.md")), ids=lambda p: p.name)
def test_task_follows_the_stage_rules(path):
    text = path.read_text(encoding="utf-8")
    fields = frontmatter(text)
    assert fields.get("status") in STAGES
    assert "## Status History" in text

    history = text.split("## Status History", 1)[1].strip().splitlines()
    moves = [HISTORY_LINE.match(line) for line in history]
    assert all(moves), "every history line has the expected format"
    assert moves[0].group(2) == "created" and moves[0].group(3) == "open"

    # One stage at a time, never skipping.
    for previous, move in zip(moves, moves[1:], strict=False):
        assert move.group(2) == previous.group(3)
        assert STAGES.index(move.group(3)) == STAGES.index(move.group(2)) + 1

    assert moves[-1].group(3) == fields["status"], "last move matches the status"

    if fields["status"] == "done":
        assert moves[-1].group(4), "done needs a sign-off"
        assert fields.get("completedDate") == moves[-1].group(1)
    else:
        assert "completedDate" not in fields
