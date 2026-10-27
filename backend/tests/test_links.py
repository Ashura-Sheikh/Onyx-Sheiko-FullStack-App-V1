"""Wikilinks: finding, resolving, backlinks and related tasks."""

import pytest

from onyx import links, summary
from onyx.vault import Vault
from tests.test_summary import task, write


def test_finds_links_in_order_with_text_and_headings_dropped():
    body = "See [[Atlas]] and [[Harbor#Plan|the plan]], then [[Folder/Deep note]]."
    assert links.find_links(body) == ["Atlas", "Harbor", "Folder/Deep note"]


def test_links_in_code_are_not_links():
    body = "`[[inline]]` real [[One]]\n```\n[[fenced]]\n```\n~~~\n[[tilde]]\n~~~\nafter [[Two]]"
    assert links.find_links(body) == ["One", "Two"]


@pytest.mark.parametrize(
    "text", ["[[]]", "[[ ]]", "[[#Heading]]", "[[a\nb]]", "[[" + "x" * 301 + "]]"]
)
def test_empty_or_broken_links_are_ignored(text):
    assert links.find_links(text) == []


def test_link_from_frontmatter_value():
    assert links.link_from_value("[[Atlas architecture]]") == "Atlas architecture"
    assert links.link_from_value("[[Harbor|Harbor project]]") == "Harbor"
    assert links.link_from_value("Plain text") is None


INDEX = links.LinkIndex(
    [
        "Projects/Atlas.md",
        "Archive/Atlas.md",
        "Archive/Old/Atlas.md",
        "Inbox.md",
        "Deep/Folder/Note.md",
    ]
)


def test_a_target_names_a_file_ignoring_case():
    assert INDEX.resolve("inbox", "Projects/x.md") == "Inbox.md"
    assert INDEX.resolve("Inbox.md", "x.md") == "Inbox.md"


def test_same_folder_wins_then_shortest_path():
    assert INDEX.resolve("Atlas", "Archive/Old/x.md") == "Archive/Old/Atlas.md"
    assert INDEX.resolve("Atlas", "Archive/x.md") == "Archive/Atlas.md"
    assert INDEX.resolve("Atlas", "Inbox.md") == "Archive/Atlas.md"  # shortest, then alphabetical


def test_a_target_with_a_folder_must_match_the_path_end():
    assert INDEX.resolve("Old/Atlas", "Inbox.md") == "Archive/Old/Atlas.md"
    assert INDEX.resolve("Folder/Note", "x.md") == "Deep/Folder/Note.md"
    assert INDEX.resolve("Other/Note", "x.md") is None
    assert INDEX.resolve("lder/Note", "x.md") is None


def test_unknown_targets_resolve_to_nothing():
    assert INDEX.resolve("Missing", "x.md") is None
    assert INDEX.resolve("../Inbox", "x.md") is None
    assert INDEX.resolve("x" * 400, "x.md") is None


def test_backlinks_and_related_tasks(tmp_path):
    write(tmp_path, "Projects/Atlas.md", "# Atlas\n\nSee [[Inbox]] and [[Nowhere]].\n")
    write(tmp_path, "Inbox.md", "# Inbox\n\nAbout [[Atlas]].\n")
    write(tmp_path, "Journal.md", "# Journal\n\n`[[Atlas]]` in code only.\n")
    extra = 'projects:\n  - "[[Atlas]]"\n'
    write(
        tmp_path,
        "Tasks/Plan.md",
        task(status="in-review", extra=extra).replace("A task", "Plan it"),
    )
    write(
        tmp_path,
        "Tasks/Body.md",
        task().replace("# A task\n", "# A task\n\nFor [[Projects/Atlas]].\n"),
    )
    write(tmp_path, "Tasks/Other.md", task())
    detail = summary.note_detail(Vault(tmp_path), "Projects/Atlas.md")
    assert detail["links"] == {"Inbox": "Inbox.md", "Nowhere": None}
    assert detail["backlinks"] == [{"path": "Inbox.md", "title": "Inbox"}]
    assert detail["related_tasks"] == [
        {"path": "Tasks/Body.md", "title": "A task", "status": "open"},
        {"path": "Tasks/Plan.md", "title": "Plan it", "status": "in-review"},
    ]


def test_a_note_linking_to_itself_is_not_its_own_backlink(tmp_path):
    write(tmp_path, "a.md", "# A\n\n[[a]]\n")
    detail = summary.note_detail(Vault(tmp_path), "a.md")
    assert detail["links"] == {"a": "a.md"}
    assert detail["backlinks"] == []


def test_links_in_hidden_sections_are_not_listed(tmp_path):
    text = (
        task(history="- 2031-04-13T11:00:00Z — created → open\n") + "\n## Context\n\n[[Hidden]]\n"
    )
    write(tmp_path, "t.md", text)
    write(tmp_path, "Hidden.md", "# Hidden\n")
    assert summary.note_detail(Vault(tmp_path), "t.md")["links"] == {}


def test_notes_list_has_notes_only_with_their_tags(tmp_path):
    write(tmp_path, "b.md", "---\ntags: [atlas]\n---\n# B\n")
    write(tmp_path, "Folder/a.md", "# A\n")
    write(tmp_path, "t.md", task())
    listed = summary.notes_list(summary.read_summary(Vault(tmp_path)))
    assert [(n["path"], n["folder"], n["tags"]) for n in listed] == [
        ("Folder/a.md", "Folder", []),
        ("b.md", "", ["atlas"]),
    ]


def test_dev_vault_links():
    from tests.test_security_baseline import DEV_VAULT

    detail = summary.note_detail(Vault(DEV_VAULT), "Projects/Atlas kickoff.md")
    assert detail["links"] == {
        "Atlas architecture": "Projects/Atlas architecture.md",
        "Release checklist": "Reference/Release checklist.md",
    }
    assert {b["title"] for b in detail["backlinks"]} >= {"Atlas architecture"}
    assert detail["related_tasks"]  # tasks list it in `projects`


def test_notes_endpoint():
    from fastapi.testclient import TestClient

    from onyx.app import create_app
    from onyx.config import load_settings
    from tests.test_security_baseline import BASE, DEV_VAULT, OK, PORT, sign_in, with_session

    app = create_app(load_settings(DEV_VAULT, PORT))
    client = TestClient(app, base_url=BASE)
    assert client.get("/api/notes", headers=OK).status_code == 401
    session = sign_in(client, app)
    notes = client.get("/api/notes", headers=with_session(session)).json()["notes"]
    assert set(notes[0]) == {"path", "title", "folder", "updated", "tags"}
    assert not any(n["path"].startswith("Tasks/") for n in notes)
    kickoff = next(n for n in notes if n["path"] == "Projects/Atlas kickoff.md")
    assert kickoff["tags"] == ["atlas", "planning"]
