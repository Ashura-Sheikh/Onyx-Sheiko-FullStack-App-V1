"""Creating tasks and sub-tasks, renaming and deleting tasks (#9 part (c)).

Every write goes to a copy of dev-vault/ in a temporary folder (Sheikh's
decision 5 on #8). "Now" is fixed, so times are exact."""

import hashlib
import shutil
from datetime import UTC, datetime

import pytest
import yaml
from fastapi.testclient import TestClient

from onyx import app as app_module
from onyx import frontmatter, lifecycle, task_writes
from onyx.app import create_app
from onyx.config import load_settings
from onyx.vault import PathRejected, Vault
from tests.test_security_baseline import BASE, DEV_VAULT, PORT, sign_in, with_session

NOW = datetime(2031, 4, 16, 12, 0, 0, tzinfo=UTC)
T = lifecycle.local_iso(NOW)
PARENT = "Tasks/Launch Atlas beta.md"  # in progress, with 3 sub-tasks
CHILD = "Tasks/Write beta invite text.md"  # a sub-task of PARENT
DONE = "Tasks/Write Atlas architecture note.md"  # done, no parent
PLAIN = "Tasks/Tidy Reference folder.md"  # open, no parent, no sub-tasks
NOTE = "Projects/Atlas kickoff.md"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(app_module, "now", lambda: NOW)


@pytest.fixture
def vault(tmp_path):
    copy = tmp_path / "vault"
    shutil.copytree(DEV_VAULT, copy, symlinks=True)
    return copy


def make_client(vault_dir, allow_writes=True):
    app = create_app(load_settings(vault_dir, PORT, allow_writes=allow_writes, identity="sheikh"))
    client = TestClient(app, base_url=BASE)
    return client, with_session(sign_in(client, app))


@pytest.fixture
def api(vault):
    return make_client(vault)


def version(vault, path):
    return hashlib.sha256((vault / path).read_bytes()).hexdigest()


def board(client, headers):
    return {t["path"]: t for t in client.get("/api/tasks", headers=headers).json()["tasks"]}


def files(vault):
    return sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*") if p.is_file())


def post(client, headers, url, body):
    return client.post(url, json=body, headers=headers)


def with_checklist(vault, path, lines):
    """Add a checklist to a task's body (as if edited in Obsidian)."""
    text = (vault / path).read_text(encoding="utf-8")
    head, body = frontmatter.split_raw(text)
    (vault / path).write_text(
        head + body.replace("\n## Status History", lines + "\n## Status History")
    )


# --- Create ----------------------------------------------------------------------------------


