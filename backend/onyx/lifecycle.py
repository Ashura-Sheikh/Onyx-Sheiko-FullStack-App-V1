"""Task stage moves and sign-off (#9 part (b)), in Sheiko's own formats.

The text formats and section rules here are ported from the Sheiko Task
Lifecycle plugin (0.2.5, src/lifecycle.ts and src/signoff-record.ts), so a
note Onyx changes reads the same to Sheiko, and the other way round:

- a Status History line:  "- <time> — <from> → <to>" plus " (<note>)" if any;
- a sign-off:             "- **<time> — <who>:** Signed off (not closed)" in ## Context;
- a close's note:         "signed off by <who> at <time>";
- times: local ISO 8601 with the offset, no fractions of a second;
- a line is added after the section's last entry (so text typed under the
  heading stays below), the section is created at the end if missing, and a
  section ends at the next "## " heading. Existing lines are never changed.

Frontmatter: only the fields being changed are touched, one top-level line
each, in the raw text; the YAML is never rebuilt. Afterwards it's parsed
again, and the change is refused unless the only differences are the
intended ones (this catches duplicate keys, look-alike keys inside other
values, and anything the line edit got wrong).
"""

import json
import re
from datetime import date, datetime

import yaml

from onyx import frontmatter

HISTORY_HEADING = "## Status History"
CONTEXT_HEADING = "## Context"
SIGNOFF_PHRASE = "Signed off (not closed)"

_HISTORY_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}T\S+) — (\S+) → (\S+)(.*)$")
_CONTEXT_LINE = re.compile(r"^- \*\*\d{4}-\d{2}-\d{2}T[^*]*:\*\* ")
_ISO_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}")


class FieldEditRefused(ValueError):
    """The frontmatter can't be changed safely line by line; nothing is written."""


# --- Times ------------------------------------------------------------------------


def local_iso(at: datetime) -> str:
    """2026-11-11T18:00:00+00:00: local time with its offset, whole seconds."""
    return at.astimezone().isoformat(timespec="seconds")


def as_timestamp(value: object) -> datetime | None:
    """A full timestamp from a frontmatter value; None for a date-only or other
    value. A time of day is never guessed (Sheiko's parseTimestamp)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.astimezone()
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value.strip()):
        try:
            found = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return found if found.tzinfo else found.astimezone()
    return None


def is_date_only(value: object) -> bool:
    if isinstance(value, date) and not isinstance(value, datetime):
        return True
    return isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()) is not None


# --- Lines and sections -----------------------------------------------------------------


def history_line(at: datetime, from_stage: str, to_stage: str, note: str | None = None) -> str:
    line = f"- {local_iso(at)} — {from_stage} → {to_stage}"
    return f"{line} ({note})" if note else line


def context_line(at: datetime, who: str, text: str) -> str:
    single = re.sub(r"\s*\n\s*", " ", text.strip())
    by = f" — {who.strip()}" if who.strip() else ""
    return f"- **{local_iso(at)}{by}:** {single}"


def is_history_entry(line: str) -> bool:
    return _HISTORY_LINE.match(line.strip()) is not None


def is_context_entry(line: str) -> bool:
    return _CONTEXT_LINE.match(line.strip()) is not None


def section_lines(body: str, heading: str) -> list[str]:
    """The lines under `heading` (exactly that line), up to the next "## " heading."""
    lines = body.split("\n")
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return []
    out = []
    for line in lines[start + 1 :]:
        if re.match(r"^##\s", line):
            break
        out.append(line)
    return out


def last_move_to(body: str) -> str | None:
    """The stage the history's last entry moved to, or None if it has none.
    Entries are compared by time, as Sheiko sorts them; with equal times the
    later line wins (Sheiko's sort keeps file order, then takes the last)."""
    moves = []
    for index, line in enumerate(section_lines(body, HISTORY_HEADING)):
        match = _HISTORY_LINE.match(line.strip())
        if match and (at := as_timestamp(match.group(1))):
            moves.append((at, index, match.group(3)))
    return max(moves)[2] if moves else None


def append_to_section(content: str, heading: str, line: str, is_entry) -> str:
    """Sheiko's appendToSection, with an entry test (Status History, Context)."""
    lines = content.split("\n")
    try:
        start = next(i for i, text in enumerate(lines) if text.strip() == heading)
    except StopIteration:
        return f"{content.rstrip()}\n\n{heading}\n\n{line}\n"
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^##\s", lines[i])), len(lines)
    )
    last_entry = max((i for i in range(start + 1, end) if is_entry(lines[i])), default=-1)
    if last_entry != -1:
        lines.insert(last_entry + 1, line)
        return "\n".join(lines)
    first_text = start + 1
    while first_text < end and lines[first_text].strip() == "":
        first_text += 1
    if first_text < end:
        lines[start + 1 : first_text] = ["", line, ""]
        return "\n".join(lines)
    insert_at = end
    while insert_at > start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    if insert_at == start + 1:
        lines[start + 1 : start + 1] = ["", line]
    else:
        lines.insert(insert_at, line)
    return "\n".join(lines)


# --- Frontmatter fields --------------------------------------------------------------------


def yaml_scalar(value: str | int) -> str:
    """A value as YAML that reads back as exactly that value: plain if it does,
    else JSON-quoted (e.g. "yes" or "123" as a name). A timestamp from
    local_iso stays plain, as Obsidian and Sheiko write it; YAML reads it as
    that same moment."""
    if isinstance(value, int):
        return str(value)
    if _ISO_STAMP.fullmatch(value) and _loads(value) == as_timestamp(value):
        return value
    if (
        value
        and value == value.strip()
        and _loads(value) == value
        and value[0] not in "\"'&*!|>%@`{[#"
    ):
        return value
    return json.dumps(value)


def _loads(text: str) -> object:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def set_fields(text: str, updates: dict[str, str | int]) -> str:
    """Set top-level frontmatter fields by editing their lines; add missing
    ones before the closing "---". Raises FieldEditRefused if that can't be
    done safely; the text is then unchanged."""
    head, body = frontmatter.split_raw(text)
    bom = "﻿" if head.startswith("﻿") else ""
    block = head[len(bom) :]
    if not block:
        raise FieldEditRefused("no-frontmatter")
    lines = block.splitlines(keepends=True)
    newline = "\r\n" if lines[0].endswith("\r\n") else "\n"
    inner = lines[1:-1]
    for key, value in updates.items():
        found = [i for i, line in enumerate(inner) if re.match(rf"^{re.escape(key)}\s*:", line)]
        if len(found) > 1:
            raise FieldEditRefused("duplicate-field")
        new_line = f"{key}: {yaml_scalar(value)}{newline}"
        if found:
            i = found[0]
            current = inner[i].split(":", 1)[1].strip()
            following = inner[i + 1] if i + 1 < len(inner) else ""
            if current in ("", "|", ">", "|-", ">-", "|+", ">+") or following[:1] in (" ", "\t"):
                raise FieldEditRefused("block-field")  # a list, a block or a nested value
            inner[i] = new_line
        else:
            inner.append(new_line)
    changed = bom + lines[0] + "".join(inner) + lines[-1] + body

    before, _ = frontmatter.split(text)
    after, _ = frontmatter.split(changed)
    expected = {**before, **{k: _loads(yaml_scalar(v)) for k, v in updates.items()}}
    if not before or after != expected:
        raise FieldEditRefused("check-failed")
    return changed
