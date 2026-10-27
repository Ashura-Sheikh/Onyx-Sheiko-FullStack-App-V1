"""Search by title and content, from the SQLite cache (FTS5)."""

import os
import stat

import pytest
from fastapi.testclient import TestClient

from onyx.app import create_app
from onyx.cache import NoteCache, fts_query, snippet_parts
from onyx.config import load_settings
from onyx.vault import Vault
from tests.test_security_baseline import BASE, DEV_VAULT, OK, PORT, sign_in, with_session
from tests.test_summary import task, write


@pytest.fixture
def make(tmp_path):
    def build(files: dict[str, str]) -> NoteCache:
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir(exist_ok=True)
        for name, text in files.items():
            write(vault_dir, name, text)
        cache = NoteCache(Vault(vault_dir), tmp_path / "cache")
        cache.rebuild()
        return cache

    return build


def titles(results):
    return [r["title"] for r in results]


# --- The query --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("atlas", '"atlas"*'),
        ("Atlas plan", '"Atlas"* "plan"*'),
        ('atlas" OR body:*', '"atlas"* "OR"* "body"*'),
        ("NEAR(a b) -c ^d", '"NEAR"* "a"* "b"* "c"* "d"*'),
        ("café", '"café"*'),
        ("   ", None),
        ('"*()^-:', None),
    ],
)
def test_user_text_becomes_plain_prefix_words(text, query):
    assert fts_query(text) == query


def test_query_is_limited_to_ten_words():
    assert fts_query(" ".join(f"w{n}" for n in range(30))).count('"') == 20


def test_snippet_parts():
    assert snippet_parts("a \x02b\x03 c") == [
        {"text": "a ", "match": False},
        {"text": "b", "match": True},
        {"text": " c", "match": False},
    ]


# --- Matching -----------------------------------------------------------------------


def test_finds_by_title_and_by_content(make):
    cache = make(
        {"Atlas.md": "# Atlas\n\nPlans.\n", "Other.md": "# Other\n\nAbout the atlas project.\n"}
    )
    assert titles(cache.search("atlas")) == ["Atlas", "Other"]  # title match ranks first
    assert titles(cache.search("project")) == ["Other"]


def test_words_match_as_prefixes_ignoring_case_and_accents(make):
    cache = make({"a.md": "# Café\n\nRésumé of PLANNING.\n"})
    assert titles(cache.search("cafe")) == ["Café"]
    assert titles(cache.search("resume plan")) == ["Café"]
    assert cache.search("planz") == []


def test_every_word_must_match(make):
    cache = make({"a.md": "# A\n\nred apple\n", "b.md": "# B\n\nred pear\n"})
    assert titles(cache.search("red apple")) == ["A"]


def test_typed_operators_cannot_change_the_query(make):
    cache = make({"a.md": "# A\n\nalpha\n", "b.md": "# B\n\nbeta\n"})
    assert titles(cache.search("alpha OR beta")) == []  # OR is a word here, not an operator
    assert cache.search('"') == []
    assert cache.search("title:alpha") == []


def test_snippet_marks_the_match_and_is_plain_text(make):
    cache = make({"a.md": "# A\n\nThe <b>quick</b> fox \x02jumps\x03.\n"})
    result = cache.search("fox")[0]
    assert {"text": "fox", "match": True} in result["snippet"]
    joined = "".join(p["text"] for p in result["snippet"])
    assert "<b>quick</b>" in joined  # stored as text; React shows it as text
    assert not any(
        p["match"] and p["text"] == "jumps" for p in result["snippet"]
    )  # can't fake a match


def test_frontmatter_title_heading_and_hidden_sections_are_not_searched(make):
    text = (
        task(history="- 2031-04-13T11:00:00Z — created → open\n") + "\n## Context\n\nsecretword\n"
    )
    cache = make({"t.md": text.replace("tags:\n  - task", "tags:\n  - task\n  - zebra")})
    assert cache.search("zebra") == []  # frontmatter
    assert cache.search("secretword") == []  # Context
    assert cache.search("created") == []  # Status History
    result = cache.search("task")[0]  # the title is still found
    assert result["kind"] == "task"


