"""Creating tasks, sub-tasks (checklist lines), Edit details, renaming and
deleting tasks (#9 part (c), with Sheikh's decisions on #40).

Every write goes to a copy of dev-vault/ in a temporary folder (Sheikh's
decision 5 on #8). "Now" is fixed, so times are exact."""

import hashlib
import shutil
from datetime import UTC, date, datetime

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
BETA = "Tasks/Launch Atlas beta.md"  # in progress; [x] Write the beta invite, [ ] Book a demo slot
DONE = "Tasks/Write Atlas architecture note.md"  # done
PLAIN = "Tasks/Tidy Reference folder.md"  # open, no checklist
NOTE = "Projects/Atlas kickoff.md"
Z = "0" * 64


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


def snapshot(vault):
    return {p: (vault / p).read_bytes() for p in files(vault)}


def post(client, headers, url, body):
    return client.post(url, json=body, headers=headers)


def read(vault, path):
    return (vault / path).read_text(encoding="utf-8")


def move(client, headers, vault, path, to):
    return post(
        client, headers, "/api/task/move", {"path": path, "to": to, "version": version(vault, path)}
    )


# --- Create ----------------------------------------------------------------------------------


def test_create_makes_exactly_this_file(api, vault):
    client, headers = api
    response = post(
        client,
        headers,
        "/api/tasks",
        {
            "title": "Book venue",
            "priority": "high",
            "due": "2031-05-02",
            "description": "Somewhere for **40** people.\r\nNear the station.",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "path": "Tasks/Book venue.md",
        "version": version(vault, "Tasks/Book venue.md"),
    }
    assert read(vault, "Tasks/Book venue.md") == (
        "---\ntags:\n  - task\nstatus: open\npriority: high\ndue: 2031-05-02\n"
        f"dateCreated: {T}\ndateModified: {T}\n---\n\n"
        "Somewhere for **40** people.\nNear the station.\n\n"
        f"## Status History\n\n- {T} — created → open\n"
    )
    card = board(client, headers)["Tasks/Book venue.md"]
    assert (card["status"], card["priority"], card["due"]) == ("open", "high", "2031-05-02")
    assert card["description"] == "Somewhere for **40** people."
    assert card["checklist"] == []


def test_create_with_only_a_title(api, vault):
    client, headers = api
    path = post(client, headers, "/api/tasks", {"title": "Book venue"}).json()["path"]
    assert read(vault, path) == (
        f"---\ntags:\n  - task\nstatus: open\ndateCreated: {T}\ndateModified: {T}\n---\n\n"
        f"## Status History\n\n- {T} — created → open\n"
    )


def test_a_new_task_is_valid_yaml_and_moves_like_any_other(api, vault):
    client, headers = api
    path = post(client, headers, "/api/tasks", {"title": "Book venue"}).json()["path"]
    meta = yaml.safe_load(read(vault, path).split("---")[1])
    assert meta["tags"] == ["task"] and meta["status"] == "open"
    assert move(client, headers, vault, path, "in-progress").status_code == 200


def test_create_never_replaces_a_task(api, vault):
    client, headers = api
    before = snapshot(vault)
    response = post(client, headers, "/api/tasks", {"title": "Tidy Reference folder"})
    assert response.status_code == 409 and response.json()["reason"] == "exists"
    assert snapshot(vault) == before


@pytest.mark.parametrize("title", ["a/b", "../escape", ".hidden", "x[[y]]", "a:b", "  "])
def test_create_refuses_names_that_arent_allowed(api, vault, title):
    client, headers = api
    before = files(vault)
    assert post(client, headers, "/api/tasks", {"title": title}).status_code == 400
    assert files(vault) == before


@pytest.mark.parametrize(
    ("description", "code"),
    [
        ("Intro\n## A section", "description-heading"),
        ("# Title", "description-heading"),
        ("bell \x07", "description-character"),
    ],
)
def test_create_refuses_a_description_that_would_break_the_task(api, vault, description, code):
    client, headers = api
    before = files(vault)
    response = post(client, headers, "/api/tasks", {"title": "x", "description": description})
    assert response.status_code == 400
    assert response.json() == {"detail": task_writes.TASK_REFUSALS[code]}
    assert files(vault) == before


def test_a_heading_in_a_code_block_and_a_level_3_heading_are_fine(api, vault):
    client, headers = api
    text = "### Steps\n```\n## not a heading\n```"
    path = post(client, headers, "/api/tasks", {"title": "x", "description": text}).json()["path"]
    assert f"\n{text}\n\n## Status History" in read(vault, path)


def test_create_refuses_fields_it_doesnt_know(api):
    client, headers = api
    for body in [
        {"title": "x", "status": "done"},
        {"title": "x", "parent": BETA},
        {"title": "x", "priority": "urgent"},
        {"title": "x", "due": "soon"},
    ]:
        assert post(client, headers, "/api/tasks", body).status_code == 422, body


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


def test_task_text_refuses_if_the_frontmatter_doesnt_read_back(monkeypatch):
    monkeypatch.setattr(lifecycle, "local_iso", lambda at: "yes")  # reads back as True
    with pytest.raises(task_writes.TaskRefused) as refused:
        task_writes.task_text(NOW)
    assert refused.value.code == "build-failed"


# --- Sub-tasks: checklist lines -----------------------------------------------------------------


def add(client, headers, vault, path, text):
    return post(
        client,
        headers,
        "/api/task/checklist/add",
        {"path": path, "text": text, "version": version(vault, path)},
    )


def tick(client, headers, vault, path, index, done=True):
    return post(
        client,
        headers,
        "/api/task/checklist/set",
        {"path": path, "index": index, "done": done, "version": version(vault, path)},
    )


def test_add_a_sub_task_after_the_last_checklist_line_and_nothing_else_changes(api, vault):
    client, headers = api
    before = read(vault, BETA)
    response = add(client, headers, vault, BETA, "  Send the invites  ")
    assert response.status_code == 200, response.text
    assert response.json() == {"path": BETA, "version": version(vault, BETA)}
    assert read(vault, BETA) == before.replace(
        "- [ ] Book a demo slot\n", "- [ ] Book a demo slot\n- [ ] Send the invites\n"
    )
    assert board(client, headers)[BETA]["checklist"][-1] == {
        "text": "Send the invites",
        "done": False,
    }


def test_the_first_sub_task_goes_at_the_end_of_the_top_text(api, vault):
    client, headers = api
    before = read(vault, PLAIN)
    assert add(client, headers, vault, PLAIN, "Sort the PDFs").status_code == 200
    assert read(vault, PLAIN) == before.replace(
        "\n\n## Status History", "\n\n- [ ] Sort the PDFs\n\n## Status History"
    )


def test_tick_and_untick_change_one_character(api, vault):
    client, headers = api
    before = read(vault, BETA)
    assert tick(client, headers, vault, BETA, 1).status_code == 200
    assert read(vault, BETA) == before.replace("- [ ] Book a demo slot", "- [x] Book a demo slot")
    assert tick(client, headers, vault, BETA, 0, done=False).status_code == 200
    assert board(client, headers)[BETA]["checklist"] == [
        {"text": "Write the beta invite", "done": False},
        {"text": "Book a demo slot", "done": True},
    ]


def test_ticking_a_line_already_ticked_writes_nothing(api, vault):
    client, headers = api
    before = (vault / BETA).stat().st_mtime_ns, read(vault, BETA)
    response = tick(client, headers, vault, BETA, 0)  # already [x]
    assert response.status_code == 200
    assert response.json()["version"] == version(vault, BETA)
    assert ((vault / BETA).stat().st_mtime_ns, read(vault, BETA)) == before


def test_a_crlf_task_keeps_its_line_endings(api, vault):
    client, headers = api
    (vault / BETA).write_bytes(read(vault, BETA).replace("\n", "\r\n").encode())
    assert add(client, headers, vault, BETA, "Third").status_code == 200
    assert tick(client, headers, vault, BETA, 2).status_code == 200
    data = (vault / BETA).read_bytes()
    assert data.count(b"\n") == data.count(b"\r\n")
    assert b"- [ ] Book a demo slot\r\n- [x] Third\r\n" in data


@pytest.mark.parametrize("index", [2, 99])
def test_ticking_a_line_that_isnt_there_is_refused(api, vault, index):
    client, headers = api
    before = read(vault, BETA)
    response = tick(client, headers, vault, BETA, index)
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS["item-gone"]
    assert read(vault, BETA) == before


def test_a_done_tasks_checklist_cant_change(api, vault):
    client, headers = api
    before = snapshot(vault)
    for response in [
        add(client, headers, vault, DONE, "More"),
        tick(client, headers, vault, DONE, 0),
    ]:
        assert response.status_code == 400
        assert response.json()["detail"] == task_writes.TASK_REFUSALS["task-done"]
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    ("text", "code"), [("   ", "item-empty"), ("bell \x07", "item-text"), ("a\nb", "item-text")]
)
def test_add_refuses_text_that_isnt_one_plain_line(api, vault, text, code):
    client, headers = api
    before = read(vault, BETA)
    response = add(client, headers, vault, BETA, text)
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS[code]
    assert read(vault, BETA) == before


