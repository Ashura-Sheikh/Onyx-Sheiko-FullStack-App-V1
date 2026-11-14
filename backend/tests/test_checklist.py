"""Sub-tasks (checklist lines) and the description, in a task's body
(onyx.checklist), and whole-field frontmatter edits (lifecycle.set_frontmatter)."""

from datetime import date

import pytest

from onyx import checklist, frontmatter, lifecycle
from onyx.checklist import Item

BODY = """
# Title

Top text.
- [ ] One
* [x] Two

```
- [ ] code
```

## Notes

  + [X] Three

## Status History

- [ ] history

## Context

- [ ] context
"""


def test_items_skip_code_blocks_and_lifecycle_sections():
    assert checklist.items(BODY) == [Item("One", False), Item("Two", True), Item("Three", True)]
    assert checklist.counts(BODY) == (2, 3)


def test_not_items():
    body = "- [ ]\n- [ ]   \n-[ ] x\n- [ ]x\n- [y] x\n1. [ ] x\n"
    assert checklist.items(body) == []


def test_description_is_the_top_text_without_title_or_items():
    # The code block is in the top text, so it's part of the description.
    assert checklist.description(BODY) == "Top text.\n\n```\n- [ ] code\n```"
    assert checklist.summary_line(BODY) == "Top text."
    assert checklist.description("\n## Status History\n") == ""
    assert checklist.summary_line("\n## Status History\n") is None
    # A heading that isn't the first line ends the top text, even a "# " one.
    assert checklist.description("Intro\n# Later\nmore\n") == "Intro"


def test_summary_line_drops_markdown_markers():
    assert checklist.summary_line("> quoted **bold**\n") == "quoted **bold**"


def test_without_items_keeps_everything_else():
    shown = checklist.without_items(BODY)
    assert "One" not in shown and "Three" not in shown
    assert "- [ ] code" in shown and "- [ ] history" in shown and "Top text." in shown


def test_add_after_the_last_item_even_in_a_later_section():
    out = checklist.add_item(BODY, "Four")
    assert "  + [X] Three\n- [ ] Four\n" in out
    assert out.replace("- [ ] Four\n", "", 1) == BODY


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("", "\n- [ ] x\n"),
        ("\n", "\n- [ ] x\n"),
        ("\nText", "\nText\n\n- [ ] x\n"),
        ("\nText\n\n\n## H\n", "\nText\n\n- [ ] x\n\n## H\n"),
        ("\n## H\n", "\n- [ ] x\n\n## H\n"),
        ("\n# Title\n\n## H\n", "\n# Title\n\n- [ ] x\n\n## H\n"),
    ],
)
def test_the_first_item_goes_at_the_end_of_the_top_text(body, expected):
    assert checklist.add_item(body, "x") == expected


def test_set_item_changes_one_character():
    out = checklist.set_item(BODY, 0, True)
    assert out == BODY.replace("- [ ] One", "- [x] One")
    assert checklist.set_item(out, 0, False) == BODY
    assert checklist.set_item(BODY, 1, True) == BODY  # already ticked
    with pytest.raises(checklist.ChecklistError):
        checklist.set_item(BODY, 3, True)
    with pytest.raises(checklist.ChecklistError):
        checklist.set_item(BODY, -1, True)


def test_with_description_keeps_title_items_and_later_sections():
    out = checklist.with_description(BODY, "New\n\ntext")
    assert out.startswith("\n# Title\n\nNew\n\ntext\n\n- [ ] One\n* [x] Two\n\n## Notes\n")
    assert out.endswith(BODY[BODY.index("## Notes") :])
    assert checklist.description(out) == "New\n\ntext"
    # The same description: no rewrite, so the layout is kept exactly.
    assert checklist.with_description(BODY, checklist.description(BODY)) == BODY


def test_with_description_moves_a_code_block_only_if_it_is_in_the_top_text():
    out = checklist.with_description(BODY, "")
    assert checklist.items(out) == checklist.items(BODY)
    assert checklist.description(out) == ""


def test_clean_description():
    assert checklist.clean_description("  a\r\nb\r") == "a\nb"
    for bad in ["## x", "# x", "a\n## x"]:
        with pytest.raises(checklist.ChecklistError):
            checklist.clean_description(bad)
    with pytest.raises(checklist.ChecklistError):
        checklist.clean_description("x" * (checklist.MAX_DESCRIPTION_CHARS + 1))
    assert checklist.clean_description("```\n## not a heading\n```")


# --- set_frontmatter ---------------------------------------------------------------------------


def test_set_frontmatter_replaces_lists_and_removes_fields_keeping_other_lines():
    text = (
        "---\ntags:\n  - task\n  - old\nstatus: open\npriority: high\n"
        'projects:\n- "[[A]]"\nother: keep # comment\n---\nbody\n'
    )
    out = lifecycle.set_frontmatter(
        text,
        {"tags": ["task", "new"], "priority": None, "projects": ["[[B]]"], "due": date(2031, 5, 2)},
    )
    assert out == (
        "---\ntags:\n  - task\n  - new\nstatus: open\n"
        'projects:\n  - "[[B]]"\nother: keep # comment\ndue: 2031-05-02\n---\nbody\n'
    )


def test_set_frontmatter_keeps_crlf_and_bom():
    text = "﻿---\r\nstatus: open\r\ntags: [task]\r\n---\r\nbody\r\n"
    out = lifecycle.set_frontmatter(text, {"tags": ["task", "x"]})
    assert out == "﻿---\r\nstatus: open\r\ntags:\r\n  - task\r\n  - x\r\n---\r\nbody\r\n"


def test_set_frontmatter_refuses_a_duplicate_and_anything_that_reads_back_wrong():
    with pytest.raises(lifecycle.FieldEditRefused, match="duplicate-field"):
        lifecycle.set_frontmatter("---\na: 1\na: 2\n---\n", {"a": "3"})
    with pytest.raises(lifecycle.FieldEditRefused):
        lifecycle.set_frontmatter("no frontmatter\n", {"a": "3"})
    # A field whose next line is a nested mapping value: replaced whole.
    out = lifecycle.set_frontmatter("---\nm:\n  x: 1\nb: 2\n---\n", {"m": None})
    assert frontmatter.split(out)[0] == {"b": 2}
