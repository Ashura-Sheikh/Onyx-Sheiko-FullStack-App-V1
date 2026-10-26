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
"""

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

NOTE_SUFFIX = ".md"
MAX_PATH_CHARS = 512
MAX_SEGMENT_CHARS = 255
TEMP_PREFIX = ".onyx-tmp-"


class PathRejected(ValueError):
    """The name isn't allowed. The message is safe to show to the user."""


class NoteNotFound(FileNotFoundError):
    pass


class NoteExists(FileExistsError):
    pass


class VersionConflict(RuntimeError):
    """The file changed on disk since it was read."""


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

    def resolve(self, name: str) -> Path:
        """Return the real absolute path for a note name, or raise PathRejected."""
        if not isinstance(name, str) or name == "":
            raise PathRejected("A note path is required.")
        if len(name) > MAX_PATH_CHARS:
            raise PathRejected("The note path is too long.")
        if "\x00" in name or "\\" in name:
            raise PathRejected("The note path contains a character that isn't allowed.")
        if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
            raise PathRejected("Use a path inside the vault, not an absolute path.")
        segments = name.split("/")
        for segment in segments:
            if segment in ("", ".", ".."):
                raise PathRejected("The note path has an empty, '.' or '..' part.")
            if segment.startswith("."):
                raise PathRejected("Hidden files and folders can't be used.")
            if len(segment) > MAX_SEGMENT_CHARS:
                raise PathRejected("A part of the note path is too long.")
        if not segments[-1].endswith(NOTE_SUFFIX) or segments[-1] == NOTE_SUFFIX:
            raise PathRejected("Only Markdown notes (.md) can be opened.")

        real = Path(os.path.realpath(self.root.joinpath(*segments)))
        if not real.is_relative_to(self.root) or real == self.root:
            raise PathRejected("The note path leads outside the vault.")
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
            raise PathRejected("That path is a folder, not a note.") from error
        return Note(path=self.relative(path), text=data.decode("utf-8"), version=version_of(data))

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
