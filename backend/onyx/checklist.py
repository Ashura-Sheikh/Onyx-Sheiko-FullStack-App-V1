"""A task's sub-tasks and description, read from and written into its body.

Sub-tasks are the task's own checklist lines ("- [ ] …", ticked "- [x] …"),
as in the old Onyx app and in Obsidian (Sheikh's decision on #40, replacing
separate sub-task files). A checklist line counts wherever it is in the body,
except inside a code block and under the Status History and Context headings.

The description is the text at the top of the body: everything before the
first "## " heading, without a leading "# Title" heading and without the
checklist lines.

Everything here works on the body text only (no frontmatter, "\\n" line
endings); onyx.task_writes handles the file, its version and line endings.
Writes change only the lines they're about: ticking changes one character,
adding inserts one line, and a new description replaces only the top text.
"""

import re
from dataclasses import dataclass

# Sections that belong to the lifecycle, not to the task's own content.
LIFECYCLE_SECTIONS = ("Status History", "Context")
MAX_ITEMS_SHOWN = 200
MAX_ITEM_CHARS = 300
MAX_SUMMARY_CHARS = 160

_ITEM = re.compile(r"^(\s*[-*+]\s+\[)([ xX])(\]\s+)(\S.*?)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


@dataclass(frozen=True)
class Item:
    text: str
    done: bool


def _item_lines(lines: list[str]) -> list[int]:
    """Indexes of checklist lines, outside code blocks and lifecycle sections."""
    found, in_code, skip_level = [], False, None
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and heading.group(2) in LIFECYCLE_SECTIONS:
                skip_level = level
            continue
        if skip_level is None and _ITEM.match(line):
            found.append(index)
    return found


def _lead_end(lines: list[str]) -> int:
    """Where the top text ends: the first "#"/"##" heading after the first
    line of text (a "# Title" first line stays in it), outside code blocks."""
    in_code, seen_text = False, False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            in_code = not in_code
        if not in_code:
            heading = _HEADING.match(line)
            if heading and len(heading.group(1)) <= 2 and (seen_text or len(heading.group(1)) == 2):
                return index
        if line.strip():
            seen_text = True
    return len(lines)


def _title_line(lines: list[str], end: int) -> int | None:
    """The index of a "# Title" heading that is the first line of text, if any."""
    for index in range(end):
        if lines[index].strip():
            heading = _HEADING.match(lines[index])
            return index if heading and len(heading.group(1)) == 1 else None
    return None


def items(body: str) -> list[Item]:
    lines = body.split("\n")
    out = []
    for index in _item_lines(lines)[:MAX_ITEMS_SHOWN]:
        match = _ITEM.match(lines[index])
        out.append(Item(match.group(4), match.group(2) != " "))
    return out


def counts(body: str) -> tuple[int, int]:
    """(done, total) over every checklist line."""
    lines = body.split("\n")
    marks = [_ITEM.match(lines[i]).group(2) != " " for i in _item_lines(lines)]
    return sum(marks), len(marks)


def description(body: str) -> str:
    lines = body.split("\n")
    end = _lead_end(lines)
    skip = set(_item_lines(lines))
    title = _title_line(lines, end)
    if title is not None:
        skip.add(title)
    return "\n".join(line for i, line in enumerate(lines[:end]) if i not in skip).strip()


def summary_line(body: str) -> str | None:
    """The description's first line, for a card."""
    for line in description(body).split("\n"):
        text = line.strip().lstrip("#>*-+ ").strip()
        if text:
            return text if len(text) <= MAX_SUMMARY_CHARS else text[: MAX_SUMMARY_CHARS - 1] + "…"
    return None


def without_items(body: str) -> str:
    """The body with its checklist lines taken out (they're shown as sub-tasks)."""
    lines = body.split("\n")
    skip = set(_item_lines(lines))
    return "\n".join(line for i, line in enumerate(lines) if i not in skip)


# --- Writing ------------------------------------------------------------------------------


class ChecklistError(ValueError):
    """`code` says why; onyx.task_writes turns it into a fixed sentence."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def clean_item_text(text: str) -> str:
    single = text.strip()
    if not single:
        raise ChecklistError("item-empty")
    # One line: a newline is a control character, so it's refused here too.
    if len(single) > MAX_ITEM_CHARS or any(ord(c) < 32 or ord(c) == 127 for c in single):
        raise ChecklistError("item-text")
    return single


def add_item(body: str, text: str) -> str:
    """One unticked line: after the last checklist line, or at the end of the top text."""
    line = f"- [ ] {clean_item_text(text)}"
    lines = body.split("\n")
    found = _item_lines(lines)
    if found:
        lines.insert(found[-1] + 1, line)
        return "\n".join(lines)
    end = _lead_end(lines)
    floor = 1 if lines[0] == "" and end > 0 else 0  # the blank line after the frontmatter
    at = end
    while at > floor and lines[at - 1].strip() == "":
        at -= 1
    block = ([""] if at > 0 and lines[at - 1].strip() else []) + [line]
    has_heading = end < len(lines)
    if has_heading:
        block.append("")  # a blank line before the next heading
    lines[at:end] = block
    out = "\n".join(lines)
    return out if has_heading or out.endswith("\n") else out + "\n"


def set_item(body: str, index: int, done: bool) -> str:
    """Tick or untick the checklist line at `index` (0 = the first)."""
    lines = body.split("\n")
    found = _item_lines(lines)
    if not 0 <= index < len(found):
        raise ChecklistError("item-gone")
    match = _ITEM.match(lines[found[index]])
    mark = "x" if done else " "
    if (match.group(2) != " ") == done:
        return body
    start = match.start(2)
    line = lines[found[index]]
    lines[found[index]] = line[:start] + mark + line[start + 1 :]
    return "\n".join(lines)


MAX_DESCRIPTION_CHARS = 20_000


def clean_description(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(cleaned) > MAX_DESCRIPTION_CHARS:
        raise ChecklistError("description-long")
    in_code = False
    for line in cleaned.split("\n"):
        if _FENCE.match(line):
            in_code = not in_code
        heading = None if in_code else _HEADING.match(line)
        if heading and len(heading.group(1)) <= 2:
            raise ChecklistError("description-heading")
    if any(ord(c) < 32 and c not in "\n\t" for c in cleaned):
        raise ChecklistError("description-character")
    return cleaned


def with_description(body: str, text: str) -> str:
    """Replace the top text with `text`. A "# Title" first line and the
    checklist lines in the top text stay, in order, below the description.
    Everything from the first "## " heading on is unchanged."""
    new = clean_description(text)
    if new == description(body):
        return body
    lines = body.split("\n")
    end = _lead_end(lines)
    title = _title_line(lines, end)
    kept_items = [lines[i] for i in _item_lines(lines) if i < end]
    lead: list[str] = [""] if lines[0] == "" and end > 0 else []
    if title is not None:
        lead += [lines[title], ""]
    if new:
        lead += [*new.split("\n"), ""]
    if kept_items:
        lead += [*kept_items, ""]
    rest = lines[end:]
    if not rest:
        joined = "\n".join(lead).strip("\n")
        return ("\n" if lead[:1] == [""] else "") + joined + "\n" if joined else ""
    return "\n".join(lead + rest)
