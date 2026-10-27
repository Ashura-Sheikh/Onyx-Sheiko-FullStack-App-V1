"""Home and palette data: frontmatter reading, task and note summaries, the
two endpoints. Read-only; T5 (every read goes through the path guard)."""

import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from onyx import frontmatter, summary
from onyx.__main__ import parse_args
from onyx.app import create_app
from onyx.config import ConfigError, load_settings
from onyx.vault import PathRejected, Vault
from tests.test_security_baseline import BASE, DEV_VAULT, OK, PORT, sign_in, with_session

TODAY = date(2031, 4, 16)


def write(root: Path, name: str, text: str | bytes) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def task(status="open", priority="normal", due="2031-04-16", extra="", history="") -> str:
    return (
        f"---\ntags:\n  - task\nstatus: {status}\npriority: {priority}\ndue: {due}\n{extra}---\n\n"
        f"# A task\n\n## Status History\n\n{history}"
    )


# --- Frontmatter -----------------------------------------------------------------


def test_frontmatter_and_body_are_split():
    meta, body = frontmatter.split("---\nstatus: open\n---\n# Title\n")
    assert meta == {"status": "open"}
    assert body == "# Title\n"


@pytest.mark.parametrize(
    "text",
    [
        "# No frontmatter\n",
        "---\nstatus: open\n# never closed\n",
        "---\n- a list\n- not a mapping\n---\n",
        "---\nstatus: [unclosed\n---\n",
        "---\njust a string\n---\n",
    ],
)
def test_missing_or_broken_frontmatter_gives_no_fields(text):
    assert frontmatter.split(text)[0] == {}


def test_frontmatter_never_builds_python_objects():
    text = "---\nx: !!python/object/apply:os.system ['echo hacked']\n---\n"
    assert frontmatter.split(text)[0] == {}


def test_deeply_nested_frontmatter_gives_no_fields():
    nested = "[" * 5000 + "]" * 5000
    assert frontmatter.split(f"---\nx: {nested}\n---\n")[0] == {}


def test_one_broken_note_does_not_break_home(tmp_path):
    write(tmp_path, "nested.md", "---\nx: " + "[" * 5000 + "]" * 5000 + "\n---\n# Nested\n")
    write(tmp_path, "t.md", task())
    result = summary.read_summary(Vault(tmp_path))
    assert [n.title for n in result.notes] == ["Nested"]
    assert len(result.tasks) == 1


def test_oversized_frontmatter_is_ignored():
    big = "x: " + "a" * frontmatter.MAX_FRONTMATTER_BYTES
    assert frontmatter.split(f"---\n{big}\n---\n")[0] == {}
    small = "x: " + "a" * (frontmatter.MAX_FRONTMATTER_BYTES - 10)
    assert frontmatter.split(f"---\n{small}\n---\n")[0] != {}


def test_byte_order_mark_and_windows_line_endings():
    meta, _ = frontmatter.split("﻿---\r\nstatus: done\r\n---\r\nbody")
    assert meta == {"status": "done"}


def test_section_stops_at_the_next_heading_of_the_same_level():
    body = "## Status History\n\n- one\n### detail\n- two\n## Context\n- three\n"
    assert frontmatter.section(body, "Status History") == ["", "- one", "### detail", "- two"]
    assert frontmatter.section(body, "Context") == ["- three", ""]
    assert frontmatter.section(body, "Missing") == []


def test_first_heading_is_level_one_only():
    assert frontmatter.first_heading("## Sub\n# Main\n") == "Main"
    assert frontmatter.first_heading("no heading") is None


# --- Tasks -------------------------------------------------------------------------


def test_a_task_is_a_note_tagged_task(tmp_path):
    write(tmp_path, "Tasks/List.md", task())
    write(tmp_path, "Tasks/String.md", task().replace("tags:\n  - task", "tags: task"))
    write(tmp_path, "Tasks/Untagged.md", task().replace("tags:\n  - task", "tags:\n  - idea"))
    result = summary.read_summary(Vault(tmp_path))
    assert sorted(t.path for t in result.tasks) == ["Tasks/List.md", "Tasks/String.md"]
    assert [n.path for n in result.notes] == ["Tasks/Untagged.md"]


