"""Creating, renaming and deleting tasks, and sub-tasks (#9 part (c)).

Rules (issue #9, project-manager's #9 read, Sheikh's decisions 1a and 5a):
- a new task is `Tasks/<title>.md`, with `tags: [task]`, `status: open`,
  `dateCreated` and `dateModified`, optional `priority` and `due`, and a
  Status History holding one "created → open" line, in Sheiko's format;
- a sub-task also has the `subtask` tag and a `projects:` link to its parent
  (decision 1a: only tasks made as children count, so existing `projects:`
  links are left alone);
- one level only: a sub-task can't have sub-tasks. A done parent can't get
  new ones (done means every sub-task is done);
- "Make sub-tasks" makes one sub-task per unticked checklist line ("- [ ]")
  in the parent's body, and leaves the parent unchanged. Every name is
  checked before anything is written; a line whose sub-task already exists
  is skipped, so it can be run again after adding lines;
- a task with sub-tasks can't be renamed (decision 5a) or deleted;
- rename keeps the task in its folder and doesn't change [[links]] in other
  notes; delete moves it to .trash. Both quote the version that was opened.

Refusals are fixed sentences chosen by code (as onyx.vault.REFUSALS); typed
text never goes into a response.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import PurePosixPath

from onyx import editing, frontmatter, lifecycle, links, summary
from onyx.summary import SUBTASK_TAG, is_task
from onyx.vault import Note, NoteExists, NoteNotFound, PathRejected, Vault, VersionConflict

TASKS_FOLDER = "Tasks"
MAX_SUBTASKS = 50

TASK_REFUSALS: dict[str, str] = {
    "not-a-task": "This is a note, not a task.",
    "parent-not-task": "The parent must be a task.",
    "parent-is-subtask": "A sub-task can't have sub-tasks of its own: one level only.",
    "parent-done": "This task is done, so it can't get new sub-tasks.",
    "no-checklist": "This task has no unticked checklist lines (- [ ]) to make sub-tasks from.",
    "all-exist": "Every unticked checklist line already has its sub-task.",
    "too-many": f"That's more than {MAX_SUBTASKS} sub-tasks at once. Split the checklist first.",
    "item-name": "A checklist line can't be used as a task name. Names can't contain "
    '/ \\ : * ? " < > | # ^ [ ] or start with a dot.',
    "item-duplicate": "Two checklist lines give the same task name.",
    "item-taken": "A checklist line's name is already used by another note or task.",
    "rename-parent": "This task has sub-tasks, so it can't be renamed: their links to it "
    "would stop working.",
    "delete-parent": "This task has sub-tasks, so it can't be deleted. Delete them first.",
    "build-failed": "The new task's frontmatter couldn't be made safely, so nothing was written.",
}


class TaskRefused(ValueError):
    """`code` is a key of TASK_REFUSALS. `line` is the checklist line (1 = the
    first unticked one) a sub-task refusal is about, if any."""

    def __init__(self, code: str, line: int | None = None) -> None:
        super().__init__(TASK_REFUSALS[code])
        self.code = code
        self.line = line


class PartlyDone(RuntimeError):
    """Some sub-tasks were made, then one failed (a file appeared meanwhile)."""

    def __init__(self, created: list[str]) -> None:
        super().__init__("partly done")
        self.created = created


@dataclass(frozen=True)
class SubtasksMade:
    created: list[str]
    skipped: list[str]  # already there, as sub-tasks of this parent


# --- Reading the vault's tasks -----------------------------------------------------------


def _board(vault: Vault) -> dict[str, dict]:
    return {t["path"]: t for t in summary.task_board(summary.read_summary(vault))}


def _has_subtasks(board: dict[str, dict], path: str) -> bool:
    return any(t["parent"] and t["parent"]["path"] == path for t in board.values())


def _read_task(vault: Vault, requested: str) -> tuple[str, Note]:
    name = editing.listed(vault, requested)
    try:
        note = vault.read(name)
    except (PathRejected, UnicodeDecodeError) as error:
        raise NoteNotFound(requested) from error
    meta, _ = frontmatter.split(note.text)
    if not is_task(meta):
        raise TaskRefused("not-a-task")
    return name, note


def _check_parent(vault: Vault, board: dict[str, dict], requested: str) -> str:
    """The parent's path if it can take a new sub-task; raises otherwise."""
    name = editing.listed(vault, requested)
    parent = board.get(name)
    if parent is None:
        raise TaskRefused("parent-not-task")
    if parent["parent"] is not None:
        raise TaskRefused("parent-is-subtask")
    if parent["status"] == "done":
        raise TaskRefused("parent-done")
    return name


# --- Building a new task --------------------------------------------------------------------


def _quoted(text: str) -> str:
    # JSON strings are valid YAML double-quoted strings; names have no
    # control characters, quotes or backslashes (editing.note_file_name).
    return json.dumps(text, ensure_ascii=False)


def _parent_link(parent: str, child: str, all_paths: list[str]) -> str:
    """[[Name]] if that opens the parent from the child, else [[Folder/Name]]."""
    stem = PurePosixPath(parent).stem
    index = links.LinkIndex([*all_paths, child])
    if index.resolve(stem, child) == parent:
        return f"[[{stem}]]"
    return f"[[{parent.removesuffix('.md')}]]"


