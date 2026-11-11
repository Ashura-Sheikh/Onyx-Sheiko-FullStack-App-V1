"""Moving tasks one stage on, and signing off a close (#9 part (b)).

Every write goes to a copy of dev-vault/ in a temporary folder (Sheikh's
decision 5 on #8). "Now" is fixed, so times and durations are exact."""

import hashlib
import shutil
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from onyx import app as app_module
from onyx import frontmatter, lifecycle
from onyx.app import create_app
from onyx.config import ConfigError, load_settings
from tests.test_security_baseline import BASE, DEV_VAULT, PORT, sign_in, with_session

NOW = datetime(2031, 4, 16, 12, 0, 0, tzinfo=UTC)
T = lifecycle.local_iso(NOW)
OPEN = "Tasks/Tidy Reference folder.md"
REVIEW = "Tasks/Update release checklist.md"
PARENT = "Tasks/Launch Atlas beta.md"
DONE = "Tasks/Write Atlas architecture note.md"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(app_module, "now", lambda: NOW)


@pytest.fixture
def vault(tmp_path):
    copy = tmp_path / "vault"
    shutil.copytree(DEV_VAULT, copy, symlinks=True)
    return copy


def make_client(vault_dir, allow_writes=True, identity="sheikh"):
    settings = load_settings(vault_dir, PORT, allow_writes=allow_writes, identity=identity)
    app = create_app(settings)
    client = TestClient(app, base_url=BASE)
    return client, with_session(sign_in(client, app))


@pytest.fixture
def api(vault):
    return make_client(vault)


def version(vault, path):
    return hashlib.sha256((vault / path).read_bytes()).hexdigest()


def move(client, headers, path, to, ver):
    return client.post(
        "/api/task/move", json={"path": path, "to": to, "version": ver}, headers=headers
    )


def fields(vault, path):
    return frontmatter.split((vault / path).read_text(encoding="utf-8"))[0]


# --- One stage at a time -------------------------------------------------------------------


def test_a_move_changes_status_and_date_modified_and_adds_one_history_line(api, vault):
    client, headers = api
    before = (vault / OPEN).read_text(encoding="utf-8")
    response = move(client, headers, OPEN, "in-progress", version(vault, OPEN))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in-progress"
    assert response.json()["version"] == version(vault, OPEN)
    after = (vault / OPEN).read_text(encoding="utf-8")
    expected = (
        before.replace("status: open", "status: in-progress")
        .replace("dateModified: 2031-04-08T16:00:00Z", f"dateModified: {T}")
        .replace(
            "- 2031-04-08T16:00:00Z — created → open\n",
            f"- 2031-04-08T16:00:00Z — created → open\n- {T} — open → in-progress\n",
        )
    )
    assert after == expected


def test_three_moves_take_a_task_to_review(api, vault):
    client, headers = api
    for to in ["in-progress", "in-review"]:
        assert move(client, headers, OPEN, to, version(vault, OPEN)).status_code == 200
    assert fields(vault, OPEN)["status"] == "in-review"
    assert lifecycle.last_move_to((vault / OPEN).read_text()) == "in-review"


@pytest.mark.parametrize(
    ("path", "to"),
    [
        (OPEN, "in-review"),  # skips a stage
        (OPEN, "done"),
        (OPEN, "open"),  # same stage
        (REVIEW, "in-progress"),  # backwards
        (DONE, "in-review"),
        (DONE, "done"),
    ],
)
def test_skipping_moving_back_and_standing_still_are_refused(api, vault, path, to):
    client, headers = api
    before = (vault / path).read_bytes()
    response = move(client, headers, path, to, version(vault, path))
    assert response.status_code == 400
    assert response.json()["detail"] == "Tasks move one stage at a time, forward only."
    assert (vault / path).read_bytes() == before


def test_a_task_with_an_unknown_stage_is_refused(api, vault):
    client, headers = api
    text = (vault / OPEN).read_text().replace("status: open", "status: someday")
    (vault / OPEN).write_text(text)
    response = move(client, headers, OPEN, "in-progress", version(vault, OPEN))
    assert response.status_code == 400
    assert "isn't one of open" in response.json()["detail"]
    assert (vault / OPEN).read_text() == text


def test_a_note_is_not_moved(api, vault):
    client, headers = api
    path = "Projects/Atlas kickoff.md"
    response = move(client, headers, path, "in-progress", version(vault, path))
    assert response.status_code == 400
    assert response.json()["detail"] == "This is a note, not a task."