def test_add_refuses_an_overlong_line(api, vault):
    client, headers = api
    before = read(vault, BETA)
    assert add(client, headers, vault, BETA, "x" * 301).status_code == 422
    assert read(vault, BETA) == before


def test_checklist_writes_quote_the_version(api, vault):
    client, headers = api
    before = read(vault, BETA)
    for url, body in [
        ("/api/task/checklist/add", {"path": BETA, "text": "x", "version": Z}),
        ("/api/task/checklist/set", {"path": BETA, "index": 1, "done": True, "version": Z}),
        # Already ticked, so nothing to write: still refused for a stale version.
        ("/api/task/checklist/set", {"path": BETA, "index": 0, "done": True, "version": Z}),
    ]:
        response = post(client, headers, url, body)
        assert response.status_code == 409 and response.json()["reason"] == "changed", url
    assert read(vault, BETA) == before


def test_checklist_writes_refuse_a_note(api, vault):
    client, headers = api
    before = read(vault, NOTE)
    response = add(client, headers, vault, NOTE, "x")
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS["not-a-task"]
    assert read(vault, NOTE) == before


def test_a_task_can_close_once_every_sub_task_is_ticked(api, vault):
    client, headers = api
    assert move(client, headers, vault, BETA, "in-review").status_code == 200
    assert move(client, headers, vault, BETA, "done").status_code == 400
    assert tick(client, headers, vault, BETA, 1).status_code == 200
    assert move(client, headers, vault, BETA, "done").status_code == 200


