"""Creating tasks, their sub-tasks and details; renaming and deleting tasks (#9 part (c)).

Sheikh's decisions on #40 (2026-11-14): sub-tasks are the task's own
checklist lines, as in the old Onyx app (onyx.checklist), not separate
files; a new task can have a description; "Edit details" changes priority,
due date, projects, tags and description. The title is the file name and
changes only through Rename.

- A new task is `Tasks/<title>.md`: `tags: [task]`, `status: open`,
  `dateCreated`, `dateModified`, optional `priority` and `due`, the
  description as its top text, and a Status History holding one
  "created → open" line, in Sheiko's format.
- Adding a sub-task inserts one "- [ ] …" line; ticking changes one
  character. A done task's checklist can't change (done means all ticked).
- Edit details writes only the fields whose value actually changes, so a
  value Onyx doesn't show (an unknown priority, say) is kept unless the user
  sets that field. Fields are edited in the raw frontmatter and parsed
  again; anything but the intended change is refused.
- Rename keeps the task in its folder and doesn't change [[links]] in other
  notes; delete moves it to .trash.

Every write quotes the version that was opened. Refusals are fixed
sentences chosen by code; typed text never goes into a response.
"""

import re
from datetime import date, datetime
from pathlib import PurePosixPath

from onyx import checklist, editing, frontmatter, lifecycle, links, summary
from onyx.summary import PRIORITIES, is_task
from onyx.vault import Note, NoteNotFound, PathRejected, Vault, VersionConflict

TASKS_FOLDER = "Tasks"
MAX_TAGS = 20
MAX_PROJECTS = 20
_TAG = re.compile(r"[\w/-]{1,64}")

TASK_REFUSALS: dict[str, str] = {
    "not-a-task": "This is a note, not a task.",
    "task-done": "This task is done, so its sub-tasks can't change.",
    "item-empty": "Type the sub-task.",
    "item-text": f"A sub-task is one line of up to {checklist.MAX_ITEM_CHARS} characters.",
    "item-gone": "That sub-task isn't there any more. Open the task again.",
    "tag-bad": "A tag is letters, digits, _, - or /, with at least one letter, and no spaces.",
    "tag-many": f"At most {MAX_TAGS} tags.",
    "project-bad": "A project name can't contain / \\ : * ? \" < > | # ^ [ ] or start with a dot.",
    "project-many": f"At most {MAX_PROJECTS} projects.",
    "description-long": "The description is too long.",
    "description-heading": "The description can't contain a # or ## heading; use ### or below.",
    "description-character": "The description contains a character that isn't allowed.",
    "build-failed": "The new task's frontmatter couldn't be made safely, so nothing was written.",
    "no-frontmatter": "This task has no frontmatter to change.",
    "duplicate-field": "This task's frontmatter has a field written twice, so it isn't "
    "changed here. Fix it in Obsidian first.",
    "check-failed": "This task's frontmatter couldn't be changed safely, so nothing was written.",
}


class TaskRefused(ValueError):
    """`code` is a key of TASK_REFUSALS."""

    def __init__(self, code: str) -> None:
        super().__init__(TASK_REFUSALS[code])
        self.code = code


# --- Reading ------------------------------------------------------------------------------


def _read_task(vault: Vault, requested: str) -> tuple[str, Note, dict]:
    name = editing.listed(vault, requested)
    try:
        note = vault.read(name)
    except (PathRejected, UnicodeDecodeError) as error:
        raise NoteNotFound(requested) from error
    meta, _ = frontmatter.split(note.text)
    if not is_task(meta):
        raise TaskRefused("not-a-task")
    return name, note, meta


def _with_body(text: str, change) -> str:
    """Apply `change` to the body ("\\n" line endings), keeping the frontmatter
    byte for byte and the file's own line endings."""
    head, body = frontmatter.split_raw(text)
    new = change(body.replace("\r\n", "\n"))
    return head + editing.with_line_endings_of(new, text)


def _checked(change):
    try:
        return change()
    except checklist.ChecklistError as error:
        raise TaskRefused(error.code) from error


# --- Create ---------------------------------------------------------------------------------


def task_text(
    at: datetime,
    priority: str | None = None,
    due: date | None = None,
    description: str = "",
) -> str:
    """A new task's whole text. The frontmatter is parsed back and must be
    exactly the intended fields, else nothing is written."""
    stamp = lifecycle.local_iso(at)
    lines = ["---", "tags:", "  - task", "status: open"]
    if priority:
        lines.append(f"priority: {priority}")
    if due:
        lines.append(f"due: {due.isoformat()}")
    lines += [f"dateCreated: {stamp}", f"dateModified: {stamp}", "---", ""]
    text = "\n".join(lines) + "\n"
    text += f"{description}\n\n" if description else ""
    text += f"{lifecycle.HISTORY_HEADING}\n\n{lifecycle.history_line(at, 'created', 'open')}\n"

    expected: dict = {"tags": ["task"], "status": "open"}
    if priority:
        expected["priority"] = priority
    if due:
        expected["due"] = due
    expected["dateCreated"] = lifecycle.as_timestamp(stamp)
    expected["dateModified"] = lifecycle.as_timestamp(stamp)
    meta, _ = frontmatter.split(text)
    if meta != expected:
        raise TaskRefused("build-failed")
    return text