def test_unknown_status_and_priority_are_dropped(tmp_path):
    write(tmp_path, "a.md", task(status="blocked", priority="urgent"))
    write(tmp_path, "b.md", task(status="[open]", priority="{x: 1}"))
    home = summary.home(summary.read_summary(Vault(tmp_path)), TODAY)
    assert home["counts"] == {"open": 0, "in-progress": 0, "in-review": 0, "done": 0}
    tasks = summary.read_summary(Vault(tmp_path)).tasks
    assert all(t.status is None and t.priority is None for t in tasks)


@pytest.mark.parametrize(
    ("due", "expected"),
    [
        ("2031-04-16", date(2031, 4, 16)),
        ('"2031-04-15"', date(2031, 4, 15)),
        ("2031-04-14T10:00:00Z", date(2031, 4, 14)),
        ("soon", None),
        ("[2031-04-16]", None),
        ("", None),
    ],
)
def test_due_dates(tmp_path, due, expected):
    write(tmp_path, "a.md", task(due=due))
    assert summary.read_summary(Vault(tmp_path)).tasks[0].due == expected


def test_due_lists_open_work_due_today_or_earlier(tmp_path):
    write(tmp_path, "today.md", task(due="2031-04-16"))
    write(tmp_path, "late.md", task(due="2031-04-01", status="in-review"))
    write(tmp_path, "later.md", task(due="2031-04-17"))
    write(tmp_path, "done.md", task(due="2031-04-01", status="done"))
    write(tmp_path, "no-due.md", task(due='""'))
    home = summary.home(summary.read_summary(Vault(tmp_path)), TODAY)
    assert [t["path"] for t in home["due"]] == ["late.md", "today.md"]
    assert [t["path"] for t in home["waiting"]] == ["late.md"]


def test_title_comes_from_frontmatter_then_heading_then_file_name(tmp_path):
    write(tmp_path, "a.md", "---\ntitle: From frontmatter\n---\n# From heading\n")
    write(tmp_path, "b.md", "# From heading\n")
    write(tmp_path, "File name.md", "no heading\n")
    write(tmp_path, "long.md", "# " + "x" * 1000 + "\n")
    titles = {n.path: n.title for n in summary.read_summary(Vault(tmp_path)).notes}
    assert titles["a.md"] == "From frontmatter"
    assert titles["b.md"] == "From heading"
    assert titles["File name.md"] == "File name"
    assert len(titles["long.md"]) == summary.MAX_TITLE_CHARS


# --- History -------------------------------------------------------------------------


def test_history_lines_in_sheiko_format(tmp_path):
    lines = (
        "- 2031-04-14T18:00:00+00:00 — open → in-progress\n"
        "- 2031-04-14T20:00:00Z — in-review → done (signed off by owner)\n"
        "- 2031-04-14T21:00:00 — done → open\n"  # no offset: taken as UTC
        "- not a time — open → done\n"
        "- 2031-04-14T22:00:00Z — open → blocked\n"
        "- 2031-04-14T23:00:00Z open → done\n"
        "A hand-written sentence.\n"
    )
    write(tmp_path, "a.md", task(history=lines))
    history = summary.home(summary.read_summary(Vault(tmp_path)), TODAY)["history"]
    assert [(h["at"], h["from"], h["to"], h["remark"]) for h in history] == [
        ("2031-04-14T21:00:00+00:00", "done", "open", None),
        ("2031-04-14T20:00:00+00:00", "in-review", "done", "signed off by owner"),
        ("2031-04-14T18:00:00+00:00", "open", "in-progress", None),
    ]
    assert history[0]["title"] == "A task"
    assert history[0]["path"] == "a.md"


def test_history_outside_its_section_is_ignored(tmp_path):
    text = task(history="") + "\n## Notes\n\n- 2031-04-14T18:00:00Z — open → done\n"
    write(tmp_path, "a.md", text)
    assert summary.read_summary(Vault(tmp_path)).history == []