def test_create_makes_exactly_this_file(api, vault):
    client, headers = api
    response = post(
        client,
        headers,
        "/api/tasks",
        {"title": "Book venue", "priority": "high", "due": "2031-05-02"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["path"] == "Tasks/Book venue.md"
    assert response.json()["version"] == version(vault, "Tasks/Book venue.md")
    assert (vault / "Tasks/Book venue.md").read_text(encoding="utf-8") == (
        "---\ntags:\n  - task\nstatus: open\npriority: high\ndue: 2031-05-02\n"
        f"dateCreated: {T}\ndateModified: {T}\n---\n\n## Status History\n\n"
        f"- {T} — created → open\n"
    )
    card = board(client, headers)["Tasks/Book venue.md"]
    assert (card["status"], card["priority"], card["due"]) == ("open", "high", "2031-05-02")
    assert card["parent"] is None and card["subtasks"] is None


def test_a_new_task_is_valid_yaml_and_moves_like_any_other(api, vault):
    client, headers = api
    path = post(client, headers, "/api/tasks", {"title": "Book venue"}).json()["path"]
    meta = yaml.safe_load((vault / path).read_text(encoding="utf-8").split("---")[1])
    assert meta["tags"] == ["task"] and meta["status"] == "open"
    assert "priority" not in meta and "due" not in meta and "projects" not in meta
    moved = post(
        client,
        headers,
        "/api/task/move",
        {"path": path, "to": "in-progress", "version": version(vault, path)},
    )
    assert moved.status_code == 200, moved.text


def test_create_a_subtask_links_and_tags_it(api, vault):
    client, headers = api
    before = board(client, headers)[PARENT]["subtasks"]
    response = post(client, headers, "/api/tasks", {"title": "Send invites", "parent": PARENT})
    assert response.status_code == 201, response.text
    meta, _ = frontmatter.split((vault / "Tasks/Send invites.md").read_text(encoding="utf-8"))
    assert meta["tags"] == ["task", "subtask"]
    assert meta["projects"] == ["[[Launch Atlas beta]]"]
    after = board(client, headers)
    assert after["Tasks/Send invites.md"]["parent"]["path"] == PARENT
    assert after[PARENT]["subtasks"] == {"done": before["done"], "total": before["total"] + 1}


def test_a_new_subtask_blocks_closing_its_parent(api, vault):
    """Decision 6 (part (b)) now covers sub-tasks made here."""
    client, headers = api
    post(client, headers, "/api/tasks", {"title": "Book venue", "parent": PLAIN})
    for to in ["in-progress", "in-review"]:
        post(
            client,
            headers,
            "/api/task/move",
            {"path": PLAIN, "to": to, "version": version(vault, PLAIN)},
        )
    done = post(
        client,
        headers,
        "/api/task/move",
        {"path": PLAIN, "to": "done", "version": version(vault, PLAIN)},
    )
    assert done.status_code == 400
    assert done.json()["detail"] == "This task has sub-tasks that aren't done yet."


@pytest.mark.parametrize(
    ("parent", "code"),
    [
        (NOTE, "parent-not-task"),
        (CHILD, "parent-is-subtask"),
        (DONE, "parent-done"),
    ],
)
def test_create_refuses_a_parent_that_cant_take_subtasks(api, vault, parent, code):
    client, headers = api
    before = files(vault)
    response = post(client, headers, "/api/tasks", {"title": "Book venue", "parent": parent})
    assert response.status_code == 400
    assert response.json() == {"detail": task_writes.TASK_REFUSALS[code], "line": None}
    assert files(vault) == before


def test_create_refuses_a_missing_parent(api, vault):
    client, headers = api
    response = post(
        client, headers, "/api/tasks", {"title": "Book venue", "parent": "Tasks/Nope.md"}
    )
    assert response.status_code == 404
    assert not (vault / "Tasks/Book venue.md").exists()


def test_create_never_replaces_a_task(api, vault):
    client, headers = api
    before = (vault / PLAIN).read_bytes()
    response = post(client, headers, "/api/tasks", {"title": "Tidy Reference folder"})
    assert response.status_code == 409 and response.json()["reason"] == "exists"
    assert (vault / PLAIN).read_bytes() == before


def test_create_never_replaces_a_task_differing_only_in_capitals(api, vault):
    client, headers = api
    before = files(vault)
    response = post(client, headers, "/api/tasks", {"title": "tidy reference FOLDER"})
    # On a disk that ignores case (the Mac default) the name is taken; on one
    # that doesn't, it's a different file. Either way nothing is replaced.
    if response.status_code == 201:
        assert len(files(vault)) == len(before) + 1
    else:
        assert response.status_code == 409 and files(vault) == before
    assert (vault / PLAIN).read_text(encoding="utf-8").startswith("---\nsynthetic: true")


@pytest.mark.parametrize("title", ["a/b", "../escape", ".hidden", "x[[y]]", "a:b", "  "])
def test_create_refuses_names_that_arent_allowed(api, vault, title):
    client, headers = api
    before = files(vault)
    response = post(client, headers, "/api/tasks", {"title": title})
    assert response.status_code == 400
    assert files(vault) == before


def test_create_refuses_fields_it_doesnt_know(api):
    client, headers = api
    response = post(client, headers, "/api/tasks", {"title": "x", "status": "done"})
    assert response.status_code == 422
    response = post(client, headers, "/api/tasks", {"title": "x", "priority": "urgent"})
    assert response.status_code == 422
    response = post(client, headers, "/api/tasks", {"title": "x", "due": "soon"})
    assert response.status_code == 422


def test_create_makes_the_tasks_folder_if_missing(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    note = task_writes.create_task(Vault(root), "First", NOW)
    assert note.path == "Tasks/First.md" and (root / "Tasks").is_dir()


def test_create_refuses_a_tasks_folder_that_is_a_link(tmp_path):
    root, elsewhere = tmp_path / "vault", tmp_path / "elsewhere"
    root.mkdir()
    elsewhere.mkdir()
    (root / "Tasks").symlink_to(elsewhere)
    with pytest.raises(PathRejected) as refused:
        task_writes.create_task(Vault(root), "First", NOW)
    assert refused.value.code == "folder-link"
    assert list(elsewhere.iterdir()) == []


def test_parent_link_uses_the_folder_when_the_name_alone_opens_something_else():
    paths = ["Projects/Plan.md", "Tasks/Plan.md", "Tasks/Child.md"]
    # From Tasks/, [[Plan]] opens Tasks/Plan.md, so a parent in Projects/ needs its folder.
    assert (
        task_writes._parent_link("Projects/Plan.md", "Tasks/Child.md", paths) == "[[Projects/Plan]]"
    )
    assert task_writes._parent_link("Tasks/Plan.md", "Tasks/Child.md", paths) == "[[Plan]]"


def test_task_text_refuses_if_the_frontmatter_doesnt_read_back(monkeypatch):
    monkeypatch.setattr(
        task_writes, "_quoted", lambda text: text
    )  # unquoted [[...]] is a YAML list
    with pytest.raises(task_writes.TaskRefused) as refused:
        task_writes.task_text(NOW, parent_link="[[Plan]]")
    assert refused.value.code == "build-failed"


# --- Make sub-tasks ---------------------------------------------------------------------------

CHECKLIST = """
- [ ] Draft the agenda
- [x] Already ticked
  * [ ] Book the room
```
- [ ] Inside a code block
```
"""


def make(client, headers, vault, path):
    return post(
        client, headers, "/api/task/subtasks", {"path": path, "version": version(vault, path)}
    )


def test_make_subtasks_one_per_unticked_line_and_parent_unchanged(api, vault):
    client, headers = api
    with_checklist(vault, PLAIN, CHECKLIST)
    before = (vault / PLAIN).read_bytes()
    response = make(client, headers, vault, PLAIN)
    assert response.status_code == 201, response.text
    assert response.json() == {
        "created": ["Tasks/Draft the agenda.md", "Tasks/Book the room.md"],
        "skipped": [],
    }
    assert (vault / PLAIN).read_bytes() == before
    cards = board(client, headers)
    assert cards[PLAIN]["subtasks"] == {"done": 0, "total": 2}
    assert cards["Tasks/Book the room.md"]["parent"]["path"] == PLAIN
    assert (vault / "Tasks/Book the room.md").read_text(encoding="utf-8") == (
        task_writes.task_text(NOW, parent_link="[[Tidy Reference folder]]")
    )


def test_make_subtasks_again_skips_the_ones_already_made(api, vault):
    client, headers = api
    with_checklist(vault, PLAIN, CHECKLIST)
    make(client, headers, vault, PLAIN)
    with_checklist(vault, PLAIN, "- [ ] Send the notes\n")
    response = make(client, headers, vault, PLAIN)
    assert response.status_code == 201, response.text
    assert response.json() == {
        "created": ["Tasks/Send the notes.md"],
        "skipped": ["Tasks/Draft the agenda.md", "Tasks/Book the room.md"],
    }
    again = make(client, headers, vault, PLAIN)
    assert again.status_code == 400
    assert again.json()["detail"] == task_writes.TASK_REFUSALS["all-exist"]


@pytest.mark.parametrize(
    ("lines", "code", "line"),
    [
        ("- [ ] Fine\n- [ ] See [[Atlas kickoff]]\n", "item-name", 2),
        ("- [ ] Same name\n- [ ] same NAME\n", "item-duplicate", 2),
        ("- [ ] Fine\n- [ ] Add glossary entries\n", "item-taken", 2),
        # Another parent's sub-task: taken, not skipped.
        ("- [ ] Write beta invite text\n", "item-taken", 1),
        ("- [ ] .dotted\n", "item-name", 1),
    ],
)
def test_make_subtasks_checks_every_line_before_writing_anything(api, vault, lines, code, line):
    client, headers = api
    with_checklist(vault, PLAIN, lines)
    before = files(vault)
    response = make(client, headers, vault, PLAIN)
    assert response.status_code == 400
    assert response.json() == {"detail": task_writes.TASK_REFUSALS[code], "line": line}
    assert files(vault) == before


def test_make_subtasks_needs_a_checklist(api, vault):
    client, headers = api
    response = make(client, headers, vault, PLAIN)
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS["no-checklist"]


def test_make_subtasks_has_a_limit(api, vault):
    client, headers = api
    lines = "".join(f"- [ ] Item {n}\n" for n in range(task_writes.MAX_SUBTASKS + 1))
    with_checklist(vault, PLAIN, lines)
    before = files(vault)
    response = make(client, headers, vault, PLAIN)
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS["too-many"]
    assert files(vault) == before


def test_make_subtasks_up_to_the_limit_is_allowed(api, vault):
    client, headers = api
    lines = "".join(f"- [ ] Item {n}\n" for n in range(task_writes.MAX_SUBTASKS))
    with_checklist(vault, PLAIN, lines)
    response = make(client, headers, vault, PLAIN)
    assert response.status_code == 201 and len(response.json()["created"]) == 50


@pytest.mark.parametrize(("path", "code"), [(CHILD, "parent-is-subtask"), (DONE, "parent-done")])
def test_make_subtasks_refuses_a_subtask_or_a_done_task(api, vault, path, code):
    client, headers = api
    with_checklist(vault, path, "- [ ] Something\n")
    before = files(vault)
    response = make(client, headers, vault, path)
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS[code]
    assert files(vault) == before


def test_make_subtasks_refuses_a_note(api, vault):
    client, headers = api
    response = make(client, headers, vault, NOTE)
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS["not-a-task"]


def test_make_subtasks_refuses_if_the_task_changed_since_it_was_opened(api, vault):
    client, headers = api
    with_checklist(vault, PLAIN, "- [ ] Something\n")
    old = version(vault, PLAIN)
    with_checklist(vault, PLAIN, "- [ ] Something else\n")
    before = files(vault)
    response = post(client, headers, "/api/task/subtasks", {"path": PLAIN, "version": old})
    assert response.status_code == 409
    assert files(vault) == before


def test_make_subtasks_reports_what_was_made_if_a_file_appears_midway(api, vault, monkeypatch):
    client, headers = api
    with_checklist(vault, PLAIN, "- [ ] One\n- [ ] Two\n")
    real = Vault.create

    def racing(self, name, text):
        if name == "Tasks/Two.md":
            (vault / name).write_text("made by someone else")
        return real(self, name, text)

    monkeypatch.setattr(Vault, "create", racing)
    response = make(client, headers, vault, PLAIN)
    assert response.status_code == 409
    assert response.json()["created"] == ["Tasks/One.md"]
    assert (vault / "Tasks/Two.md").read_text() == "made by someone else"


def test_unticked_lines():
    assert task_writes.unticked_lines(CHECKLIST) == ["Draft the agenda", "Book the room"]
    assert task_writes.unticked_lines("- [ ]\n- [ ]   \n-[ ] x\n- [ ]x\n") == []


# --- Rename and delete -------------------------------------------------------------------------


def test_rename_a_task(api, vault):
    client, headers = api
    response = post(
        client,
        headers,
        "/api/task/rename",
        {"path": PLAIN, "name": "Tidy Reference", "version": version(vault, PLAIN)},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"path": "Tasks/Tidy Reference.md"}
    assert not (vault / PLAIN).exists()
    assert "Tasks/Tidy Reference.md" in board(client, headers)


def test_rename_a_subtask_keeps_its_parent(api, vault):
    client, headers = api
    response = post(
        client,
        headers,
        "/api/task/rename",
        {"path": CHILD, "name": "Write invite", "version": version(vault, CHILD)},
    )
    assert response.status_code == 200, response.text
    assert board(client, headers)["Tasks/Write invite.md"]["parent"]["path"] == PARENT


def test_rename_refuses_a_parent_with_subtasks(api, vault):
    """Decision 5a."""
    client, headers = api
    before = files(vault)
    response = post(
        client,
        headers,
        "/api/task/rename",
        {"path": PARENT, "name": "Launch", "version": version(vault, PARENT)},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS["rename-parent"]
    assert files(vault) == before


def test_rename_refuses_a_note_and_a_stale_version_and_a_taken_name(api, vault):
    client, headers = api
    note = post(
        client,
        headers,
        "/api/task/rename",
        {"path": NOTE, "name": "x", "version": version(vault, NOTE)},
    )
    assert note.status_code == 400
    assert note.json()["detail"] == task_writes.TASK_REFUSALS["not-a-task"]
    stale = post(
        client, headers, "/api/task/rename", {"path": PLAIN, "name": "x", "version": "0" * 64}
    )
    assert stale.status_code == 409 and stale.json()["reason"] == "changed"
    taken = post(
        client,
        headers,
        "/api/task/rename",
        {"path": PLAIN, "name": "Add glossary entries", "version": version(vault, PLAIN)},
    )
    assert taken.status_code == 409 and taken.json()["reason"] == "exists"
    assert (vault / PLAIN).exists()


def test_delete_a_subtask_moves_it_to_trash(api, vault):
    client, headers = api
    before = board(client, headers)[PARENT]["subtasks"]["total"]
    response = post(
        client, headers, "/api/task/delete", {"path": CHILD, "version": version(vault, CHILD)}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"trashed_to": ".trash/" + CHILD}
    assert (vault / ".trash" / CHILD).exists() and not (vault / CHILD).exists()
    assert board(client, headers)[PARENT]["subtasks"]["total"] == before - 1


def test_delete_refuses_a_parent_with_subtasks(api, vault):
    client, headers = api
    response = post(
        client, headers, "/api/task/delete", {"path": PARENT, "version": version(vault, PARENT)}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS["delete-parent"]
    assert (vault / PARENT).exists()


def test_delete_refuses_a_note_and_a_stale_version(api, vault):
    client, headers = api
    note = post(
        client, headers, "/api/task/delete", {"path": NOTE, "version": version(vault, NOTE)}
    )
    assert note.status_code == 400
    stale = post(client, headers, "/api/task/delete", {"path": PLAIN, "version": "0" * 64})
    assert stale.status_code == 409
    assert (vault / NOTE).exists() and (vault / PLAIN).exists()


# --- Writes off, and paths ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "body"),
    [
        ("/api/tasks", {"title": "Book venue"}),
        ("/api/task/subtasks", {"path": PLAIN, "version": "0" * 64}),
        ("/api/task/rename", {"path": PLAIN, "name": "x", "version": "0" * 64}),
        ("/api/task/delete", {"path": PLAIN, "version": "0" * 64}),
    ],
)
def test_every_task_write_is_refused_with_writes_off(vault, url, body):
    client, headers = make_client(vault, allow_writes=False)
    before = files(vault)
    response = post(client, headers, url, body)
    assert response.status_code == 403
    assert files(vault) == before


@pytest.mark.parametrize(
    "path", ["../outside.md", "/etc/passwd.md", ".obsidian/x.md", "Tasks/../../x.md"]
)
def test_task_writes_refuse_paths_outside_the_listing(api, vault, path):
    client, headers = api
    before = files(vault)
    for url, body in [
        ("/api/tasks", {"title": "x", "parent": path}),
        ("/api/task/subtasks", {"path": path, "version": "0" * 64}),
        ("/api/task/rename", {"path": path, "name": "x", "version": "0" * 64}),
        ("/api/task/delete", {"path": path, "version": "0" * 64}),
    ]:
        assert post(client, headers, url, body).status_code == 404, url
    assert files(vault) == before


def test_task_writes_need_the_session_and_header(vault):
    client, _ = make_client(vault)
    response = client.post("/api/tasks", json={"title": "x"})
    assert response.status_code in (401, 403)
    assert not (vault / "Tasks/x.md").exists()
