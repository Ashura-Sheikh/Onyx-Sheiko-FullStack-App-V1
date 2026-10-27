"""The SQLite cache (threat model T10).

The Markdown files are the source of truth; this cache only speeds up
listing and search. Rules:

- It lives in the user's cache folder (macOS: ~/Library/Caches/onyx-sheiko,
  elsewhere: $XDG_CACHE_HOME/onyx-sheiko or ~/.cache/onyx-sheiko), or in
  ONYX_CACHE_DIR if set. It is refused inside the vault or inside this
  repository, so it can't be synced with the notes or committed.
- One file per vault, named by a hash of the vault's real path, so the file
  name doesn't reveal the vault's name or location.
- The folder is private (0700) and the file is private (0600): it holds note
  content, for search.
- It is rebuilt from the files every time the server starts, so it can never
  hold the only copy of anything, and deleting it is always safe.
- Before each search it catches up with the files: only notes whose size or
  modified time changed (or that were added or removed) are read again, so
  edits made in Obsidian show up without a restart.

Search (full-text, SQLite FTS5): each word of the query matches a word
starting with it, in the title (weighted 10x) or the body, ignoring case and
accents. The query is reduced to plain words before it reaches FTS5, so
quotes, operators or brackets typed by the user can't change the query.
"""

import hashlib
import os
import re
import sqlite3
import sys
import threading
from contextlib import closing
from pathlib import Path

from onyx.config import REPO_ROOT
from onyx.summary import searchable
from onyx.vault import NoteNotFound, PathRejected, Vault

APP_FOLDER = "onyx-sheiko"
SCHEMA_VERSION = 2
MAX_QUERY_WORDS = 10
SEARCH_LIMIT = 20
# Marks around matched words in a snippet. Removed from indexed text first,
# so a note can't fake a match.
MATCH_START, MATCH_END = "\x02", "\x03"
_WORD = re.compile(r"\w+")


def fts_query(text: str) -> str | None:
    """User text → an FTS5 query of quoted prefix words, or None if there are
    no words. Only \\w characters survive, so nothing can be an operator."""
    words = _WORD.findall(text)[:MAX_QUERY_WORDS]
    return " ".join(f'"{w}"*' for w in words) or None


def snippet_parts(snippet: str) -> list[dict]:
    """ "a \\x02b\\x03 c" → [{"text": "a ", "match": False}, {"text": "b", "match": True}, …]"""
    parts = []
    for index, piece in enumerate(re.split(f"[{MATCH_START}{MATCH_END}]", snippet)):
        if piece:
            parts.append({"text": piece, "match": index % 2 == 1})
    return parts


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
        # FastAPI runs requests on several threads; one catch-up at a time.
        self._lock = threading.Lock()

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

        with closing(self._connect()) as db, db:
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            db.execute(
                "CREATE TABLE notes (path TEXT PRIMARY KEY, version TEXT NOT NULL, "
                "size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL)"
            )
            db.execute(
                "CREATE VIRTUAL TABLE notes_fts USING fts5("
                "path UNINDEXED, title, body, kind UNINDEXED, folder UNINDEXED, "
                "tokenize = 'unicode61 remove_diacritics 2')"
            )
        return self.refresh()

    def _index(self, db: sqlite3.Connection, name: str) -> bool:
        try:
            stat = self.vault.resolve(name).stat()
            note = self.vault.read(name)
        except (NoteNotFound, PathRejected, UnicodeDecodeError, FileNotFoundError):
            # Gone since the listing, or not UTF-8: left out, never an error.
            return False
        title, kind, folder, body = searchable(note.text, note.path)
        clean = str.maketrans("", "", MATCH_START + MATCH_END)
        db.execute("DELETE FROM notes_fts WHERE path = ?", (note.path,))
        db.execute(
            "INSERT OR REPLACE INTO notes VALUES (?, ?, ?, ?)",
            (note.path, note.version, stat.st_size, stat.st_mtime_ns),
        )
        db.execute(
            "INSERT INTO notes_fts VALUES (?, ?, ?, ?, ?)",
            (note.path, title.translate(clean), body.translate(clean), kind, folder),
        )
        return True

    def refresh(self) -> int:
        """Catch up with the files: re-read only what changed. Returns the
        number of notes indexed."""
        with self._lock, closing(self._connect()) as db, db:
            known = {
                path: (size, mtime)
                for path, size, mtime in db.execute("SELECT path, size, mtime_ns FROM notes")
            }
            listed = set(self.vault.list_notes())
            for name in sorted(listed):
                try:
                    stat = self.vault.resolve(name).stat()
                except (PathRejected, FileNotFoundError):
                    continue
                if known.get(name) != (stat.st_size, stat.st_mtime_ns) and not self._index(
                    db, name
                ):
                    listed.discard(name)
            for gone in set(known) - listed:
                db.execute("DELETE FROM notes WHERE path = ?", (gone,))
                db.execute("DELETE FROM notes_fts WHERE path = ?", (gone,))
            return db.execute("SELECT count(*) FROM notes").fetchone()[0]

    def search(self, text: str, limit: int = SEARCH_LIMIT) -> list[dict]:
        """Notes and tasks matching the words in `text`, best first."""
        query = fts_query(text)
        if query is None:
            return []
        self.refresh()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT path, title, kind, folder, "
                "snippet(notes_fts, 2, char(2), char(3), '…', 12) "
                "FROM notes_fts WHERE notes_fts MATCH ? "
                "ORDER BY bm25(notes_fts, 0.0, 10.0, 1.0), path LIMIT ?",
                (query, limit),
            ).fetchall()
        return [
            {"path": p, "title": t, "kind": k, "folder": f, "snippet": snippet_parts(sn)}
            for p, t, k, f, sn in rows
        ]

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
