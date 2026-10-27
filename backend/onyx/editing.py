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

from onyx import frontmatter
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


def current_version(vault: Vault, name: str) -> str | None:
    """The note's version now, or None if it's gone (for a conflict answer)."""
    try:
        return vault.read(_listed(vault, name)).version
    except (NoteNotFound, PathRejected, UnicodeDecodeError):
        return None