def task_text(
    at: datetime,
    priority: str | None = None,
    due: date | None = None,
    parent_link: str | None = None,
) -> str:
    """A new task's whole text. The frontmatter is parsed back and must be
    exactly the intended fields, else nothing is written."""
    stamp = lifecycle.local_iso(at)
    tags = ["task", SUBTASK_TAG] if parent_link else ["task"]
    lines = ["---", "tags:", *(f"  - {t}" for t in tags), "status: open"]
    if priority:
        lines.append(f"priority: {priority}")
    if due:
        lines.append(f"due: {due.isoformat()}")
    if parent_link:
        lines += ["projects:", f"  - {_quoted(parent_link)}"]
    lines += [f"dateCreated: {stamp}", f"dateModified: {stamp}", "---", ""]
    text = "\n".join(lines) + "\n" + lifecycle.HISTORY_HEADING + "\n\n"
    text += lifecycle.history_line(at, "created", "open") + "\n"

    expected: dict = {"tags": tags, "status": "open"}
    if priority:
        expected["priority"] = priority
    if due:
        expected["due"] = due
    if parent_link:
        expected["projects"] = [parent_link]
    expected["dateCreated"] = lifecycle.as_timestamp(stamp)
    expected["dateModified"] = lifecycle.as_timestamp(stamp)
    meta, _ = frontmatter.split(text)
    if meta != expected:
        raise TaskRefused("build-failed")
    return text


def _task_path(file_name: str) -> str:
    return f"{TASKS_FOLDER}/{file_name}"


def create_task(
    vault: Vault,
    title: str,
    at: datetime,
    priority: str | None = None,
    due: date | None = None,
    parent: str | None = None,
) -> Note:
    """A new task in Tasks/. Never replaces a file (NoteExists)."""
    path = _task_path(editing.note_file_name(title))
    parent_link = None
    if parent is not None:
        board = _board(vault)
        parent_path = _check_parent(vault, board, parent)
        parent_link = _parent_link(parent_path, path, vault.list_notes())
    if vault.root.joinpath(TASKS_FOLDER).exists():
        vault.resolve_folder(TASKS_FOLDER)  # a real folder, not a link
    return vault.create(path, task_text(at, priority, due, parent_link))


# --- Make sub-tasks from the parent's checklist ---------------------------------------------

_UNTICKED = re.compile(r"^\s*[-*+]\s+\[ \]\s+(.*\S)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


def unticked_lines(body: str) -> list[str]:
    """The text of every unticked checklist line, outside code blocks."""
    found, in_code = [], False
    for line in body.split("\n"):
        if _FENCE.match(line):
            in_code = not in_code
            continue
        if not in_code and (match := _UNTICKED.match(line.rstrip("\r"))):
            found.append(match.group(1))
    return found


def make_subtasks(vault: Vault, requested: str, version: str, at: datetime) -> SubtasksMade:
    """One sub-task per unticked checklist line of the parent. Everything is
    checked first; then the sub-tasks are made. The parent isn't changed, but
    its version is checked, so the checklist used is the one that was shown."""
    name, note = _read_task(vault, requested)
    if note.version != version:
        raise VersionConflict(name)
    board = _board(vault)
    _check_parent(vault, board, name)
    _, body = frontmatter.split(note.text)
    items = unticked_lines(body)
    if not items:
        raise TaskRefused("no-checklist")
    if len(items) > MAX_SUBTASKS:
        raise TaskRefused("too-many")

    existing = {p.casefold(): p for p in vault.list_notes()}
    seen: set[str] = set()
    to_make: list[str] = []
    skipped: list[str] = []
    for number, item in enumerate(items, start=1):
        try:
            path = _task_path(editing.note_file_name(item))
        except PathRejected as error:
            raise TaskRefused("item-name", number) from error
        key = path.casefold()
        if key in seen:
            raise TaskRefused("item-duplicate", number)
        seen.add(key)
        if key in existing:
            there = board.get(existing[key])
            if there and there["parent"] and there["parent"]["path"] == name:
                skipped.append(existing[key])
                continue
            raise TaskRefused("item-taken", number)
        to_make.append(path)
    if not to_make:
        raise TaskRefused("all-exist")

    all_paths = vault.list_notes()
    created: list[str] = []
    for path in to_make:
        text = task_text(at, parent_link=_parent_link(name, path, all_paths))
        try:
            created.append(vault.create(path, text).path)
        except (NoteExists, OSError) as error:
            if created:
                raise PartlyDone(created) from error
            raise
    return SubtasksMade(created, skipped)


# --- Rename and delete -----------------------------------------------------------------------


def rename_task(vault: Vault, requested: str, typed_name: str, version: str) -> str:
    """Rename a task in its folder. Refused for a task with sub-tasks (5a)."""
    name, _ = _read_task(vault, requested)
    if _has_subtasks(_board(vault), name):
        raise TaskRefused("rename-parent")
    folder = str(PurePosixPath(name).parent)
    file_name = editing.note_file_name(typed_name)
    return vault.rename(name, file_name if folder == "." else f"{folder}/{file_name}", version)


def delete_task(vault: Vault, requested: str, version: str, now: datetime) -> str:
    """Move a task to .trash. Refused for a task with sub-tasks."""
    name, _ = _read_task(vault, requested)
    if _has_subtasks(_board(vault), name):
        raise TaskRefused("delete-parent")
    return vault.trash(name, version, now)
