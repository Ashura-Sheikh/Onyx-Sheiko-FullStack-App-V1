"""The editor's preview hides the same parts of a note as the Read view.

frontend/src/readView.ts repeats the rules of frontmatter.without_sections and
without_first_heading (with summary.HIDDEN_SECTIONS). Both sides are checked
against the same cases in frontend/src/readView.cases.json, so a change on
one side that isn't made on the other fails a test."""

import json

from onyx import frontmatter
from onyx.config import REPO_ROOT
from onyx.summary import HIDDEN_SECTIONS

CASES = json.loads((REPO_ROOT / "frontend" / "src" / "readView.cases.json").read_text("utf-8"))


def test_hidden_sections_match():
    assert CASES["hidden_sections"] == list(HIDDEN_SECTIONS)


def test_each_case_gives_what_the_read_view_shows():
    assert len(CASES["cases"]) >= 10
    for case in CASES["cases"]:
        shown = frontmatter.without_first_heading(
            frontmatter.without_sections(case["body"], HIDDEN_SECTIONS), case["title"]
        ).strip("\n")
        assert shown == case["shown"], case
