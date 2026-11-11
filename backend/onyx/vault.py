"""All access to vault files goes through this module (threat model T5, T8).

Path guard (T5): a note is named by a relative path like
"Projects/Atlas kickoff.md". Before anything touches the disk, the name is
checked lexically, then resolved with symlinks followed, and the real path
must still be inside the vault. Refused: empty or over-long names, absolute
paths, backslashes, NUL bytes, "." and ".." segments, empty segments, any
segment starting with "." (dotfiles, .git, .obsidian, and this module's own
temporary files), and anything that isn't a .md file.

Safe writes (T8): every write goes to a temporary file in the same folder,
is flushed to disk, then renamed over the target in one step (os.replace),
so a crash never leaves a half-written note. Each read returns a version (a
SHA-256 of the bytes); a write must quote the version it read, and is
refused if the file changed on disk since, so nothing is silently
overwritten. Creating a note refuses to replace an existing one.

The check-then-rename has a small window in which another program could
change the file; for a single-user local app that is accepted, not locked.

Rename and trash (part (d) of #8) never replace a file: the note is hard-linked
to its new name (which fails if that name exists), checked again, and only then
is the old name removed, and only if it's still the same file. Both quote a
version, like saving. Notes reached through a symlink are never moved. The
trash folder (.trash, as in Obsidian) is hidden, so it's built here rather
than through the path guard, and every folder on the way must be a real
folder, never a link.
"""

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

NOTE_SUFFIX = ".md"
TRASH_FOLDER = ".trash"  # Obsidian's own trash folder name
MAX_PATH_CHARS = 512
MAX_SEGMENT_CHARS = 255
TEMP_PREFIX = ".onyx-tmp-"


# Why a name or path was refused, by code. The API answers with these fixed
# sentences only, looked up by code, so no exception text, path or typed
# input ever reaches a response (CodeQL: information exposure through an
# exception).
REFUSALS: dict[str, str] = {
    "path-required": "A note path is required.",
    "path-too-long": "The note path is too long.",
    "path-character": "The note path contains a character that isn't allowed.",
    "path-absolute": "Use a path inside the vault, not an absolute path.",
    "path-dots": "The note path has an empty, '.' or '..' part.",
    "path-hidden": "Hidden files and folders can't be used.",
    "path-part-too-long": "A part of the note path is too long.",
    "not-markdown": "Only Markdown notes (.md) can be opened.",
    "outside-vault": "The note path leads outside the vault.",
    "folder-link": "That folder is a link, or leads outside the vault.",
    "no-folder": "There's no such folder in the vault.",
    "note-link": "Notes reached through a link can't be moved or deleted.",
    "is-folder": "That path is a folder, not a note.",
    "target-folder-link": "The new folder is a link, or leads outside the vault.",
    "same-name": "The new name is the same as the old one.",
    "trash-link": "The trash folder is a link or a file, so nothing was moved.",
    "name-empty": "Type a name for the note.",
    "name-character": "A note name can't contain / \\ : * ? \" < > | # ^ [ ]",
    "name-dot": "A note name can't start with a dot.",
}


class PathRejected(ValueError):
    """The name isn't allowed. `code` is a key of REFUSALS; the message is
    REFUSALS[code], a fixed sentence written for the user."""

    def __init__(self, code: str) -> None:
        super().__init__(REFUSALS[code])
        self.code = code


class NoteNotFound(FileNotFoundError):
    pass


class NoteExists(FileExistsError):
    pass


class VersionConflict(RuntimeError):
    """The file changed on disk since it was read."""


class MoveNotSupported(OSError):
    """The disk can't make the link a safe move needs (some USB and network
    disks); nothing was moved."""


@dataclass(frozen=True)
class Note:
    path: str  # relative, with "/" separators
    text: str
    version: str


