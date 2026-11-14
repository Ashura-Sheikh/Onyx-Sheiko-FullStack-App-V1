"""The Tasks board and list (#9 part (a)): every task with its projects,
description and sub-tasks. Read-only.

Sub-tasks are the task's own checklist lines (Sheikh's decision on #40,
replacing separate sub-task files). A `projects` link to another task (a
handoff linking back, say) isn't shown as a project."""

import pytest
from fastapi.testclient import TestClient

from onyx import summary
from onyx.app import create_app
from onyx.config import load_settings
from onyx.vault import Vault
from tests.test_security_baseline import BASE, DEV_VAULT, OK, PORT, sign_in, with_session


def task(
    status="open", tags=("task",), projects=(), due=None, priority=None, title=None, body="body\n"
):
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
    return "\n".join(lines) + body


def board(tmp_path, files: dict[str, str]) -> dict[str, dict]:
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    cards = summary.task_board(summary.read_summary(Vault(tmp_path)))
    return {c["path"]: c for c in cards}


CHECKLIST_BODY = """What it's about, **in short**.
More text.

- [ ] Draft
- [x] Review
  * [X] Nested counts too

```
- [ ] in a code block
```

## Notes

- [ ] in another section

## Status History

- [ ] in the history
"""


def test_sub_tasks_are_the_checklist_lines_and_the_description_is_the_top_text(tmp_path):
    cards = board(tmp_path, {"T.md": task(title="T", body=CHECKLIST_BODY)})
    assert cards["T.md"]["checklist"] == [
        {"text": "Draft", "done": False},
        {"text": "Review", "done": True},
        {"text": "Nested counts too", "done": True},
        {"text": "in another section", "done": False},
    ]
    assert cards["T.md"]["description"] == "What it's about, **in short**."


def test_no_checklist_and_no_description(tmp_path):
    cards = board(tmp_path, {"T.md": task(body="\n## Status History\n\n- x\n")})
    assert cards["T.md"]["checklist"] == []
    assert cards["T.md"]["description"] is None


def test_a_long_first_line_is_shortened_for_the_card(tmp_path):
    cards = board(tmp_path, {"T.md": task(body="x" * 500 + "\n")})
    assert len(cards["T.md"]["description"]) == 160
    assert cards["T.md"]["description"].endswith("…")


def test_a_link_to_a_task_is_not_a_project(tmp_path):
    # Like a handoff or sign-off note linking back to its task (486 such links
    # in the real vault).
    cards = board(
        tmp_path,
        {
            "Parent.md": task(),
            "Note.md": "a note\n",
            "Handoff.md": task(projects=["[[Parent]]", "[[Note]]", "[[Not written yet]]"]),
        },
    )
    assert cards["Handoff.md"]["projects"] == ["Note", "Not written yet"]


def test_links_in_the_body_are_not_projects(tmp_path):
    cards = board(tmp_path, {"Note.md": "a note\n", "T.md": task(body="See [[Note]].\n")})
    assert cards["T.md"]["projects"] == []


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
    assert cards["Launch Atlas beta"]["checklist"] == [
        {"text": "Write the beta invite", "done": True},
        {"text": "Book a demo slot", "done": False},
    ]
    # Links to another task: not a project.
    assert cards["Prepare Harbor demo"]["projects"] == ["Harbor retrospective"]
    assert cards["Write beta invite text"]["projects"] == []


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
        "description": "Made-up task with sub-tasks, for development and tests. Its sub-tasks "
        "are its checklist lines.",
        "checklist": [
            {"text": "Write the beta invite", "done": True},
            {"text": "Book a demo slot", "done": False},
        ],
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
