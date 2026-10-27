"""Editing a note's body and saving it (part (c) of issue #8; threat model T5, T7, T8).

Every write here goes to a copy of dev-vault/ in a temporary folder, never to
the committed folder (Sheikh's decision 5 on #8)."""

import hashlib
import shutil

import pytest
from fastapi.testclient import TestClient

from onyx import frontmatter
from onyx.app import create_app
from onyx.config import ConfigError, load_settings
from onyx.editing import uses_crlf, with_line_endings_of
from onyx.try_writes import make_copy
from tests.test_security_baseline import BASE, DEV_VAULT, PORT, sign_in, with_session

INBOX = "Inbox.md"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- Keeping the frontmatter byte for byte -------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "no frontmatter\n",
        "---\nstatus: open\n---\n\n# Body\n",
        "---\r\nstatus: open\r\n---\r\n\r\n# Body\r\n",
        "﻿---\nstatus: open\n---\nbody",
        "﻿no frontmatter",
        "---\nstatus: open\n---",  # closing line is the last line, no newline
        "---\nstatus: open\n---\n",
        "---\nkey: [unclosed\n---\nbody\n",  # malformed YAML
        "---\nno closing line\nbody\n",
        "---\n" + "x: " + "y" * (70 * 1024) + "\n---\nbody\n",  # over 64 KiB
        "---\n---\nempty frontmatter\n",
        "--- \nnot a fence (trailing space)\n---\n",
        "---\nstatus: open\n---\n---\nsecond fence is body\n",
    ],
)
def test_split_raw_round_trips(text):
    head, body = frontmatter.split_raw(text)
    assert head + body == text


@pytest.mark.parametrize(
    "text",
    [
        "---\nstatus: open\n---\n\n# Body\n",
        "---\r\nstatus: open\r\n---\r\n\r\n# Body\r\n",
        "﻿---\nstatus: open\n---\nbody",
        "no frontmatter\n",
        "---\nno closing line\nbody\n",
    ],
)
def test_split_raw_body_is_the_same_body_split_reads(text):
    assert frontmatter.split_raw(text)[1] == frontmatter.split(text)[1]


def test_split_raw_head_is_the_whole_block_with_its_line_ending():
    assert frontmatter.split_raw("---\na: 1\n---\nrest") == ("---\na: 1\n---\n", "rest")
    assert frontmatter.split_raw("---\r\na: 1\r\n---\r\nrest") == ("---\r\na: 1\r\n---\r\n", "rest")
    assert frontmatter.split_raw("﻿body") == ("﻿", "body")


def test_line_endings():
    assert uses_crlf("a\r\nb\r\n")
    assert not uses_crlf("a\nb\r\n")
    assert not uses_crlf("no newline")
    assert with_line_endings_of("a\nb\n", "x\r\ny\r\n") == "a\r\nb\r\n"
    assert with_line_endings_of("a\r\nb\n", "x\r\ny\r\n") == "a\r\nb\r\n"
    assert with_line_endings_of("a\nb\n", "x\ny\n") == "a\nb\n"
    assert with_line_endings_of("a\nb\n", "mixed\r\nendings\n") == "a\nb\n"


# --- The API --------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path):
    """A copy of dev-vault/ to write to."""
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


