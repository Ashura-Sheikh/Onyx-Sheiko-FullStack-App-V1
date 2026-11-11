"""The Tasks board and list (#9 part (a)): every task with its parent, sub-task
progress and projects. Read-only.

Parent and child (Sheikh's decision 1a on #9): a child is tagged `subtask`
and links to its parent task in `projects`. A `projects` link to a task
without that tag doesn't make a sub-task."""

import pytest
from fastapi.testclient import TestClient

from onyx import summary
from onyx.app import create_app
from onyx.config import load_settings
from onyx.vault import Vault
from tests.test_security_baseline import BASE, DEV_VAULT, OK, PORT, sign_in, with_session


def task(status="open", tags=("task",), projects=(), due=None, priority=None, title=None):
    lines = ["---", "tags:", *[f"  - {t}" for t in tags], f"status: {status}"]
    if priority:
        lines.append(f"priority: {priority}")
    if due:
        lines.append(f"due: {due}")
    if projects:
        lines += ["projects:", *[f'  - "{p}"' for p in projects]]
    lines += ["---", ""]
    if title:
        lines += [f"# {title}", ""]
    return "\n".join(lines) + "body\n"


def board(tmp_path, files: dict[str, str]) -> dict[str, dict]:
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    cards = summary.task_board(summary.read_summary(Vault(tmp_path)))
    return {c["path"]: c for c in cards}


def test_a_subtask_names_its_parent_and_the_parent_counts_its_children(tmp_path):
    cards = board(
        tmp_path,
        {
            "Parent.md": task("in-progress", projects=["[[Project note]]"]),
            "A.md": task("done", tags=("task", "subtask"), projects=["[[Parent]]"]),
            "B.md": task("open", tags=("task", "subtask"), projects=["[[Parent]]"]),
            "C.md": task("in-review", tags=("task", "subtask"), projects=["[[Parent]]"]),
            "Project note.md": "a note\n",
        },
    )
    assert cards["Parent.md"]["subtasks"] == {"done": 1, "total": 3}
    assert cards["Parent.md"]["parent"] is None
    assert cards["Parent.md"]["projects"] == ["Project note"]
    for child in ["A.md", "B.md", "C.md"]:
        assert cards[child]["parent"] == {"path": "Parent.md", "title": "Parent"}
        assert cards[child]["subtasks"] is None
        assert cards[child]["projects"] == []  # the parent link isn't a project


def test_a_link_to_a_task_without_the_subtask_tag_is_not_a_child(tmp_path):
    # Like a handoff or sign-off note linking back to its task (486 such links
    # in the real vault): neither a sub-task nor a project.
    cards = board(
        tmp_path,
        {
            "Parent.md": task(),
            "Handoff.md": task(projects=["[[Parent]]"]),
        },
    )
    assert cards["Handoff.md"]["parent"] is None
    assert cards["Handoff.md"]["projects"] == []
    assert cards["Parent.md"]["subtasks"] is None


def test_a_subtask_linking_to_a_note_has_no_parent(tmp_path):
    cards = board(
        tmp_path,
        {
            "Note.md": "a note\n",
            "Child.md": task(
                tags=("task", "subtask"), projects=["[[Note]]", "[[Not written yet]]"]
            ),
        },
    )
    assert cards["Child.md"]["parent"] is None
    assert cards["Child.md"]["projects"] == ["Note", "Not written yet"]


def test_links_in_the_body_are_neither_projects_nor_parents(tmp_path):
    cards = board(
        tmp_path,
        {
            "Parent.md": task(),
            "Note.md": "a note\n",
            "Child.md": task(tags=("task", "subtask")).replace(
                "body\n", "See [[Parent]] and [[Note]].\n"
            ),
        },
    )
    assert cards["Child.md"]["parent"] is None
    assert cards["Child.md"]["projects"] == []
    assert cards["Parent.md"]["subtasks"] is None


def test_a_subtask_with_two_task_links_takes_the_first_as_parent(tmp_path):
    cards = board(
        tmp_path,
        {
            "First.md": task(),
            "Second.md": task(),
            "Child.md": task(tags=("task", "subtask"), projects=["[[First]]", "[[Second]]"]),
        },
    )
    assert cards["Child.md"]["parent"]["path"] == "First.md"
    assert cards["First.md"]["subtasks"] == {"done": 0, "total": 1}
    assert cards["Second.md"]["subtasks"] is None
    assert cards["Child.md"]["projects"] == []


