"""Create, rename and delete notes through the API (part (d) of issue #8;
threat model T1, T5, T8).

Every write goes to a copy of dev-vault/ in a temporary folder, never the
committed folder (Sheikh's decision 5 on #8)."""

import hashlib
import shutil

import pytest
from fastapi.testclient import TestClient

from onyx import app as app_module
from onyx.app import create_app
from onyx.config import load_settings
from onyx.editing import note_file_name
from onyx.vault import PathRejected
from tests.test_security_baseline import BASE, DEV_VAULT, PORT, sign_in, with_session

NOTE = "Projects/Atlas kickoff.md"
TASK = "Tasks/Add glossary entries.md"


@pytest.fixture
def vault(tmp_path):
    copy = tmp_path / "vault"
    shutil.copytree(DEV_VAULT, copy, symlinks=True)
    return copy


def make_client(vault_dir, allow_writes=True):
    app = create_app(load_settings(vault_dir, PORT, allow_writes=allow_writes))
    client = TestClient(app, base_url=BASE)
    return client, with_session(sign_in(client, app))


@pytest.fixture
def api(vault):
    return make_client(vault)


def version(vault, path):
    return hashlib.sha256((vault / path).read_bytes()).hexdigest()


def listed(client, headers):
    return {n["path"] for n in client.get("/api/notes", headers=headers).json()["notes"]}


def create(client, headers, folder, name):
    return client.post("/api/notes", json={"folder": folder, "name": name}, headers=headers)


def rename(client, headers, path, name, ver):
    return client.post(
        "/api/note/rename", json={"path": path, "name": name, "version": ver}, headers=headers
    )


def delete(client, headers, path, ver):
    return client.post("/api/note/delete", json={"path": path, "version": ver}, headers=headers)


def snapshot(vault):
    return {
        p.relative_to(vault).as_posix(): p.read_bytes() for p in vault.rglob("*") if p.is_file()
    }


# --- Names -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "file"),
    [
        ("Plan", "Plan.md"),
        ("  Plan  ", "Plan.md"),
        ("Plan.md", "Plan.md"),
        ("Plan.MD", "Plan.md"),
        ("Unicode — ✓ é 字", "Unicode — ✓ é 字.md"),
        ("Q2, draft (v1)", "Q2, draft (v1).md"),
    ],
)
def test_note_file_name(typed, file):
    assert note_file_name(typed) == file


@pytest.mark.parametrize(
    "typed",
    [
        "",
        "   ",
        ".md",
        "a/b",
        "..",
        "../x",
        ".hidden",
        "a\\b",
        "a:b",
        "a#b",
        "a^b",
        "[[a]]",
        "a|b",
        "a*b",
        "a?b",
        'a"b',
        "a<b",
        "a>b",
        "a\x00b",
        "a\nb",
        "a\x7fb",
    ],
)
def test_note_file_name_refuses(typed):
    with pytest.raises(PathRejected):
        note_file_name(typed)


# --- Create ------------------------------------------------------------------------


def test_create_makes_an_empty_note_in_the_folder(api, vault):
    client, headers = api
    response = create(client, headers, "Projects", "Atlas budget")
    assert response.status_code == 201, response.text
    assert response.json() == {
        "path": "Projects/Atlas budget.md",
        "version": hashlib.sha256(b"").hexdigest(),
    }
    assert (vault / "Projects/Atlas budget.md").read_bytes() == b""
    assert "Projects/Atlas budget.md" in listed(client, headers)


def test_create_at_the_top_level(api, vault):
    client, headers = api
    assert create(client, headers, "", "Loose idea").status_code == 201
    assert (vault / "Loose idea.md").exists()


def test_create_never_replaces_a_note(api, vault):
    client, headers = api
    before = snapshot(vault)
    response = create(client, headers, "Projects", "Atlas kickoff")
    assert response.status_code == 409
    assert response.json()["reason"] == "exists"
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    ("folder", "name"),
    [
        ("Nope", "x"),  # no such folder
        ("..", "x"),
        ("../..", "x"),
        (".obsidian", "x"),
        (".trash", "x"),
        ("Projects", "../x"),
        ("Projects", "a/b"),
        ("Projects", ".hidden"),
        ("/srv", "x"),
        ("Projects/Atlas kickoff.md", "x"),  # a note, not a folder
    ],
)
def test_create_refuses_bad_folders_and_names(api, vault, folder, name):
    client, headers = api
    before = snapshot(vault)
    response = create(client, headers, folder, name)
    assert response.status_code == 400, response.text
    assert snapshot(vault) == before


