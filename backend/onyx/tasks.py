"""Moving a task one stage on, and signing off its close (#9 part (b)).

Rules (issue #9, project-manager's #9 read, Sheikh's decisions 3a and 6):
- one stage at a time, forward only: open → in-progress → in-review → done;
- each move changes `status` (and `dateModified` if the note has one) and
  adds one Status History line; nothing else in the note changes;
- done needs a sign-off by the identity the server was started with
  (--identity). The task's history must end with its move into review (as in
  Sheiko 0.2.5, #21), and none of its sub-tasks may still be open;
- on done: a Context sign-off line, a history line "(signed off by <who> at
  <time>)", and closure fields only where they're blank: completedDate,
  closedBy, timeToCloseMinutes (only from a full-timestamp dateCreated: a
  date-only one gives no duration, never a guessed one), closureSource: onyx
  (so Sheiko's reopen leaves them alone);
- the move quotes the version that was opened, like every write.

Refusals are fixed sentences chosen by code (as onyx.vault.REFUSALS).
"""

from datetime import datetime

from onyx import editing, frontmatter, lifecycle, summary
from onyx.summary import STAGES, is_task
from onyx.vault import Note, NoteNotFound, PathRejected, Vault

MOVE_REFUSALS: dict[str, str] = {
    "not-a-task": "This is a note, not a task.",
    "unknown-stage": "This task's stage isn't one of open, in progress, in review or done, "
    "so it can't be moved here. Fix it in Obsidian first.",
    "one-step": "Tasks move one stage at a time, forward only.",
    "no-identity": "Sign-off needs a name: start the server with --identity NAME.",
    "no-review-entry": "This task's history doesn't end with its move into review, so a "
    "sign-off can't count. Move it out of review and back first.",
    "open-subtasks": "This task has sub-tasks that aren't done yet.",
    "no-frontmatter": "This task has no frontmatter to change.",
    "duplicate-field": "This task's frontmatter has a field written twice, so it isn't "
    "changed here. Fix it in Obsidian first.",
    "block-field": "A field this move changes is written as a list or a block, so it isn't "
    "changed here. Fix it in Obsidian first.",
    "check-failed": "This task's frontmatter couldn't be changed safely, so nothing was written.",
}


class MoveRefused(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(MOVE_REFUSALS[code])
        self.code = code


def _open_subtasks(vault: Vault, path: str) -> bool:
    board = summary.task_board(summary.read_summary(vault))
    return any(t["parent"] and t["parent"]["path"] == path and t["status"] != "done" for t in board)


def move(
    vault: Vault, requested: str, to: str, version: str, identity: str | None, now: datetime
) -> Note:
    """Move a task one stage on. Raises MoveRefused, NoteNotFound, or
    VersionConflict (from the write) if the file isn't the version opened."""
    name = editing.listed(vault, requested)
    try:
        note = vault.read(name)
    except (PathRejected, UnicodeDecodeError) as error:
        raise NoteNotFound(requested) from error
    meta, body = frontmatter.split(note.text)
    if not is_task(meta):
        raise MoveRefused("not-a-task")
    current = meta.get("status")
    if current not in STAGES:
        raise MoveRefused("unknown-stage")
    if to not in STAGES or STAGES.index(to) != STAGES.index(current) + 1:
        raise MoveRefused("one-step")

    at = now.astimezone().replace(microsecond=0)
    stamp = lifecycle.local_iso(at)
    fields: dict[str, str | int] = {"status": to}
    if "dateModified" in meta:
        fields["dateModified"] = stamp
    note_text = None

    if to == "done":
        who = (identity or "").strip()
        if not who:
            raise MoveRefused("no-identity")
        if lifecycle.last_move_to(body) != "in-review":
            raise MoveRefused("no-review-entry")
        if _open_subtasks(vault, name):
            raise MoveRefused("open-subtasks")
        closure = _closure_fields(meta, at, who)
        fields.update(closure)
        if closure:
            fields["closureSource"] = "onyx"
        note_text = f"signed off by {who} at {stamp}"

    try:
        text = lifecycle.set_fields(note.text, fields)
    except lifecycle.FieldEditRefused as error:
        raise MoveRefused(str(error)) from error
    if to == "done":
        text = lifecycle.append_to_section(
            text,
            lifecycle.CONTEXT_HEADING,
            lifecycle.context_line(at, who, lifecycle.SIGNOFF_PHRASE),
            lifecycle.is_context_entry,
        )
    text = lifecycle.append_to_section(
        text,
        lifecycle.HISTORY_HEADING,
        lifecycle.history_line(at, current, to, note_text),
        lifecycle.is_history_entry,
    )
    return vault.update(name, text, version)


def _blank(value: object) -> bool:
    return value is None or value == ""


def _closure_fields(meta: dict, at: datetime, who: str) -> dict[str, str | int]:
    """Sheiko's applyClosure rules: fill blanks only, never overwrite, never guess."""
    out: dict[str, str | int] = {}
    completed = meta.get("completedDate")
    same_day = lifecycle.is_date_only(completed) and str(completed) == at.date().isoformat()
    if _blank(completed) or same_day:
        out["completedDate"] = lifecycle.local_iso(at)
        closed = at
    else:
        closed = lifecycle.as_timestamp(completed)
    if _blank(meta.get("closedBy")):
        out["closedBy"] = who
    created = lifecycle.as_timestamp(meta.get("dateCreated"))
    if "timeToCloseMinutes" not in meta and closed and created and closed >= created:
        out["timeToCloseMinutes"] = round((closed - created).total_seconds() / 60)
    return out
