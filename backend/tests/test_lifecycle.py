"""Sheiko's formats and section rules, and line-by-line frontmatter edits
(#9 part (b)). Formats checked against Sheiko 0.2.5 (src/lifecycle.ts,
src/signoff-record.ts)."""

from datetime import UTC, datetime

import pytest

from onyx import frontmatter, lifecycle
from onyx.lifecycle import FieldEditRefused, append_to_section, set_fields

AT = datetime(2031, 4, 16, 9, 30, 15, 123456, tzinfo=UTC)


# --- Times and lines ----------------------------------------------------------------------


def test_local_iso_has_the_offset_and_whole_seconds():
    text = lifecycle.local_iso(AT)
    assert "." not in text
    assert text[-6] in "+-" and text[-3] == ":"
    assert datetime.fromisoformat(text) == AT.replace(microsecond=0)


def test_history_and_context_lines_match_sheiko():
    t = lifecycle.local_iso(AT)
    assert lifecycle.history_line(AT, "open", "in-progress") == f"- {t} — open → in-progress"
    assert (
        lifecycle.history_line(AT, "in-review", "done", f"signed off by sheikh at {t}")
        == f"- {t} — in-review → done (signed off by sheikh at {t})"
    )
    assert (
        lifecycle.context_line(AT, "sheikh", "Signed off (not closed)")
        == f"- **{t} — sheikh:** Signed off (not closed)"
    )
    assert lifecycle.context_line(AT, "sheikh", "two\n  lines") == f"- **{t} — sheikh:** two lines"


def test_entry_tests():
    assert lifecycle.is_history_entry("- 2031-04-16T09:00:00Z — open → in-progress")
    assert lifecycle.is_history_entry("  - 2031-04-16T09:00:00+01:00 — created → open  ")
    assert not lifecycle.is_history_entry("- a note typed under the heading")
    assert lifecycle.is_context_entry("- **2031-04-16T09:00:00Z — sheikh:** Reviewed")
    assert not lifecycle.is_context_entry("- **Bold** text")


def test_timestamps_are_never_guessed():
    assert lifecycle.as_timestamp("2031-04-16T09:00:00Z") == datetime(2031, 4, 16, 9, tzinfo=UTC)
    assert lifecycle.as_timestamp("2031-04-16") is None
    assert lifecycle.as_timestamp(datetime(2031, 4, 16).date()) is None
    assert lifecycle.as_timestamp("soon") is None
    assert lifecycle.as_timestamp(None) is None
    assert lifecycle.is_date_only("2031-04-16") and lifecycle.is_date_only(AT.date())
    assert not lifecycle.is_date_only("2031-04-16T09:00:00Z")


def test_last_move_is_the_latest_by_time_not_by_position():
    body = (
        "## Status History\n\n"
        "- 2031-04-16T10:00:00Z — in-progress → in-review\n"
        "- 2031-04-16T09:00:00Z — open → in-progress\n"
        "\n## Next\n- 2031-04-17T09:00:00Z — in-review → done\n"
    )
    assert lifecycle.last_move_to(body) == "in-review"  # and the line under ## Next isn't in it
    assert lifecycle.last_move_to("no history\n") is None
    same_second = (
        "## Status History\n"
        "- 2031-04-16T09:00:00Z — open → in-progress\n"
        "- 2031-04-16T09:00:00Z — in-progress → in-review\n"
    )
    assert lifecycle.last_move_to(same_second) == "in-review"


# --- Sections (Sheiko's appendToSection) ---------------------------------------------------

LINE = "- NEW"


def add(content):
    return append_to_section(content, "## Status History", LINE, lifecycle.is_history_entry)


def test_goes_after_the_last_entry_keeping_typed_text_below():
    content = (
        "# T\n\n## Status History\n\n"
        "- 2031-04-16T09:00:00Z — created → open\n\nSome text typed here.\n\n## Context\n"
    )
    assert add(content) == (
        "# T\n\n## Status History\n\n- 2031-04-16T09:00:00Z — created → open\n- NEW\n\n"
        "Some text typed here.\n\n## Context\n"
    )


def test_a_missing_section_is_added_at_the_end():
    assert add("# T\n\nbody\n\n\n") == "# T\n\nbody\n\n## Status History\n\n- NEW\n"