def test_create_in_a_folder_link_leading_outside_is_refused(api, vault, tmp_path):
    client, headers = api
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / "Out").symlink_to(outside, target_is_directory=True)
    assert create(client, headers, "Out", "planted").status_code == 400
    assert list(outside.iterdir()) == []


# --- Rename ------------------------------------------------------------------------


def test_rename_in_the_same_folder(api, vault):
    client, headers = api
    before = (vault / NOTE).read_bytes()
    response = rename(client, headers, NOTE, "Atlas kick-off", version(vault, NOTE))
    assert response.status_code == 200, response.text
    assert response.json() == {"path": "Projects/Atlas kick-off.md"}
    assert (vault / "Projects/Atlas kick-off.md").read_bytes() == before
    assert not (vault / NOTE).exists()
    paths = listed(client, headers)
    assert "Projects/Atlas kick-off.md" in paths and NOTE not in paths
    assert client.get("/api/note", params={"path": NOTE}, headers=headers).status_code == 404


def test_rename_at_the_top_level_stays_at_the_top_level(api, vault):
    client, headers = api
    response = rename(client, headers, "Inbox.md", "Inbox old", version(vault, "Inbox.md"))
    assert response.json() == {"path": "Inbox old.md"}


def test_rename_can_only_change_the_name_not_the_folder(api, vault):
    client, headers = api
    before = snapshot(vault)
    response = rename(client, headers, NOTE, "../Moved", version(vault, NOTE))
    assert response.status_code == 400
    assert snapshot(vault) == before


def test_rename_onto_an_existing_note_is_refused(api, vault):
    client, headers = api
    before = snapshot(vault)
    response = rename(client, headers, NOTE, "Atlas architecture", version(vault, NOTE))
    assert response.status_code == 409
    assert response.json()["reason"] == "exists"
    assert snapshot(vault) == before


def test_rename_of_a_changed_note_is_refused(api, vault):
    client, headers = api
    stale = version(vault, NOTE)
    (vault / NOTE).write_text("changed in Obsidian\n")
    before = snapshot(vault)
    response = rename(client, headers, NOTE, "Renamed", stale)
    assert response.status_code == 409
    assert response.json()["reason"] == "changed"
    assert snapshot(vault) == before


def test_rename_changing_only_capitals(api, vault):
    client, headers = api
    response = rename(client, headers, NOTE, "atlas kickoff", version(vault, NOTE))
    assert response.status_code == 200, response.text
    assert "atlas kickoff.md" in [p.name for p in (vault / "Projects").iterdir()]
    assert "Projects/atlas kickoff.md" in listed(client, headers)


def test_a_task_is_not_renamed_here(api, vault):
    client, headers = api
    before = snapshot(vault)
    response = rename(client, headers, TASK, "Other", version(vault, TASK))
    assert response.status_code == 400
    assert "task" in response.json()["detail"].lower()
    assert snapshot(vault) == before


@pytest.mark.parametrize("path", ["../outside.md", ".obsidian/app.md", "Nope.md", "/etc/x.md"])
def test_rename_only_finds_listed_notes(api, vault, path):
    client, headers = api
    before = snapshot(vault)
    assert rename(client, headers, path, "x", "0" * 64).status_code == 404
    assert snapshot(vault) == before


# --- Delete ------------------------------------------------------------------------


def test_delete_moves_the_note_to_the_vaults_trash(api, vault):
    client, headers = api
    before = (vault / NOTE).read_bytes()
    response = delete(client, headers, NOTE, version(vault, NOTE))
    assert response.status_code == 200, response.text
    assert response.json() == {"trashed_to": ".trash/Projects/Atlas kickoff.md"}
    assert (vault / ".trash/Projects/Atlas kickoff.md").read_bytes() == before
    assert not (vault / NOTE).exists()
    assert NOTE not in listed(client, headers)
    results = client.get("/api/search", params={"q": "kickoff"}, headers=headers).json()
    assert NOTE not in [r["path"] for r in results["results"]]