def test_history_is_newest_first_across_tasks_and_limited(tmp_path):
    for n in range(15):
        line = f"- 2031-04-{n + 1:02d}T10:00:00Z — open → in-progress\n"
        write(tmp_path, f"t{n:02d}.md", task(history=line))
    history = summary.home(summary.read_summary(Vault(tmp_path)), TODAY)["history"]
    assert len(history) == summary.HISTORY_ENTRIES == 10
    assert [h["path"] for h in history] == [f"t{n:02d}.md" for n in range(14, 4, -1)]


def test_notes_only_have_no_history(tmp_path):
    write(
        tmp_path, "note.md", "# Note\n\n## Status History\n\n- 2031-04-14T18:00:00Z — open → done\n"
    )
    assert summary.read_summary(Vault(tmp_path)).history == []


# --- Notes -------------------------------------------------------------------------


def test_recent_notes_use_date_modified_then_file_time(tmp_path):
    write(tmp_path, "Projects/old.md", "---\ndateModified: 2031-04-01T10:00:00Z\n---\n# Old\n")
    write(tmp_path, "new.md", "---\ndateModified: 2031-04-15T10:00:00Z\n---\n# New\n")
    write(tmp_path, "plain.md", "# Plain\n")
    stamp = datetime(2031, 4, 10, tzinfo=UTC).timestamp()
    os.utime(tmp_path / "plain.md", (stamp, stamp))
    recent = summary.home(summary.read_summary(Vault(tmp_path)), TODAY)["recent_notes"]
    assert [(n["path"], n["folder"]) for n in recent] == [
        ("new.md", ""),
        ("plain.md", ""),
        ("Projects/old.md", "Projects"),
    ]
    assert recent[1]["updated"] == "2031-04-10T00:00:00+00:00"


def test_recent_notes_are_limited_to_five(tmp_path):
    for n in range(8):
        write(tmp_path, f"n{n}.md", f"---\ndateModified: 2031-04-0{n + 1}T00:00:00Z\n---\n")
    recent = summary.home(summary.read_summary(Vault(tmp_path)), TODAY)["recent_notes"]
    assert [n["path"] for n in recent] == ["n7.md", "n6.md", "n5.md", "n4.md", "n3.md"]


def test_a_file_that_isnt_utf8_is_left_out(tmp_path):
    write(tmp_path, "bad.md", b"\xff\xfe not utf-8")
    write(tmp_path, "good.md", "# Good\n")
    result = summary.read_summary(Vault(tmp_path))
    assert [n.path for n in result.notes] == ["good.md"]


def test_modified_goes_through_the_path_guard(tmp_path):
    write(tmp_path, "a.md", "x")
    with pytest.raises(PathRejected):
        Vault(tmp_path).modified("../a.md")
    with pytest.raises(PathRejected):
        Vault(tmp_path).modified(".hidden.md")


def test_items_list_every_note_and_task_by_title(tmp_path):
    write(tmp_path, "b.md", "# Beta\n")
    write(tmp_path, "t.md", task())
    write(tmp_path, "a.md", "# alpha\n")
    assert summary.items(summary.read_summary(Vault(tmp_path))) == [
        {"kind": "task", "path": "t.md", "title": "A task"},
        {"kind": "note", "path": "a.md", "title": "alpha"},
        {"kind": "note", "path": "b.md", "title": "Beta"},
    ]


# --- The made-up dev-vault ------------------------------------------------------------


def test_dev_vault_home_on_16_april_2031():
    home = summary.home(summary.read_summary(Vault(DEV_VAULT)), TODAY)
    assert home["today"] == "2031-04-16"
    assert home["counts"] == {"open": 4, "in-progress": 3, "in-review": 2, "done": 3}
    assert [t["title"] for t in home["due"]] == [
        "Pick a layout after design review",
        "Plan weekly sync agenda",
        "Review cache rebuild design",
    ]
    assert [t["title"] for t in home["waiting"]] == [
        "Review cache rebuild design",
        "Update release checklist",
    ]
    assert len(home["recent_notes"]) == 5
    assert home["history"][0]["title"] == "Prepare Harbor demo"


# --- Endpoints and settings ------------------------------------------------------------


@pytest.fixture
def app():
    return create_app(load_settings(DEV_VAULT, PORT, "2031-04-16"))