def version_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Vault:
    def __init__(self, root: Path) -> None:
        self.root = Path(os.path.realpath(root))
        if not self.root.is_dir():
            raise NotADirectoryError(str(root))

    # --- Path guard ----------------------------------------------------------

    @staticmethod
    def _segments(name: str) -> list[str]:
        """The lexical checks shared by notes and folders."""
        if not isinstance(name, str) or name == "":
            raise PathRejected("path-required")
        if len(name) > MAX_PATH_CHARS:
            raise PathRejected("path-too-long")
        if "\x00" in name or "\\" in name:
            raise PathRejected("path-character")
        if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
            raise PathRejected("path-absolute")
        segments = name.split("/")
        for segment in segments:
            if segment in ("", ".", ".."):
                raise PathRejected("path-dots")
            if segment.startswith("."):
                raise PathRejected("path-hidden")
            if len(segment) > MAX_SEGMENT_CHARS:
                raise PathRejected("path-part-too-long")
        return segments

    def resolve(self, name: str) -> Path:
        """Return the real absolute path for a note name, or raise PathRejected."""
        segments = self._segments(name)
        if not segments[-1].endswith(NOTE_SUFFIX) or segments[-1] == NOTE_SUFFIX:
            raise PathRejected("not-markdown")

        real = Path(os.path.realpath(self.root.joinpath(*segments)))
        if not real.is_relative_to(self.root) or real == self.root:
            raise PathRejected("outside-vault")
        return real

    def resolve_folder(self, name: str) -> Path:
        """An existing folder inside the vault ("" is the vault itself), with
        no symlink anywhere in its path. Raises PathRejected otherwise."""
        if name == "":
            return self.root
        segments = self._segments(name)
        joined = self.root.joinpath(*segments)
        if Path(os.path.realpath(joined)) != joined:
            raise PathRejected("folder-link")
        if not joined.is_dir():
            raise PathRejected("no-folder")
        return joined

    def _strict(self, name: str) -> Path:
        """resolve(), and also refuse any symlink in the path: moving a file
        that's reached through a link would move the link's target."""
        real = self.resolve(name)
        if real != self.root.joinpath(*name.split("/")):
            raise PathRejected("note-link")
        return real

    def relative(self, real: Path) -> str:
        return real.relative_to(self.root).as_posix()

    # --- Reading -------------------------------------------------------------

    def read(self, name: str) -> Note:
        path = self.resolve(name)
        try:
            data = path.read_bytes()
        except FileNotFoundError as error:
            raise NoteNotFound(name) from error
        except IsADirectoryError as error:
            raise PathRejected("is-folder") from error
        return Note(path=self.relative(path), text=data.decode("utf-8"), version=version_of(data))

    def modified(self, name: str) -> datetime:
        """When the note's file last changed on disk (UTC)."""
        path = self.resolve(name)
        try:
            seconds = path.stat().st_mtime
        except FileNotFoundError as error:
            raise NoteNotFound(name) from error
        return datetime.fromtimestamp(seconds, tz=UTC)

    def list_notes(self) -> list[str]:
        """Every note in the vault, sorted. Hidden folders and symlinks that
        lead outside the vault are left out; symlinked folders aren't followed."""
        found = []
        for folder, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for file in files:
                if file.startswith(".") or not file.endswith(NOTE_SUFFIX):
                    continue
                relative = Path(folder, file).relative_to(self.root).as_posix()
                try:
                    self.resolve(relative)
                except PathRejected:
                    continue
                found.append(relative)
        return sorted(found)

    # --- Writing -------------------------------------------------------------

    def create(self, name: str, text: str) -> Note:
        """Create a new note. Refuses to replace an existing file."""
        path = self.resolve(name)
        if path.exists():
            raise NoteExists(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        return self._write(path, text, expected_version=None)

    def update(self, name: str, text: str, expected_version: str) -> Note:
        """Replace a note's text, only if it hasn't changed since it was read."""
        path = self.resolve(name)
        if not path.exists():
            raise NoteNotFound(name)
        return self._write(path, text, expected_version=expected_version)

    # --- Moving: rename and trash ------------------------------------------------

    def rename(self, old: str, new: str, expected_version: str) -> str:
        """Give a note a new name. Never replaces another file, and refuses if
        the note changed since `expected_version` was read. Returns the new
        relative path."""
        source = self._strict(old)
        target = self.resolve(new)
        if target.parent != self.root.joinpath(*new.split("/")).parent:
            raise PathRejected("target-folder-link")
        if source == target:
            raise PathRejected("same-name")
        if not source.is_file():
            raise NoteNotFound(old)
        # Same letters ignoring case, and the disk says it's the same file. (Two
        # different names for one file, i.e. hard links, aren't this case:
        # os.rename would quietly do nothing there, so they go the safe way.)
        if (
            str(source).casefold() == str(target).casefold()
            and target.exists()
            and os.path.samefile(source, target)
        ):
            # Only the capitals change, on a disk that ignores case (the Mac
            # default): the "existing" target is this same file. A link would
            # fail, so rename in place; nothing else can be replaced.
            self._check_version(source, expected_version)
            os.rename(source, target)
            _fsync_folder(target.parent)
            return self.relative(target)
        if not target.parent.is_dir():
            raise PathRejected("no-folder")
        self._move_no_replace(source, target, expected_version)
        return self.relative(target)

    def trash(self, name: str, expected_version: str, now: datetime) -> str:
        """Move a note into the vault's .trash folder, keeping its folders,
        like Obsidian's own trash. Refuses if the note changed since
        `expected_version` was read. Returns where it went, relative to the vault.

        .trash is hidden, so the path guard would refuse it: the target is
        built here, from the vault root and the note's own checked path,
        never from the request. Every folder on the way must be a real
        folder (not a link), so a planted link can't send the note out."""
        source = self._strict(name)
        if not source.is_file():
            raise NoteNotFound(name)
        relative = PurePosixPath(self.relative(source))
        folder = self._real_subfolder(self.root, TRASH_FOLDER)
        for part in relative.parent.parts:
            folder = self._real_subfolder(folder, part)
        stamp = now.strftime("%Y-%m-%d %H%M%S")
        candidates = [relative.name] + [
            f"{relative.stem} (deleted {stamp}{'' if n == 1 else f' {n}'}){relative.suffix}"
            for n in range(1, 100)
        ]
        for candidate in candidates:
            # Inside the trash: every folder is checked above, and the name
            # already passed the path guard, so it has no "/" or "..".
            target = folder / candidate
            try:
                self._move_no_replace(source, target, expected_version)
            except NoteExists:
                continue
            return target.relative_to(self.root).as_posix()
        raise NoteExists(name)

    def _real_subfolder(self, parent: Path, name: str) -> Path:
        """parent/name as a real folder, made if missing. Refuses a link or a
        file in its place."""
        folder = parent / name
        try:
            os.mkdir(folder, 0o777 & ~_UMASK)
        except FileExistsError:
            pass
        if not stat.S_ISDIR(os.lstat(folder).st_mode):
            raise PathRejected("trash-link")
        return folder

    def _check_version(self, path: Path, expected_version: str) -> None:
        if version_of(path.read_bytes()) != expected_version:
            raise VersionConflict(self.relative(path))

    def _move_no_replace(self, source: Path, target: Path, expected_version: str) -> None:
        """Move source to target without ever replacing a file at target.

        os.rename would silently replace an existing target, and a separate
        "exists?" check leaves a gap. A hard link fails if the target exists,
        so: link to the new name, check it's still the expected version, then
        remove the old name, only if it is still the same file. Interrupted at
        any point, the note is under one name or both, never neither."""
        self._check_version(source, expected_version)
        try:
            os.link(source, target, follow_symlinks=False)
        except FileExistsError as error:
            raise NoteExists(self.relative(target)) from error
        except OSError as error:
            raise MoveNotSupported(str(error.strerror)) from error
        try:
            linked = os.lstat(target)
            if version_of(target.read_bytes()) != expected_version or not os.path.samestat(
                linked, os.lstat(source)
            ):
                raise VersionConflict(self.relative(source))
        except BaseException:
            os.unlink(target)
            raise
        os.unlink(source)
        _fsync_folder(target.parent)
        _fsync_folder(source.parent)

    def _write(self, path: Path, text: str, expected_version: str | None) -> Note:
        data = text.encode("utf-8")
        if expected_version is not None:
            current = path.read_bytes()
            if version_of(current) != expected_version:
                raise VersionConflict(self.relative(path))
            mode = stat.S_IMODE(path.stat().st_mode)
        else:
            mode = 0o666 & ~_UMASK

        fd, temp_name = tempfile.mkstemp(prefix=TEMP_PREFIX, dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as temp:
                temp.write(data)
                temp.flush()
                os.fsync(temp.fileno())
            os.chmod(temp_name, mode)
            if expected_version is None and path.exists():
                raise NoteExists(self.relative(path))  # created meanwhile
            os.replace(temp_name, path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        _fsync_folder(path.parent)
        return Note(path=self.relative(path), text=text, version=version_of(data))


def _read_umask() -> int:
    # os.umask can only be read by setting it, which is process-wide; do it
    # once at import, before the server starts its request threads.
    mask = os.umask(0)
    os.umask(mask)
    return mask


_UMASK = _read_umask()


def _fsync_folder(folder: Path) -> None:
    """Make the rename itself durable (best effort; not every system allows it)."""
    try:
        fd = os.open(folder, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