# --- Edit details --------------------------------------------------------------------------------


def details(client, headers, vault, path, **changes):
    current = client.get("/api/note", params={"path": path}, headers=headers).json()
    body = {
        "path": path,
        "version": version(vault, path),
        "priority": current["task"]["priority"],
        "due": current["task"]["due"],
        "projects": current["task"]["projects"],
        "tags": current["tags"],
        "description": current["task"]["description"],
        **changes,
    }
    return post(client, headers, "/api/task/details", body)


def test_edit_details_with_no_change_writes_nothing(api, vault):
    client, headers = api
    before = snapshot(vault)
    response = details(client, headers, vault, BETA)
    assert response.status_code == 200, response.text
    assert response.json()["version"] == version(vault, BETA)
    assert snapshot(vault) == before


def test_edit_details_changes_only_the_fields_that_change(api, vault):
    client, headers = api
    before = read(vault, BETA)
    response = details(
        client,
        headers,
        vault,
        BETA,
        priority="low",
        due="2031-05-09",
        projects=["Atlas kickoff", "Harbor retrospective"],
        tags=["#beta", "launch/q2"],
    )
    assert response.status_code == 200, response.text
    expected = (
        before.replace("priority: high", "priority: low")
        .replace("due: 2031-04-30", "due: 2031-05-09")
        .replace(
            'projects:\n  - "[[Atlas kickoff]]"',
            'projects:\n  - "[[Atlas kickoff]]"\n  - "[[Harbor retrospective]]"',
        )
        .replace("tags:\n  - task\n", "tags:\n  - task\n  - beta\n  - launch/q2\n")
        .replace("dateModified: 2031-04-14T10:00:00Z", f"dateModified: {T}")
    )
    assert read(vault, BETA) == expected
    assert board(client, headers)[BETA]["projects"] == ["Atlas kickoff", "Harbor retrospective"]


