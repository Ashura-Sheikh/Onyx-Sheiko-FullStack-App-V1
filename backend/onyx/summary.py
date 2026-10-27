"""What Home and the ⌘K palette show, read from the vault files.

Read-only: nothing here writes. Every file is read through onyx.vault, so the
path guard applies (threat model T5). Values from frontmatter are untrusted
text: each one is checked and turned into a plain type here, and anything
unexpected is dropped rather than passed on.

A task is a note tagged "task" (TaskNotes style). Its stage is its `status`;
a status outside the four stages isn't counted. Its history is the
"## Status History" list in the format the Sheiko Task Lifecycle plugin
writes: "- <ISO time> — <from> → <to>", optionally followed by "(…)".
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import PurePosixPath

from onyx import frontmatter
from onyx.vault import NoteNotFound, PathRejected, Vault

STAGES = ("open", "in-progress", "in-review", "done")
PRIORITIES = ("high", "normal", "low")
RECENT_NOTES = 5
HISTORY_ENTRIES = 10
MAX_TITLE_CHARS = 300

_HISTORY_LINE = re.compile(r"^-\s+(\S+)\s+—\s+(\S+)\s+→\s+(\S+)(?:\s+\((.{0,200})\))?\s*$")


@dataclass(frozen=True)
class Task:
    path: str
    title: str
    status: str | None
    priority: str | None
    due: date | None


@dataclass(frozen=True)
class NoteInfo:
    path: str
    title: str
    folder: str
    updated: datetime


@dataclass(frozen=True)
class HistoryEntry:
    at: datetime
    path: str
    title: str
    from_stage: str
    to_stage: str
    remark: str | None


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()[:MAX_TITLE_CHARS]
    return None


def _title(meta: dict, body: str, path: str) -> str:
    return (
        _text(meta.get("title"))
        or _text(frontmatter.first_heading(body))
        or PurePosixPath(path).stem[:MAX_TITLE_CHARS]
    )


def _is_task(meta: dict) -> bool:
    tags = meta.get("tags")
    if isinstance(tags, str):
        tags = [tags]
    return isinstance(tags, list) and "task" in tags


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    # A time without an offset is taken as UTC, so all times can be compared.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _history(body: str, path: str, title: str) -> list[HistoryEntry]:
    entries = []
    for line in frontmatter.section(body, "Status History"):
        match = _HISTORY_LINE.match(line)
        if not match:
            continue
        at = _as_datetime(match.group(1))
        to_stage = match.group(3)
        if at is None or to_stage not in STAGES:
            continue
        entries.append(
            HistoryEntry(at, path, title, match.group(2), to_stage, match.group(4) or None)
        )
    return entries


@dataclass(frozen=True)
class VaultSummary:
    tasks: list[Task]
    notes: list[NoteInfo]
    history: list[HistoryEntry]


def read_summary(vault: Vault) -> VaultSummary:
    tasks: list[Task] = []
    notes: list[NoteInfo] = []
    history: list[HistoryEntry] = []
    for name in vault.list_notes():
        try:
            note = vault.read(name)
        except (NoteNotFound, PathRejected, UnicodeDecodeError):
            # Removed since the listing, or not UTF-8: left out, never an error page.
            continue
        meta, body = frontmatter.split(note.text)
        title = _title(meta, body, note.path)
        if _is_task(meta):
            status = meta.get("status") if meta.get("status") in STAGES else None
            priority = meta.get("priority") if meta.get("priority") in PRIORITIES else None
            tasks.append(Task(note.path, title, status, priority, _as_date(meta.get("due"))))
            history.extend(_history(body, note.path, title))
        else:
            updated = _as_datetime(meta.get("dateModified"))
            if updated is None:
                try:
                    updated = vault.modified(name)
                except NoteNotFound:
                    continue
            folder = str(PurePosixPath(note.path).parent)
            notes.append(NoteInfo(note.path, title, "" if folder == "." else folder, updated))
    return VaultSummary(tasks, notes, history)


def home(summary: VaultSummary, today: date) -> dict:
    """The data behind Home, as plain JSON-ready values."""
    live = [t for t in summary.tasks if t.status in STAGES]
    due = sorted(
        (t for t in live if t.status != "done" and t.due is not None and t.due <= today),
        key=lambda t: (t.due, t.title.lower()),
    )
    waiting = sorted((t for t in live if t.status == "in-review"), key=lambda t: t.title.lower())
    recent = sorted(summary.notes, key=lambda n: (-n.updated.timestamp(), n.path))[:RECENT_NOTES]
    history = sorted(summary.history, key=lambda h: (-h.at.timestamp(), h.path))[:HISTORY_ENTRIES]
    return {
        "today": today.isoformat(),
        "counts": {stage: sum(1 for t in live if t.status == stage) for stage in STAGES},
        "due": [_task_json(t) for t in due],
        "waiting": [_task_json(t) for t in waiting],
        "recent_notes": [
            {
                "path": n.path,
                "title": n.title,
                "folder": n.folder,
                "updated": n.updated.isoformat(),
            }
            for n in recent
        ],
        "history": [
            {
                "at": h.at.isoformat(),
                "path": h.path,
                "title": h.title,
                "from": h.from_stage,
                "to": h.to_stage,
                "remark": h.remark,
            }
            for h in history
        ],
    }


def items(summary: VaultSummary) -> list[dict]:
    """Every note and task title, for the ⌘K palette."""
    found = [{"kind": "task", "path": t.path, "title": t.title} for t in summary.tasks]
    found += [{"kind": "note", "path": n.path, "title": n.title} for n in summary.notes]
    return sorted(found, key=lambda i: (i["title"].lower(), i["path"]))


def _task_json(task: Task) -> dict:
    return {
        "path": task.path,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "due": task.due.isoformat() if task.due else None,
    }
