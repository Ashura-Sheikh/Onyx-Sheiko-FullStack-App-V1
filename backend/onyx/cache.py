"""The SQLite cache (threat model T10).

The Markdown files are the source of truth; this cache only speeds up
listing and, later, search. Rules:

- It lives in the user's cache folder (macOS: ~/Library/Caches/onyx-sheiko,
  elsewhere: $XDG_CACHE_HOME/onyx-sheiko or ~/.cache/onyx-sheiko), or in
  ONYX_CACHE_DIR if set. It is refused inside the vault or inside this
  repository, so it can't be synced with the notes or committed.
- One file per vault, named by a hash of the vault's real path, so the file
  name doesn't reveal the vault's name or location.
- The folder is private (0700) and the file is private (0600): it holds note
  content once search is added.
- It is rebuilt from the files every time the server starts, so it can never
  hold the only copy of anything, and deleting it is always safe.
"""

import hashlib
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from onyx.vault import Vault

APP_FOLDER = "onyx-sheiko"
SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[2]


class CacheLocationError(ValueError):
    """The cache folder isn't allowed; the message says why."""


def default_cache_dir(environ: dict[str, str] | None = None, platform: str | None = None) -> Path:
    env = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    if env.get("ONYX_CACHE_DIR"):
        return Path(env["ONYX_CACHE_DIR"]).expanduser()
    home = Path(env.get("HOME") or Path.home())
    if platform == "darwin":
        return home / "Library" / "Caches" / APP_FOLDER
    xdg = env.get("XDG_CACHE_HOME")
    return (Path(xdg) if xdg else home / ".cache") / APP_FOLDER


def cache_file_for(vault_root: Path, cache_dir: Path) -> Path:
    """Where the cache for this vault lives. Raises CacheLocationError if the
    folder is inside the vault or the repository."""
    vault_real = Path(os.path.realpath(vault_root))
    dir_real = Path(os.path.realpath(cache_dir))
    if dir_real.is_relative_to(vault_real):
        raise CacheLocationError("The cache folder can't be inside the vault.")
    if dir_real.is_relative_to(REPO_ROOT):
        raise CacheLocationError("The cache folder can't be inside the repository.")
    name = hashlib.sha256(str(vault_real).encode("utf-8")).hexdigest()[:24]
    return dir_real / f"vault-{name}.sqlite3"


class NoteCache:
    def __init__(self, vault: Vault, cache_dir: Path) -> None:
        self.vault = vault
        self.path = cache_file_for(vault.root, cache_dir)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def rebuild(self) -> int:
        """Throw the cache away and build it again from the files. Returns the
        number of notes indexed."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)

        # Create the file private from the start, before any content is written.
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)

        rows = []
        for name in self.vault.list_notes():
            note = self.vault.read(name)
            rows.append((note.path, note.version, len(note.text.encode("utf-8"))))

        with closing(self._connect()) as db, db:
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            db.execute(
                "CREATE TABLE notes ("
                "path TEXT PRIMARY KEY, version TEXT NOT NULL, size INTEGER NOT NULL)"
            )
            db.executemany("INSERT INTO notes VALUES (?, ?, ?)", rows)
        return len(rows)

    def paths(self) -> list[str]:
        with closing(self._connect()) as db:
            return [row[0] for row in db.execute("SELECT path FROM notes ORDER BY path")]

    def version(self, path: str) -> str | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT version FROM notes WHERE path = ?", (path,)).fetchone()
        return row[0] if row else None

    def schema_version(self) -> int:
        with closing(self._connect()) as db:
            return db.execute("PRAGMA user_version").fetchone()[0]