def test_edit_details_can_clear_fields(api, vault):
    client, headers = api
    response = details(client, headers, vault, BETA, priority=None, due=None, projects=[])
    assert response.status_code == 200, response.text
    meta, _ = frontmatter.split(read(vault, BETA))
    assert "priority" not in meta and "due" not in meta and "projects" not in meta
    assert meta["tags"] == ["task"] and meta["status"] == "in-progress"


def test_edit_details_replaces_the_description_and_keeps_the_checklist(api, vault):
    client, headers = api
    before = read(vault, BETA)
    response = details(client, headers, vault, BETA, description="New words.\n\nTwo paragraphs.")
    assert response.status_code == 200, response.text
    old = (
        "Made-up task with sub-tasks, for development and tests. "
        "Its sub-tasks are its checklist lines."
    )
    assert read(vault, BETA) == before.replace(old, "New words.\n\nTwo paragraphs.").replace(
        "dateModified: 2031-04-14T10:00:00Z", f"dateModified: {T}"
    )
    assert board(client, headers)[BETA]["checklist"][1]["text"] == "Book a demo slot"


def test_edit_details_keeps_a_value_it_doesnt_show(api, vault):
    """An unknown priority shows as none; saving without touching it keeps it."""
    client, headers = api
    text = read(vault, PLAIN).replace("priority: low", "priority: urgent")
    assert "priority: urgent" in text
    (vault / PLAIN).write_text(text)
    response = details(client, headers, vault, PLAIN, due="2031-06-01")
    assert response.status_code == 200, response.text
    meta, _ = frontmatter.split(read(vault, PLAIN))
    assert meta["priority"] == "urgent" and meta["due"] == date(2031, 6, 1)
    assert "\ndue: 2031-06-01\n" in read(vault, PLAIN)  # a date, not quoted text


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"tags": ["two words"]}, "tag-bad"),
        ({"tags": ["123"]}, "tag-bad"),
        ({"tags": ["task"]}, "tag-bad"),
        ({"tags": [f"t{n}" for n in range(21)]}, "tag-many"),
        ({"projects": ["a[[b]]"]}, "project-bad"),
        ({"projects": ["../x"]}, "project-bad"),
        ({"projects": [f"p{n}" for n in range(21)]}, "project-many"),
        ({"description": "## Section"}, "description-heading"),
    ],
)
def test_edit_details_refuses_bad_values_and_writes_nothing(api, vault, changes, code):
    client, headers = api
    before = snapshot(vault)
    response = details(client, headers, vault, BETA, **changes)
    assert response.status_code == 400
    assert response.json() == {"detail": task_writes.TASK_REFUSALS[code]}
    assert snapshot(vault) == before


def test_edit_details_refuses_a_duplicated_field(api, vault):
    client, headers = api
    text = read(vault, PLAIN).replace("priority: low", "priority: low\npriority: high")
    (vault / PLAIN).write_text(text)
    response = details(client, headers, vault, PLAIN, priority="normal")
    assert response.status_code == 400
    assert response.json()["detail"] == task_writes.TASK_REFUSALS["duplicate-field"]
    assert read(vault, PLAIN) == text


def test_edit_details_quotes_the_version_and_refuses_a_note(api, vault):
    client, headers = api
    before = snapshot(vault)
    assert details(client, headers, vault, BETA, priority="low", version=Z).status_code == 409
    # Nothing to change, but still refused for a stale version.
    assert details(client, headers, vault, BETA, version=Z).status_code == 409
    note = post(
        client,
        headers,
        "/api/task/details",
        {
            "path": NOTE,
            "version": version(vault, NOTE),
            "priority": None,
            "due": None,
            "projects": [],
            "tags": [],
            "description": "",
        },
    )
    assert note.status_code == 400
    assert snapshot(vault) == before