def test_results_say_what_they_are(make):
    cache = make({"Projects/a.md": "# A\n\nword\n"})
    assert cache.search("word") == [
        {
            "path": "Projects/a.md",
            "title": "A",
            "kind": "note",
            "folder": "Projects",
            "snippet": [{"text": "word", "match": True}],
        }
    ]


def test_results_are_limited(make):
    cache = make({f"n{i:02d}.md": "# N\n\nshared\n" for i in range(30)})
    assert len(cache.search("shared")) == 20


# --- Keeping up with the files ------------------------------------------------------------


def test_changes_on_disk_are_found_without_a_restart(make, tmp_path):
    cache = make({"a.md": "# A\n\nold words\n"})
    path = tmp_path / "vault" / "a.md"
    path.write_text("# A\n\nnew words, longer\n")
    assert titles(cache.search("new")) == ["A"]
    assert cache.search("old") == []
    write(tmp_path / "vault", "b.md", "# B\n\nnew too\n")
    assert sorted(titles(cache.search("new"))) == ["A", "B"]
    os.remove(tmp_path / "vault" / "b.md")
    assert titles(cache.search("new")) == ["A"]


def test_a_change_with_the_same_size_is_found(make, tmp_path):
    cache = make({"a.md": "# A\n\naaaa\n"})
    path = tmp_path / "vault" / "a.md"
    before = path.stat().st_mtime_ns
    path.write_text("# A\n\nbbbb\n")
    os.utime(path, ns=(before + 10**9, before + 10**9))
    assert titles(cache.search("bbbb")) == ["A"]


def test_unchanged_files_are_not_read_again(make, tmp_path, monkeypatch):
    cache = make({"a.md": "# A\n\nx\n", "b.md": "# B\n\ny\n"})
    reads = []
    original = cache.vault.read
    monkeypatch.setattr(cache.vault, "read", lambda name: reads.append(name) or original(name))
    cache.search("x")
    assert reads == []


def test_a_file_that_is_not_utf8_is_skipped(make, tmp_path):
    (tmp_path / "vault").mkdir()
    (tmp_path / "vault" / "bad.md").write_bytes(b"\xff\xfe nope")
    cache = make({"good.md": "# Good\n\nfine\n"})
    assert titles(cache.search("fine")) == ["Good"]
    assert cache.paths() == ["good.md"]


def test_cache_stays_private_after_searching(make, tmp_path):
    cache = make({"a.md": "# A\n\nx\n"})
    cache.search("x")
    assert stat.S_IMODE(cache.path.stat().st_mode) == 0o600


# --- The endpoint -------------------------------------------------------------------------


@pytest.fixture
def app():
    return create_app(load_settings(DEV_VAULT, PORT))


def test_search_endpoint(app):
    client = TestClient(app, base_url=BASE)
    assert client.get("/api/search?q=atlas", headers=OK).status_code == 401
    session = sign_in(client, app)
    results = client.get("/api/search?q=atlas", headers=with_session(session)).json()["results"]
    assert "Atlas" in results[0]["title"]  # a title match ranks first
    assert "Atlas kickoff" in [r["title"] for r in results]
    assert {r["kind"] for r in results} == {"note", "task"}
    hostile = client.get("/api/search?q=alert", headers=with_session(session)).json()["results"]
    assert [r["title"] for r in hostile] == ["Hostile content"]
    assert client.get("/api/search?q=", headers=with_session(session)).status_code == 422
    too_long = "a" * 201
    assert client.get(f"/api/search?q={too_long}", headers=with_session(session)).status_code == 422
    assert client.get("/api/search?q=%22*", headers=with_session(session)).json() == {"results": []}