@pytest.mark.parametrize("path", ["/api/home", "/api/items"])
def test_endpoints_need_a_session(app, path):
    client = TestClient(app, base_url=BASE)
    assert client.get(path, headers=OK).status_code == 401
    session = sign_in(client, app)
    assert client.get(path, headers=with_session(session)).status_code == 200


def test_home_endpoint_uses_the_fixed_today(app):
    client = TestClient(app, base_url=BASE)
    session = sign_in(client, app)
    body = client.get("/api/home", headers=with_session(session)).json()
    assert body["today"] == "2031-04-16"
    assert len(body["due"]) == 3


def test_items_endpoint(app):
    client = TestClient(app, base_url=BASE)
    session = sign_in(client, app)
    found = client.get("/api/items", headers=with_session(session)).json()["items"]
    assert len(found) == 28
    assert {
        "kind": "task",
        "path": "Tasks/Tidy Reference folder.md",
        "title": "Tidy Reference folder",
    } in found


def test_today_defaults_to_the_computers_date():
    app = create_app(load_settings(DEV_VAULT, PORT))
    client = TestClient(app, base_url=BASE)
    session = sign_in(client, app)
    body = client.get("/api/home", headers=with_session(session)).json()
    assert body["today"] == date.today().isoformat()


def test_today_option():
    assert parse_args(["--vault", str(DEV_VAULT), "--today", "2031-04-16"]).today == TODAY
    assert parse_args(["--vault", str(DEV_VAULT)]).today is None
    with pytest.raises(ConfigError, match="--today"):
        parse_args(["--vault", str(DEV_VAULT), "--today", "16/04/2031"])


# --- One note for the focus view -------------------------------------------------------


def test_note_detail_for_a_note(tmp_path):
    write(
        tmp_path,
        "Projects/Atlas.md",
        "---\ntags: [atlas, design]\ndateModified: 2031-04-15T10:00:00Z\n---\n"
        "\n# Atlas\n\nBody text.\n",
    )
    detail = summary.note_detail(Vault(tmp_path), "Projects/Atlas.md")
    assert detail == {
        "path": "Projects/Atlas.md",
        "title": "Atlas",
        "folder": "Projects",
        "kind": "note",
        "updated": "2031-04-15T10:00:00+00:00",
        "tags": ["atlas", "design"],
        "body": "Body text.",
        "task": None,
    }


def test_note_detail_for_a_task(tmp_path):
    extra = (
        'projects:\n  - "[[Atlas architecture]]"\n  - "[[Harbor|Harbor project]]"\n  - Plain\n'
        "dateCreated: 2031-04-13T11:00:00Z\ncompletedDate: 2031-04-13T12:30:00Z\n"
        "closedBy: owner\ntimeToCloseMinutes: 90\n"
    )
    history = (
        "- 2031-04-13T11:00:00Z — created → open\n"
        "- 2031-04-13T12:30:00Z — open → done (signed off)\n"
    )
    text = task(status="done", priority="high", extra=extra, history=history)
    text = text.replace("# A task\n\n", "# A task\n\nWhat this task is about.\n\n")
    text += "\n## Context\n\n- 2031-04-13T11:05:00Z — owner: started\n\n## Notes\n\nKept.\n"
    write(tmp_path, "t.md", text)
    detail = summary.note_detail(Vault(tmp_path), "t.md")
    assert detail["kind"] == "task"
    assert detail["tags"] == []  # "task" itself isn't shown
    assert detail["body"] == "What this task is about.\n\n## Notes\n\nKept."
    assert detail["task"] == {
        "status": "done",
        "priority": "high",
        "due": "2031-04-16",
        "projects": ["Atlas architecture", "Harbor project", "Plain"],
        "created": "2031-04-13T11:00:00+00:00",
        "completed": "2031-04-13T12:30:00+00:00",
        "closed_by": "owner",
        "time_to_close_minutes": 90,
        "history": [
            {"at": "2031-04-13T11:00:00+00:00", "from": "created", "to": "open", "remark": None},
            {
                "at": "2031-04-13T12:30:00+00:00",
                "from": "open",
                "to": "done",
                "remark": "signed off",
            },
        ],
    }