def source(client, headers, path=INBOX):
    response = client.get("/api/note/source", params={"path": path}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def save(client, headers, path, body, version):
    return client.put(
        "/api/note", json={"path": path, "body": body, "version": version}, headers=headers
    )


def test_source_gives_the_body_frontmatter_and_version(api, vault):
    client, headers = api
    data = source(client, headers)
    raw = (vault / INBOX).read_bytes()
    assert data["version"] == sha(raw)
    assert data["frontmatter"].startswith("---\nsynthetic: true\n")
    assert data["frontmatter"] + data["body"] == raw.decode()
    assert data["body"].startswith("\n# Inbox\n")
    assert data["writable"] is True


def test_source_keeps_hidden_sections_the_focus_view_leaves_out(api):
    """The editor must get the whole body, or saving would drop Status History."""
    client, headers = api
    task = next(
        n["path"] for n in client.get("/api/items", headers=headers).json()["items"]
        if n["kind"] == "task"
    )
    assert "## Status History" in source(client, headers, task)["body"]


def test_save_replaces_the_body_and_keeps_the_frontmatter(api, vault):
    client, headers = api
    before = source(client, headers)
    response = save(client, headers, INBOX, "\n# Inbox\n\nEdited in Onyx.\n", before["version"])
    assert response.status_code == 200, response.text
    raw = (vault / INBOX).read_bytes()
    assert raw == (before["frontmatter"] + "\n# Inbox\n\nEdited in Onyx.\n").encode()
    assert response.json() == {"path": INBOX, "version": sha(raw)}


def test_save_never_rebuilds_frontmatter_it_cant_parse(api, vault):
    client, headers = api
    odd = "---\nstatus: open\nweird: [unclosed\nunknown_field: 1\n---\nbody\n"
    (vault / "Odd.md").write_text(odd, encoding="utf-8")
    data = source(client, headers, "Odd.md")
    assert save(client, headers, "Odd.md", "new body\n", data["version"]).status_code == 200
    assert (vault / "Odd.md").read_text(encoding="utf-8") == (
        "---\nstatus: open\nweird: [unclosed\nunknown_field: 1\n---\nnew body\n"
    )


@pytest.mark.parametrize(
    "raw",
    [
        b"---\r\nsynthetic: true\r\n---\r\n\r\n# CRLF\r\n\r\nLine two.\r\n",
        b"\xef\xbb\xbf---\nsynthetic: true\n---\n\n# BOM\n",
        b"---\nsynthetic: true\n---\n\n# No final newline",
        b"\xef\xbb\xbfNo frontmatter, BOM, CRLF\r\nsecond line\r\n",
    ],
)
def test_saving_without_an_edit_leaves_the_file_byte_for_byte(api, vault, raw):
    client, headers = api
    (vault / "Bytes.md").write_bytes(raw)
    data = source(client, headers, "Bytes.md")
    # As a browser text box gives it back: "\n" line endings only.
    typed = data["body"].replace("\r\n", "\n")
    response = save(client, headers, "Bytes.md", typed, data["version"])
    assert response.status_code == 200, response.text
    assert (vault / "Bytes.md").read_bytes() == raw
    assert response.json()["version"] == sha(raw)


def test_an_edit_to_a_crlf_note_stays_crlf(api, vault):
    client, headers = api
    (vault / "Crlf.md").write_bytes(b"---\r\na: 1\r\n---\r\none\r\n")
    data = source(client, headers, "Crlf.md")
    assert save(client, headers, "Crlf.md", "one\ntwo\n", data["version"]).status_code == 200
    assert (vault / "Crlf.md").read_bytes() == b"---\r\na: 1\r\n---\r\none\r\ntwo\r\n"


def test_a_stale_version_is_refused_and_nothing_is_written(api, vault):
    client, headers = api
    data = source(client, headers)
    # Changed by another program (Obsidian, say) after Onyx opened it.
    changed = (vault / INBOX).read_bytes() + b"\nAdded elsewhere.\n"
    (vault / INBOX).write_bytes(changed)
    response = save(client, headers, INBOX, "my edit\n", data["version"])
    assert response.status_code == 409
    assert response.json() == {
        "detail": "The note changed on disk since you opened it.",
        "version": sha(changed),
    }
    assert (vault / INBOX).read_bytes() == changed


def test_the_second_of_two_saves_from_the_same_version_is_refused(api, vault):
    client, headers = api
    data = source(client, headers)
    assert save(client, headers, INBOX, "first\n", data["version"]).status_code == 200
    assert save(client, headers, INBOX, "second\n", data["version"]).status_code == 409
    assert (vault / INBOX).read_text(encoding="utf-8").endswith("first\n")


def test_save_is_refused_unless_writes_are_allowed(vault):
    client, headers = make_client(vault, allow_writes=False)
    before = (vault / INBOX).read_bytes()
    data = source(client, headers)
    assert data["writable"] is False
    response = save(client, headers, INBOX, "nope\n", data["version"])
    assert response.status_code == 403
    assert "--allow-writes" in response.json()["detail"]
    assert (vault / INBOX).read_bytes() == before


def test_allow_writes_is_refused_for_the_committed_dev_vault():
    with pytest.raises(ConfigError, match="inside the repository"):
        load_settings(DEV_VAULT, PORT, allow_writes=True)
    load_settings(DEV_VAULT, PORT)  # reading it is fine


def test_try_writes_copies_dev_vault_outside_the_repo():
    from onyx.config import REPO_ROOT

    copy = make_copy()
    try:
        assert not copy.resolve().is_relative_to(REPO_ROOT)
        assert (copy / INBOX).read_bytes() == (DEV_VAULT / INBOX).read_bytes()
        load_settings(copy, PORT, allow_writes=True)
    finally:
        shutil.rmtree(copy.parent)


@pytest.mark.parametrize(
    "path",
    [
        "../outside.md",
        "/etc/passwd.md",
        ".obsidian/workspace.md",
        "Missing.md",
        "Inbox.md/../Inbox.md",
        "inbox.md",  # not the listed name, even on a case-insensitive disk
        "Projects",
    ],
)
def test_save_only_writes_a_listed_note(api, vault, path, tmp_path):
    client, headers = api
    before = {p: p.read_bytes() for p in vault.rglob("*") if p.is_file()}
    response = save(client, headers, path, "escaped\n", "0" * 64)
    assert response.status_code == 404
    assert {p: p.read_bytes() for p in vault.rglob("*") if p.is_file()} == before
    assert not (tmp_path / "outside.md").exists()
    assert client.get("/api/note/source", params={"path": path}, headers=headers).status_code == 404


def test_save_through_an_escaping_symlink_is_refused(api, vault, tmp_path):
    client, headers = api
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (vault / "Link.md").symlink_to(outside)
    response = save(client, headers, "Link.md", "escaped\n", sha(b"outside\n"))
    assert response.status_code == 404
    assert outside.read_text(encoding="utf-8") == "outside\n"


@pytest.mark.parametrize(
    "body",
    [
        {"path": INBOX, "body": "x"},  # no version
        {"path": INBOX, "body": "x", "version": "not-a-sha"},
        {"path": INBOX, "body": "x", "version": "0" * 64, "frontmatter": "status: done"},
        {"path": "", "body": "x", "version": "0" * 64},
        {"path": INBOX, "body": 5, "version": "0" * 64},
    ],
)
def test_invalid_save_requests_are_422(api, vault, body):
    client, headers = api
    before = (vault / INBOX).read_bytes()
    assert client.put("/api/note", json=body, headers=headers).status_code == 422
    assert (vault / INBOX).read_bytes() == before


def test_a_body_over_the_cap_is_413_and_nothing_is_written(api, vault):
    client, headers = api
    before = (vault / INBOX).read_bytes()
    data = source(client, headers)
    response = save(client, headers, INBOX, "x" * (1024 * 1024), data["version"])
    assert response.status_code == 413
    assert (vault / INBOX).read_bytes() == before


def test_save_needs_the_header_a_same_site_origin_and_a_session(api, vault):
    client, headers = api
    data = source(client, headers)
    before = (vault / INBOX).read_bytes()
    body = {"path": INBOX, "body": "csrf\n", "version": data["version"]}
    no_header = {k: v for k, v in headers.items() if k != "X-Onyx-Request"}
    assert client.put("/api/note", json=body, headers=no_header).status_code == 403
    foreign = {**headers, "Origin": "http://evil.example"}
    assert client.put("/api/note", json=body, headers=foreign).status_code == 403
    no_session = {k: v for k, v in headers.items() if k != "Cookie"}
    client.cookies.clear()
    assert client.put("/api/note", json=body, headers=no_session).status_code == 401
    assert (vault / INBOX).read_bytes() == before


def test_search_finds_the_saved_text_straight_away(api):
    client, headers = api
    data = source(client, headers)
    word = "Zyxwvutsrq"
    assert save(client, headers, INBOX, f"\n# Inbox\n\n{word}\n", data["version"]).status_code == 200
    results = client.get("/api/search", params={"q": word}, headers=headers).json()["results"]
    assert [r["path"] for r in results] == [INBOX]


def test_saving_leaves_no_temporary_files(api, vault):
    client, headers = api
    data = source(client, headers)
    save(client, headers, INBOX, "body\n", data["version"])
    assert not [p for p in vault.rglob(".onyx-tmp-*")]


def test_saved_note_content_is_not_logged(api, caplog):
    client, headers = api
    data = source(client, headers)
    secret = "Qwertyuiop-not-in-logs"
    with caplog.at_level("DEBUG"):
        save(client, headers, INBOX, f"{secret}\n", data["version"])
    assert secret not in caplog.text