def test_a_second_delete_of_the_same_name_keeps_both(api, vault, monkeypatch):
    from datetime import datetime

    monkeypatch.setattr(app_module, "now", lambda: datetime(2031, 4, 16, 9, 30, 15))
    client, headers = api
    first = (vault / NOTE).read_bytes()
    delete(client, headers, NOTE, version(vault, NOTE))
    (vault / NOTE).write_text("a new note with the old name\n")
    response = delete(client, headers, NOTE, version(vault, NOTE))
    assert response.json() == {
        "trashed_to": ".trash/Projects/Atlas kickoff (deleted 2031-04-16 093015).md"
    }
    assert (vault / ".trash/Projects/Atlas kickoff.md").read_bytes() == first


def test_delete_of_a_changed_note_is_refused(api, vault):
    client, headers = api
    stale = version(vault, NOTE)
    (vault / NOTE).write_text("changed in Obsidian\n")
    before = snapshot(vault)
    response = delete(client, headers, NOTE, stale)
    assert response.status_code == 409
    assert response.json()["reason"] == "changed"
    assert snapshot(vault) == before


def test_a_task_is_not_deleted_here(api, vault):
    client, headers = api
    before = snapshot(vault)
    assert delete(client, headers, TASK, version(vault, TASK)).status_code == 400
    assert snapshot(vault) == before


@pytest.mark.parametrize("path", ["../outside.md", ".trash/x.md", "Nope.md", "Projects"])
def test_delete_only_finds_listed_notes(api, vault, path):
    client, headers = api
    before = snapshot(vault)
    assert delete(client, headers, path, "0" * 64).status_code == 404
    assert snapshot(vault) == before


def test_trash_link_leading_outside_is_refused(api, vault, tmp_path):
    client, headers = api
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / ".trash").symlink_to(outside, target_is_directory=True)
    response = delete(client, headers, NOTE, version(vault, NOTE))
    assert response.status_code == 400
    assert (vault / NOTE).exists()
    assert list(outside.iterdir()) == []


# --- Shared rules ------------------------------------------------------------------


def test_every_write_is_refused_unless_writes_are_allowed(vault):
    client, headers = make_client(vault, allow_writes=False)
    before = snapshot(vault)
    ver = version(vault, NOTE)
    for response in [
        create(client, headers, "Projects", "New"),
        rename(client, headers, NOTE, "New", ver),
        delete(client, headers, NOTE, ver),
    ]:
        assert response.status_code == 403
        assert "--allow-writes" in response.json()["detail"]
    assert snapshot(vault) == before


def test_writes_need_the_header_a_same_site_origin_and_a_session(api, vault):
    client, headers = api
    before = snapshot(vault)
    ver = version(vault, NOTE)
    calls = [
        ("/api/notes", {"folder": "Projects", "name": "New"}),
        ("/api/note/rename", {"path": NOTE, "name": "New", "version": ver}),
        ("/api/note/delete", {"path": NOTE, "version": ver}),
    ]
    no_header = {k: v for k, v in headers.items() if k != "X-Onyx-Request"}
    foreign = {**headers, "Origin": "http://evil.example"}
    for url, body in calls:
        assert client.post(url, json=body, headers=no_header).status_code == 403
        assert client.post(url, json=body, headers=foreign).status_code == 403
    no_session = {k: v for k, v in headers.items() if k != "Cookie"}
    client.cookies.clear()
    for url, body in calls:
        assert client.post(url, json=body, headers=no_session).status_code == 401
    assert snapshot(vault) == before


@pytest.mark.parametrize(
    ("url", "body"),
    [
        ("/api/notes", {"folder": "Projects"}),
        ("/api/notes", {"folder": "Projects", "name": ""}),
        ("/api/notes", {"folder": "Projects", "name": "x", "extra": 1}),
        ("/api/note/rename", {"path": NOTE, "name": "x", "version": "not-a-version"}),
        ("/api/note/rename", {"path": NOTE, "name": "x"}),
        ("/api/note/delete", {"path": NOTE}),
        ("/api/note/delete", {"path": NOTE, "version": "A" * 64}),
    ],
)
def test_invalid_requests_are_422(api, vault, url, body):
    client, headers = api
    before = snapshot(vault)
    assert client.post(url, json=body, headers=headers).status_code == 422
    assert snapshot(vault) == before


def test_writes_leave_no_temporary_files(api, vault):
    client, headers = api
    create(client, headers, "Projects", "Temp check")
    rename(client, headers, NOTE, "Renamed", version(vault, NOTE))
    delete(client, headers, "Projects/Renamed.md", version(vault, "Projects/Renamed.md"))
    assert not list(vault.rglob(".onyx-tmp-*"))