def test_date_modified_is_not_added_if_the_task_has_none(api, vault):
    client, headers = api
    text = "".join(
        line for line in (vault / OPEN).read_text().splitlines(True) if "dateModified" not in line
    )
    (vault / OPEN).write_text(text)
    assert move(client, headers, OPEN, "in-progress", version(vault, OPEN)).status_code == 200
    assert "dateModified" not in fields(vault, OPEN)


def test_a_changed_task_is_refused_and_nothing_is_written(api, vault):
    client, headers = api
    stale = version(vault, OPEN)
    (vault / OPEN).write_text((vault / OPEN).read_text() + "edited in Obsidian\n")
    before = (vault / OPEN).read_bytes()
    response = move(client, headers, OPEN, "in-progress", stale)
    assert response.status_code == 409
    assert response.json()["reason"] == "changed"
    assert (vault / OPEN).read_bytes() == before


def test_a_duplicate_status_line_is_refused(api, vault):
    client, headers = api
    text = (vault / OPEN).read_text().replace("status: open\n", "status: open\nstatus: open\n")
    (vault / OPEN).write_text(text)
    response = move(client, headers, OPEN, "in-progress", version(vault, OPEN))
    assert response.status_code == 400
    assert "written twice" in response.json()["detail"]
    assert (vault / OPEN).read_text() == text


# --- Done: sign-off -----------------------------------------------------------------------


def test_done_records_the_sign_off_and_closure_in_sheikos_formats(api, vault):
    client, headers = api
    before = (vault / REVIEW).read_text(encoding="utf-8")
    response = move(client, headers, REVIEW, "done", version(vault, REVIEW))
    assert response.status_code == 200, response.text
    after = (vault / REVIEW).read_text(encoding="utf-8")
    meta = fields(vault, REVIEW)
    assert meta["status"] == "done"
    assert lifecycle.as_timestamp(meta["completedDate"]) == NOW
    assert meta["closedBy"] == "sheikh"
    # dateCreated 2031-04-09T09:30Z to 2031-04-16T12:00Z: 7 days 2.5 hours.
    assert meta["timeToCloseMinutes"] == 7 * 24 * 60 + 150
    assert meta["closureSource"] == "onyx"
    assert after.endswith(
        "- 2031-04-09T11:00:00Z — in-progress → in-review\n"
        f"- {T} — in-review → done (signed off by sheikh at {T})\n\n"
        "## Context\n\n"
        f"- **{T} — sheikh:** Signed off (not closed)\n"
    )
    # Nothing above the frontmatter's end or in the body changed except those lines.
    assert (
        after.split("## Status History")[0].split("---\n", 2)[2]
        == (before.split("## Status History")[0].split("---\n", 2)[2])
    )


def test_done_needs_an_identity(vault):
    client, headers = make_client(vault, identity=None)
    before = (vault / REVIEW).read_bytes()
    response = move(client, headers, REVIEW, "done", version(vault, REVIEW))
    assert response.status_code == 400
    assert "--identity" in response.json()["detail"]
    assert (vault / REVIEW).read_bytes() == before


def test_done_needs_the_history_to_end_with_the_move_into_review(api, vault):
    client, headers = api
    text = (
        (vault / REVIEW)
        .read_text()
        .replace("- 2031-04-09T11:00:00Z — in-progress → in-review\n", "")
    )
    (vault / REVIEW).write_text(text)
    response = move(client, headers, REVIEW, "done", version(vault, REVIEW))
    assert response.status_code == 400
    assert "doesn't end with its move into review" in response.json()["detail"]
    assert (vault / REVIEW).read_text() == text


def test_a_parent_with_open_sub_tasks_cant_be_done(api, vault):
    client, headers = api
    text = (
        (vault / PARENT)
        .read_text()
        .replace("status: in-progress", "status: in-review")
        .replace(
            "— open → in-progress\n",
            "— open → in-progress\n- 2031-04-15T10:00:00Z — in-progress → in-review\n",
        )
    )
    (vault / PARENT).write_text(text)
    response = move(client, headers, PARENT, "done", version(vault, PARENT))
    assert response.status_code == 400
    assert response.json()["detail"] == "This task has sub-tasks that aren't done yet."
    assert (vault / PARENT).read_text() == text

    # Once the open sub-task is done, the parent can close.
    child = "Tasks/Set up beta feedback form.md"
    for to in ["in-progress", "in-review", "done"]:
        assert move(client, headers, child, to, version(vault, child)).status_code == 200
    assert move(client, headers, PARENT, "done", version(vault, PARENT)).status_code == 200