# --- Rename and delete -------------------------------------------------------------------------


def test_rename_a_task_with_sub_tasks(api, vault):
    client, headers = api
    response = post(
        client,
        headers,
        "/api/task/rename",
        {"path": BETA, "name": "Launch beta", "version": version(vault, BETA)},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"path": "Tasks/Launch beta.md"}
    assert not (vault / BETA).exists()
    assert board(client, headers)["Tasks/Launch beta.md"]["checklist"][0]["done"] is True


def test_rename_refuses_a_note_a_stale_version_and_a_taken_name(api, vault):
    client, headers = api
    note = post(
        client,
        headers,
        "/api/task/rename",
        {"path": NOTE, "name": "x", "version": version(vault, NOTE)},
    )
    assert note.status_code == 400
    assert note.json()["detail"] == task_writes.TASK_REFUSALS["not-a-task"]
    stale = post(client, headers, "/api/task/rename", {"path": PLAIN, "name": "x", "version": Z})
    assert stale.status_code == 409 and stale.json()["reason"] == "changed"
    taken = post(
        client,
        headers,
        "/api/task/rename",
        {"path": PLAIN, "name": "Add glossary entries", "version": version(vault, PLAIN)},
    )
    assert taken.status_code == 409 and taken.json()["reason"] == "exists"
    assert (vault / PLAIN).exists() and (vault / NOTE).exists()


def test_delete_moves_a_task_to_trash(api, vault):
    client, headers = api
    response = post(
        client, headers, "/api/task/delete", {"path": BETA, "version": version(vault, BETA)}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"trashed_to": ".trash/" + BETA}
    assert (vault / ".trash" / BETA).exists() and not (vault / BETA).exists()


def test_delete_refuses_a_note_and_a_stale_version(api, vault):
    client, headers = api
    note = post(
        client, headers, "/api/task/delete", {"path": NOTE, "version": version(vault, NOTE)}
    )
    assert note.status_code == 400
    assert (
        post(client, headers, "/api/task/delete", {"path": PLAIN, "version": Z}).status_code == 409
    )
    assert (vault / NOTE).exists() and (vault / PLAIN).exists()


# --- Writes off, and paths ---------------------------------------------------------------------

EVERY_WRITE = [
    ("/api/tasks", {"title": "Book venue"}),
    ("/api/task/checklist/add", {"path": BETA, "text": "x", "version": Z}),
    ("/api/task/checklist/set", {"path": BETA, "index": 0, "done": False, "version": Z}),
    (
        "/api/task/details",
        {
            "path": BETA,
            "version": Z,
            "priority": None,
            "due": None,
            "projects": [],
            "tags": [],
            "description": "",
        },
    ),
    ("/api/task/rename", {"path": BETA, "name": "x", "version": Z}),
    ("/api/task/delete", {"path": BETA, "version": Z}),
]


@pytest.mark.parametrize(("url", "body"), EVERY_WRITE)
def test_every_task_write_is_refused_with_writes_off(vault, url, body):
    client, headers = make_client(vault, allow_writes=False)
    before = snapshot(vault)
    assert post(client, headers, url, body).status_code == 403
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    "path", ["../outside.md", "/etc/passwd.md", ".obsidian/x.md", "Tasks/../../x.md"]
)
@pytest.mark.parametrize(("url", "body"), EVERY_WRITE[1:])
def test_task_writes_refuse_paths_outside_the_listing(api, vault, path, url, body):
    client, headers = api
    before = snapshot(vault)
    assert post(client, headers, url, {**body, "path": path}).status_code == 404
    assert snapshot(vault) == before


@pytest.mark.parametrize(("url", "body"), EVERY_WRITE)
def test_task_writes_need_the_session_and_header(vault, url, body):
    client, _ = make_client(vault)
    before = snapshot(vault)
    assert client.post(url, json=body).status_code in (401, 403)
    assert snapshot(vault) == before