def test_no_entries_yet_goes_straight_under_the_heading():
    content = "## Status History\nA description typed here.\n## Next\n"
    assert add(content) == "## Status History\n\n- NEW\n\nA description typed here.\n## Next\n"


def test_an_empty_section_keeps_one_blank_line():
    assert add("## Status History\n## Next\n") == "## Status History\n\n- NEW\n## Next\n"


def test_a_deeper_heading_does_not_end_the_section_but_the_next_level_two_does():
    content = (
        "## Status History\n- 2031-04-16T09:00:00Z — created → open\n### Notes\n"
        "## Other\n- 2031-04-17T09:00:00Z — open → in-progress\n"
    )
    assert add(content) == (
        "## Status History\n- 2031-04-16T09:00:00Z — created → open\n- NEW\n### Notes\n"
        "## Other\n- 2031-04-17T09:00:00Z — open → in-progress\n"
    )


def test_only_the_exact_heading_counts():
    # Sheiko needs exactly "## Status History"; "### Status History" isn't it.
    assert add("### Status History\n- x\n").endswith("## Status History\n\n- NEW\n")


# --- Frontmatter fields ----------------------------------------------------------------------

NOTE = "---\ntags:\n  - task\nstatus: open\ndateModified: 2031-04-01T09:00:00Z\n---\n\n# T\n"


def test_changes_only_the_named_lines():
    changed = set_fields(NOTE, {"status": "in-progress"})
    assert changed == NOTE.replace("status: open", "status: in-progress")


def test_adds_a_missing_field_before_the_closing_line():
    changed = set_fields(NOTE, {"closedBy": "sheikh"})
    assert changed == NOTE.replace("---\n\n# T", "closedBy: sheikh\n---\n\n# T")


def test_keeps_windows_line_endings_and_a_byte_order_mark():
    note = "﻿" + NOTE.replace("\n", "\r\n")
    changed = set_fields(note, {"status": "done", "closedBy": "sheikh"})
    assert changed == "﻿" + NOTE.replace("status: open", "status: done").replace(
        "---\n\n# T", "closedBy: sheikh\n---\n\n# T"
    ).replace("\n", "\r\n")


def test_values_that_would_read_back_differently_are_quoted():
    for value in ["yes", "123", "a: b", "null", "#tag", " padded", ""]:
        changed = set_fields(NOTE, {"closedBy": value})
        assert frontmatter.split(changed)[0]["closedBy"] == value
    assert "closedBy: sheikh\n" in set_fields(NOTE, {"closedBy": "sheikh"})
    assert "timeToCloseMinutes: 90\n" in set_fields(NOTE, {"timeToCloseMinutes": 90})
    stamp = "2031-04-16T13:00:00+01:00"
    changed = set_fields(NOTE, {"completedDate": stamp})
    assert f"completedDate: {stamp}\n" in changed  # plain, as Obsidian writes it
    assert frontmatter.split(changed)[0]["completedDate"] == lifecycle.as_timestamp(stamp)


@pytest.mark.parametrize(
    ("note", "reason"),
    [
        ("no frontmatter\n", "no-frontmatter"),
        ("---\nstatus: open\nstatus: done\n---\n", "duplicate-field"),
        ("---\nstatus:\n  - open\n---\n", "block-field"),
        ("---\nstatus: |\n  open\n---\n", "block-field"),
        ("---\nstatus: open\n  continued\n---\n", "block-field"),
        ("---\nkey: [unclosed\nstatus: open\n---\n", "check-failed"),  # can't be checked
        ("---\n---\n", "check-failed"),  # nothing to check against
    ],
)
def test_refuses_what_it_cannot_change_safely(note, reason):
    with pytest.raises(FieldEditRefused) as error:
        set_fields(note, {"status": "done"})
    assert str(error.value) == reason


def test_a_look_alike_key_inside_another_value_is_not_touched():
    note = "---\nmeta:\n  status: secret\nstatus: open\n---\n"
    changed = set_fields(note, {"status": "done"})
    assert changed == "---\nmeta:\n  status: secret\nstatus: done\n---\n"


def test_the_check_after_the_edit_catches_a_wrong_result(monkeypatch):
    # If the line edit ever produced something else, the re-parse refuses it.
    monkeypatch.setattr(lifecycle, "yaml_scalar", lambda value: "[broken")
    with pytest.raises(FieldEditRefused):
        set_fields(NOTE, {"status": "done"})