@pytest.mark.parametrize("minutes", ['"90"', "-5", "true", "1.5", "[1]"])
def test_bad_time_to_close_is_dropped(tmp_path, minutes):
    write(tmp_path, "t.md", task(extra=f"timeToCloseMinutes: {minutes}\n"))
    assert summary.note_detail(Vault(tmp_path), "t.md")["task"]["time_to_close_minutes"] is None


def test_tags_must_be_text_and_are_limited(tmp_path):
    tags = "\n".join(f"  - t{n}" for n in range(80))
    write(tmp_path, "a.md", f"---\ntags:\n{tags}\n  - 5\n  - [nested]\n---\n")
    detail = summary.note_detail(Vault(tmp_path), "a.md")
    assert len(detail["tags"]) == summary.MAX_TAGS
    assert all(isinstance(t, str) for t in detail["tags"])


def test_heading_is_kept_when_it_is_not_the_title(tmp_path):
    write(tmp_path, "a.md", "---\ntitle: Other\n---\n# Heading\n\nText\n")
    assert summary.note_detail(Vault(tmp_path), "a.md")["body"] == "# Heading\n\nText"


def test_hidden_sections_at_any_level_are_removed():
    body = "Intro\n### Status History\n- x\n#### deeper\n- y\n### Next\nKept\n"
    assert frontmatter.without_sections(body, ("Status History",)) == "Intro\n### Next\nKept\n"


@pytest.mark.parametrize(
    "requested",
    [
        "../outside.md",
        "/etc/passwd",
        ".hidden.md",
        "Missing.md",
        "folder",
        "a.md/../a.md",
        "A.MD",
        "a.md\x00",
        "",
    ],
)
def test_only_listed_notes_can_be_opened(tmp_path, requested):
    (tmp_path / "vault").mkdir()
    write(tmp_path / "vault", "a.md", "# A\n")
    write(tmp_path / "vault", ".hidden.md", "# Hidden\n")
    (tmp_path / "vault" / "folder").mkdir()
    write(tmp_path, "outside.md", "# Outside\n")
    assert summary.note_detail(Vault(tmp_path / "vault"), requested) is None


def test_a_symlink_out_of_the_vault_cannot_be_opened(tmp_path):
    (tmp_path / "vault").mkdir()
    write(tmp_path, "secret.md", "# Secret\n")
    (tmp_path / "vault" / "link.md").symlink_to(tmp_path / "secret.md")
    assert summary.note_detail(Vault(tmp_path / "vault"), "link.md") is None


def test_only_what_home_lists_can_be_opened(tmp_path):
    """The path guard allows a symlinked folder that stays inside the vault,
    but the listing doesn't follow symlinked folders, so neither does the
    focus view: what can be opened is exactly what Home and ⌘K can list."""
    (tmp_path / "vault" / "real").mkdir(parents=True)
    write(tmp_path / "vault", "real/a.md", "# A\n")
    (tmp_path / "vault" / "alias").symlink_to(tmp_path / "vault" / "real")
    vault = Vault(tmp_path / "vault")
    assert vault.read("alias/a.md").text == "# A\n"  # the guard alone would allow it
    assert summary.note_detail(vault, "alias/a.md") is None
    assert summary.note_detail(vault, "real/a.md")["title"] == "A"


def test_note_endpoint(app):
    client = TestClient(app, base_url=BASE)
    url = "/api/note?path=Projects/Atlas%20kickoff.md"
    assert client.get(url, headers=OK).status_code == 401
    session = sign_in(client, app)
    body = client.get(url, headers=with_session(session)).json()
    assert body["title"] == "Atlas kickoff"
    assert body["kind"] == "note"
    missing = client.get("/api/note?path=..%2FREADME.md", headers=with_session(session))
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Note not found"}
    assert client.get("/api/note", headers=with_session(session)).status_code == 422
    long = "a" * 513 + ".md"
    assert client.get(f"/api/note?path={long}", headers=with_session(session)).status_code == 422


def test_dev_vault_task_detail(app):
    client = TestClient(app, base_url=BASE)
    session = sign_in(client, app)
    url = "/api/note?path=Tasks/Review%20cache%20rebuild%20design.md"
    body = client.get(url, headers=with_session(session)).json()
    assert body["task"]["status"] == "in-review"
    assert body["task"]["projects"] == ["Atlas architecture"]
    assert len(body["task"]["history"]) == 3