def create_task(
    vault: Vault,
    title: str,
    at: datetime,
    priority: str | None = None,
    due: date | None = None,
    description: str = "",
) -> Note:
    """A new task in Tasks/. Never replaces a file (NoteExists)."""
    path = f"{TASKS_FOLDER}/{editing.note_file_name(title)}"
    text = task_text(at, priority, due, _checked(lambda: checklist.clean_description(description)))
    if vault.root.joinpath(TASKS_FOLDER).exists():
        vault.resolve_folder(TASKS_FOLDER)  # a real folder, not a link
    return vault.create(path, text)


# --- Sub-tasks: checklist lines -------------------------------------------------------------


def _not_done(meta: dict) -> None:
    if meta.get("status") == "done":
        raise TaskRefused("task-done")


def add_item(vault: Vault, requested: str, text: str, version: str) -> Note:
    name, note, meta = _read_task(vault, requested)
    _not_done(meta)
    new = _checked(lambda: _with_body(note.text, lambda body: checklist.add_item(body, text)))
    return vault.update(name, new, version)


def set_item(vault: Vault, requested: str, index: int, done: bool, version: str) -> Note:
    name, note, meta = _read_task(vault, requested)
    _not_done(meta)
    new = _checked(
        lambda: _with_body(note.text, lambda body: checklist.set_item(body, index, done))
    )
    if new == note.text:
        if note.version != version:
            raise VersionConflict(name)
        return note
    return vault.update(name, new, version)


# --- Edit details -----------------------------------------------------------------------------


def _clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for tag in tags:
        clean = tag.strip().removeprefix("#")
        if not clean:
            continue
        if not _TAG.fullmatch(clean) or not re.search(r"[^\d/_-]", clean) or clean == "task":
            raise TaskRefused("tag-bad")
        if clean not in out:
            out.append(clean)
    if len(out) > MAX_TAGS:
        raise TaskRefused("tag-many")
    return out


def _clean_projects(projects: list[str]) -> list[str]:
    out: list[str] = []
    for project in projects:
        if not project.strip():
            continue
        try:
            clean = editing.note_file_name(project).removesuffix(".md")
        except PathRejected as error:
            raise TaskRefused("project-bad") from error
        if clean not in out:
            out.append(clean)
    if len(out) > MAX_PROJECTS:
        raise TaskRefused("project-many")
    return out


def _project_names(meta: dict) -> list[str]:
    return [links.link_from_value(v) or v for v in summary._strings(meta.get("projects"))]


def edit_details(
    vault: Vault,
    requested: str,
    version: str,
    at: datetime,
    priority: str | None,
    due: date | None,
    projects: list[str],
    tags: list[str],
    description: str,
) -> Note:
    """Change only what differs from the task as it is now. Returns the note
    (unchanged, with no write, if nothing differs)."""
    name, note, meta = _read_task(vault, requested)
    new_tags, new_projects = _clean_tags(tags), _clean_projects(projects)
    updates: dict[str, lifecycle.Value] = {}
    current_priority = meta.get("priority") if meta.get("priority") in PRIORITIES else None
    if priority != current_priority:
        updates["priority"] = priority
    if due != summary._as_date(meta.get("due")):
        updates["due"] = due
    if new_projects != _project_names(meta):
        updates["projects"] = [f"[[{p}]]" for p in new_projects] or None
    if new_tags != [t for t in summary._strings(meta.get("tags")) if t != "task"]:
        updates["tags"] = ["task", *new_tags]

    text = _checked(
        lambda: _with_body(note.text, lambda body: checklist.with_description(body, description))
    )
    if (updates or text != note.text) and "dateModified" in meta:
        updates["dateModified"] = lifecycle.local_iso(at.astimezone().replace(microsecond=0))
    if updates:
        try:
            text = lifecycle.set_frontmatter(text, updates)
        except lifecycle.FieldEditRefused as error:
            raise TaskRefused(str(error)) from error
    if text == note.text:
        if note.version != version:
            raise VersionConflict(name)
        return note
    return vault.update(name, text, version)


# --- Rename and delete -------------------------------------------------------------------------


def rename_task(vault: Vault, requested: str, typed_name: str, version: str) -> str:
    """Rename a task in its folder. Returns the new path."""
    name, _, _ = _read_task(vault, requested)
    folder = str(PurePosixPath(name).parent)
    file_name = editing.note_file_name(typed_name)
    return vault.rename(name, file_name if folder == "." else f"{folder}/{file_name}", version)


def delete_task(vault: Vault, requested: str, version: str, now: datetime) -> str:
    """Move a task to .trash. Returns where it went."""
    name, _, _ = _read_task(vault, requested)
    return vault.trash(name, version, now)