def test_a_subtask_linking_to_itself_has_no_parent(tmp_path):
    cards = board(tmp_path, {"Me.md": task(tags=("task", "subtask"), projects=["[[Me]]"])})
    assert cards["Me.md"]["parent"] is None
    assert cards["Me.md"]["subtasks"] is None


def test_parent_links_resolve_like_obsidian_by_file_name(tmp_path):
    # The link names the file, not the title.
    cards = board(
        tmp_path,
        {
            "Work/Big job.md": task(title="A different title"),
            "Work/Small step.md": task(tags=("task", "subtask"), projects=["[[Big job]]"]),
        },
    )
    assert cards["Work/Small step.md"]["parent"] == {
        "path": "Work/Big job.md",
        "title": "A different title",
    }


def test_order_is_stage_then_due_date_then_title_with_unknown_stages_last(tmp_path):
    cards = list(
        board(
            tmp_path,
            {
                # Due date beats the title: "b" is due first, "a" later, "c" never.
                "c.md": task("open"),
                "a.md": task("open", due="2031-04-20"),
                "b.md": task("open", due="2031-04-18"),
                "done.md": task("done"),
                "odd.md": task("someday"),
                "rev.md": task("in-review"),
            },
        )
    )
    assert cards == ["b.md", "a.md", "c.md", "rev.md", "done.md", "odd.md"]


def test_unknown_stage_and_priority_are_null(tmp_path):
    cards = board(tmp_path, {"odd.md": task("someday", priority="urgent")})
    assert cards["odd.md"]["status"] is None
    assert cards["odd.md"]["priority"] is None


def test_notes_are_not_on_the_board(tmp_path):
    cards = board(tmp_path, {"Note.md": "just a note\n", "T.md": task()})
    assert list(cards) == ["T.md"]


def test_dev_vault_board():
    cards = {c["title"]: c for c in summary.task_board(summary.read_summary(Vault(DEV_VAULT)))}
    assert len(cards) == 15
    assert cards["Launch Atlas beta"]["subtasks"] == {"done": 1, "total": 2}
    assert cards["Set up beta feedback form"]["parent"]["title"] == "Launch Atlas beta"
    assert cards["Write beta invite text"]["parent"]["title"] == "Launch Atlas beta"
    # Links to the parent without the subtask tag: not a child, not a project.
    assert cards["Prepare Harbor demo"]["parent"] is None
    assert cards["Prepare Harbor demo"]["projects"] == ["Harbor retrospective"]


# --- The endpoint ------------------------------------------------------------------------


@pytest.fixture
def client_and_headers():
    app = create_app(load_settings(DEV_VAULT, PORT))
    client = TestClient(app, base_url=BASE)
    return client, with_session(sign_in(client, app))


def test_tasks_endpoint(client_and_headers):
    client, headers = client_and_headers
    body = client.get("/api/tasks", headers=headers).json()
    assert len(body["tasks"]) == 15
    beta = next(t for t in body["tasks"] if t["title"] == "Launch Atlas beta")
    assert beta == {
        "path": "Tasks/Launch Atlas beta.md",
        "title": "Launch Atlas beta",
        "status": "in-progress",
        "priority": "high",
        "due": "2031-04-30",
        "projects": ["Atlas kickoff"],
        "parent": None,
        "subtasks": {"done": 1, "total": 2},
    }


def test_tasks_endpoint_needs_a_session():
    app = create_app(load_settings(DEV_VAULT, PORT))
    client = TestClient(app, base_url=BASE)
    assert client.get("/api/tasks", headers=OK).status_code == 401
    assert client.post("/api/tasks", headers=OK).status_code in (401, 405)


def test_a_hostile_title_is_returned_as_data(tmp_path):
    hostile = "<img src=x onerror=alert(1)>"
    cards = board(tmp_path, {"T.md": task(title=hostile)})
    assert cards["T.md"]["title"] == hostile