def test_closure_fields_already_there_are_kept(api, vault):
    client, headers = api
    text = (
        (vault / REVIEW)
        .read_text()
        .replace(
            "dateModified:",
            "completedDate: 2031-04-10T08:00:00Z\nclosedBy: someone\ntimeToCloseMinutes: 5\n"
            "dateModified:",
        )
    )
    (vault / REVIEW).write_text(text)
    assert move(client, headers, REVIEW, "done", version(vault, REVIEW)).status_code == 200
    meta = fields(vault, REVIEW)
    assert lifecycle.as_timestamp(meta["completedDate"]) == datetime(2031, 4, 10, 8, tzinfo=UTC)
    assert meta["closedBy"] == "someone"
    assert meta["timeToCloseMinutes"] == 5
    assert "closureSource" not in meta  # Onyx wrote no closure field


def test_a_date_only_completed_date_from_today_gets_the_time(api, vault):
    client, headers = api
    today = NOW.astimezone().date().isoformat()
    text = (
        (vault / REVIEW)
        .read_text()
        .replace("dateModified:", f"completedDate: {today}\ndateModified:")
    )
    (vault / REVIEW).write_text(text)
    assert move(client, headers, REVIEW, "done", version(vault, REVIEW)).status_code == 200
    assert lifecycle.as_timestamp(fields(vault, REVIEW)["completedDate"]) == NOW


def test_a_date_only_date_created_gives_no_duration(api, vault):
    client, headers = api
    text = (
        (vault / REVIEW)
        .read_text()
        .replace("dateCreated: 2031-04-09T09:30:00Z", "dateCreated: 2031-04-09")
    )
    (vault / REVIEW).write_text(text)
    assert move(client, headers, REVIEW, "done", version(vault, REVIEW)).status_code == 200
    meta = fields(vault, REVIEW)
    assert "timeToCloseMinutes" not in meta
    assert meta["closedBy"] == "sheikh"


# --- Shared rules -------------------------------------------------------------------------


def test_moves_are_refused_unless_writes_are_allowed(vault):
    client, headers = make_client(vault, allow_writes=False)
    before = (vault / OPEN).read_bytes()
    response = move(client, headers, OPEN, "in-progress", version(vault, OPEN))
    assert response.status_code == 403
    assert (vault / OPEN).read_bytes() == before


def test_moves_need_the_header_a_same_site_origin_and_a_session(api, vault):
    client, headers = api
    body = {"path": OPEN, "to": "in-progress", "version": version(vault, OPEN)}
    before = (vault / OPEN).read_bytes()
    no_header = {k: v for k, v in headers.items() if k != "X-Onyx-Request"}
    assert client.post("/api/task/move", json=body, headers=no_header).status_code == 403
    foreign = {**headers, "Origin": "http://evil.example"}
    assert client.post("/api/task/move", json=body, headers=foreign).status_code == 403
    client.cookies.clear()
    no_session = {k: v for k, v in headers.items() if k != "Cookie"}
    assert client.post("/api/task/move", json=body, headers=no_session).status_code == 401
    assert (vault / OPEN).read_bytes() == before


@pytest.mark.parametrize(
    "body",
    [
        {"path": OPEN, "to": "later", "version": "0" * 64},
        {"path": OPEN, "to": "in-progress"},
        {"path": OPEN, "to": "in-progress", "version": "x"},
        {"path": OPEN, "to": "in-progress", "version": "0" * 64, "extra": 1},
    ],
)
def test_invalid_requests_are_422(api, vault, body):
    client, headers = api
    assert client.post("/api/task/move", json=body, headers=headers).status_code == 422


@pytest.mark.parametrize("path", ["../x.md", ".obsidian/x.md", "Tasks/Nope.md"])
def test_only_listed_tasks_are_found(api, vault, path):
    client, headers = api
    assert move(client, headers, path, "in-progress", "0" * 64).status_code == 404


def test_app_settings_say_whether_writes_are_on_and_who_signs_off(vault):
    client, headers = make_client(vault)
    assert client.get("/api/app-settings", headers=headers).json() == {
        "writable": True,
        "identity": "sheikh",
    }
    client, headers = make_client(DEV_VAULT, allow_writes=False, identity=None)
    assert client.get("/api/app-settings", headers=headers).json() == {
        "writable": False,
        "identity": None,
    }


@pytest.mark.parametrize("name", ["", " ", "a" * 65, "-x", "sheikh\nx", "a:b", "**x", "名前"])
def test_identity_must_be_a_plain_name(vault, name):
    with pytest.raises(ConfigError):
        load_settings(vault, PORT, identity=name)


def test_identity_is_trimmed(vault):
    assert load_settings(vault, PORT, identity="  Sheikh M  ").identity == "Sheikh M"
