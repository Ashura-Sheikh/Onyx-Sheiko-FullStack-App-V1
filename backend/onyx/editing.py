"""Editing a note's body (part (c) of issue #8).

Only the body is edited in v1. The frontmatter is kept exactly as it is on
disk, byte for byte (frontmatter.split_raw), and is never rebuilt from parsed
fields, which would drop anything the parser can't read. Fields such as
`status` are edited in Obsidian until Onyx has a field editor.

Saving quotes the version (SHA-256) the editor opened. If the file changed
since, the save is refused (VersionConflict) and nothing is written; the
caller gets the current version and the user keeps their text.

Line endings: a browser text box always gives "\\n". If the note used "\\r\\n"
throughout, the saved body is turned back into "\\r\\n", so opening and saving
a note without editing it leaves the file byte-for-byte unchanged.

As with reading (summary.note_detail), the requested name is only used to look
up the vault's own listing; the name that's opened or written always comes
from the listing (threat model T5).
"""

from datetime import datetime
from pathlib import PurePosixPath

from onyx import frontmatter
from onyx.summary import is_task
from onyx.vault import Note, NoteNotFound, PathRejected, Vault


def _listed(vault: Vault, requested: str) -> str:
    names = {name: name for name in vault.list_notes()}
    name = names.get(requested)
    if name is None:
        raise NoteNotFound(requested)
    return name


def uses_crlf(text: str) -> bool:
    """True if every line ending in the text is "\\r\\n" (and there's at least one)."""
    count = text.count("\n")
    return count > 0 and text.count("\r\n") == count


def with_line_endings_of(body: str, original: str) -> str:
    if not uses_crlf(original):
        return body
    return body.replace("\r\n", "\n").replace("\n", "\r\n")


def source(vault: Vault, requested: str) -> dict:
    """The note's body for the editor, its frontmatter (shown, not edited) and
    its version. Raises NoteNotFound if there's no such note."""
    name = _listed(vault, requested)
    try:
        note = vault.read(name)
    except (PathRejected, UnicodeDecodeError) as error:
        raise NoteNotFound(requested) from error
    head, body = frontmatter.split_raw(note.text)
    return {
        "path": note.path,
        "frontmatter": head.removeprefix("\ufeff"),
        "body": body,
        "version": note.version,
    }


def save_body(vault: Vault, requested: str, body: str, version: str) -> Note:
    """Replace the note's body, keeping its frontmatter as it is on disk.

    Raises NoteNotFound, or VersionConflict if the file isn't the version the
    editor opened."""
    name = _listed(vault, requested)
    try:
        current = vault.read(name)
    except (PathRejected, UnicodeDecodeError) as error:
        raise NoteNotFound(requested) from error
    head, _ = frontmatter.split_raw(current.text)
    # update() refuses unless the file on disk is still `version`, checked just
    # before it replaces the file; if `current` was already a different
    # version, the new text is never written.
    return vault.update(name, head + with_line_endings_of(body, current.text), version)


# --- Create, rename, delete (part (d) of issue #8) ---------------------------------
#
# Notes only: a task (tagged "task") is renamed or deleted in Tasks (#9), where
# Sheiko's lifecycle rules are handled. Rename keeps the note in its folder; it
# doesn't rewrite [[links]] in other notes (Sheikh's decisions on #8).

# Not allowed in a note name typed into Onyx: a folder separator, characters
# Windows and Obsidian refuse in file names, and ones that break [[links]].
_BAD_NAME_CHARS = set('/\\:*?"<>|#^[]')


class TaskNotHere(ValueError):
    """A task, not a note: renamed and deleted in Tasks, not here."""


def note_file_name(typed: str) -> str:
    """What the user typed → a file name ending in .md. Raises PathRejected
    with a message for the user."""
    name = typed.strip()
    if name.casefold().endswith(".md"):
        name = name[:-3].rstrip()
    if name == "":
        raise PathRejected("name-empty")
    if any(c in _BAD_NAME_CHARS or ord(c) < 32 or ord(c) == 127 for c in name):
        raise PathRejected("name-character")
    if name.startswith("."):
        raise PathRejected("name-dot")
    return name + ".md"


def _in_folder(folder: str, file_name: str) -> str:
    return f"{folder}/{file_name}" if folder else file_name


def _only_notes(vault: Vault, name: str) -> Note:
    try:
        note = vault.read(name)
    except (PathRejected, UnicodeDecodeError) as error:
        raise NoteNotFound(name) from error
    meta, _ = frontmatter.split(note.text)
    if is_task(meta):
        raise TaskNotHere(name)
    return note


def create_note(vault: Vault, folder: str, typed_name: str) -> Note:
    """An empty note in an existing folder ("" is the top level). Never
    replaces a file (NoteExists)."""
    vault.resolve_folder(folder)
    return vault.create(_in_folder(folder, note_file_name(typed_name)), "")


def rename_note(vault: Vault, requested: str, typed_name: str, version: str) -> str:
    """Rename a note in its folder. Returns the new path."""
    name = _listed(vault, requested)
    _only_notes(vault, name)
    folder = str(PurePosixPath(name).parent)
    new = _in_folder("" if folder == "." else folder, note_file_name(typed_name))
    return vault.rename(name, new, version)


def delete_note(vault: Vault, requested: str, version: str, now: datetime) -> str:
    """Move a note to the vault's .trash folder. Returns where it went."""
    name = _listed(vault, requested)
    _only_notes(vault, name)
    return vault.trash(name, version, now)


def current_version(vault: Vault, name: str) -> str | None:
    """The note's version now, or None if it's gone (for a conflict answer)."""
    try:
        return vault.read(_listed(vault, name)).version
    except (NoteNotFound, PathRejected, UnicodeDecodeError):
        return None
