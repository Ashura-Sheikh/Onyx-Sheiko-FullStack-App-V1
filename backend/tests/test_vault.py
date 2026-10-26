"""Vault file access: the path guard (threat model T5) and safe writes (T8).

Each test builds its own small vault in a temporary folder, with a "secret"
file next to it that no path must ever reach.
"""

import os
import stat
from pathlib import Path

import pytest

from onyx.vault import (
    NoteExists,
    NoteNotFound,
    PathRejected,
    Vault,
    VersionConflict,
    version_of,
)

OUTSIDE_TEXT = "This file is outside the vault"


@pytest.fixture
def setup(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text(OUTSIDE_TEXT)
    root = tmp_path / "vault"
    (root / "Projects").mkdir(parents=True)
    (root / "Projects" / "Atlas.md").write_text("# Atlas\n")
    (root / "Unicode — ✓ é 字.md").write_text("unicode\n")
    (root / ".git").mkdir()
    (root / ".git" / "config.md").write_text("git internals")
    (root / ".obsidian").mkdir()
    (root / ".obsidian" / "app.md").write_text("settings")
    (root / ".hidden.md").write_text("hidden")
    (root / "image.png").write_bytes(b"\x89PNG")
    return Vault(root), root, outside


# --- T5: the path guard -----------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "",
        "..",
        "../outside/secret.md",
        "Projects/../../outside/secret.md",
        "Projects/../Atlas.md",  # even when it would stay inside
        "./Projects/Atlas.md",
        "Projects//Atlas.md",
        "Projects/",
        "/etc/passwd.md",
        "C:/Windows/notes.md",
        "c:notes.md",
        "Projects\\Atlas.md",
        "..\\outside\\secret.md",
        "Projects/Atlas.md\x00.png",
        ".git/config.md",
        ".obsidian/app.md",
        ".hidden.md",
        "Projects/.onyx-tmp-abc.md",
        "..%2Foutside%2Fsecret.md",  # percent-encoded, as received after one decode
        "image.png",
        "Projects",
        ".md",
        "a" * 256 + ".md",
        "a/" * 300 + "x.md",
    ],
)
def test_bad_names_are_rejected(setup, name):
    vault, _, _ = setup
    with pytest.raises(PathRejected):
        vault.resolve(name)


def test_absolute_path_inside_the_vault_is_still_rejected(setup):
    vault, root, _ = setup
    with pytest.raises(PathRejected):
        vault.resolve(str(root / "Projects" / "Atlas.md"))


def test_good_names_resolve_inside_the_vault(setup):
    vault, root, _ = setup
    assert vault.resolve("Projects/Atlas.md") == Path(os.path.realpath(root / "Projects/Atlas.md"))
    assert vault.read("Unicode — ✓ é 字.md").text == "unicode\n"


def test_symlinked_file_leading_outside_is_rejected(setup):
    vault, root, outside = setup
    (root / "link.md").symlink_to(outside / "secret.md")
    with pytest.raises(PathRejected):
        vault.read("link.md")


def test_symlinked_folder_leading_outside_is_rejected(setup):
    vault, root, outside = setup
    (root / "Shortcut").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathRejected):
        vault.read("Shortcut/secret.md")
    with pytest.raises(PathRejected):
        vault.create("Shortcut/new.md", "planted")
    assert not (outside / "new.md").exists()


def test_symlink_that_stays_inside_is_allowed(setup):
    vault, root, _ = setup
    (root / "alias.md").symlink_to(root / "Projects" / "Atlas.md")
    assert vault.read("alias.md").text == "# Atlas\n"


def test_the_secret_is_never_returned(setup):
    vault, root, outside = setup
    (root / "a.md").symlink_to(outside / "secret.md")
    (root / "Dir").symlink_to(outside, target_is_directory=True)
    attempts = ["../outside/secret.md", "a.md", "Dir/secret.md", str(outside / "secret.md")]
    for name in attempts:
        with pytest.raises(PathRejected):
            vault.read(name)


def test_listing_skips_hidden_non_markdown_and_escaping_links(setup):
    vault, root, outside = setup
    (root / "out.md").symlink_to(outside / "secret.md")
    (root / "OutDir").symlink_to(outside, target_is_directory=True)
    assert vault.list_notes() == ["Projects/Atlas.md", "Unicode — ✓ é 字.md"]


def test_missing_note(setup):
    vault, _, _ = setup
    with pytest.raises(NoteNotFound):
        vault.read("Projects/Nope.md")


def test_vault_root_must_be_a_folder(tmp_path):
    (tmp_path / "file").write_text("x")
    with pytest.raises(NotADirectoryError):
        Vault(tmp_path / "file")


# --- T8: safe writes ------------------------------------------------------


def test_read_returns_a_version_of_the_exact_bytes(setup):
    vault, root, _ = setup
    note = vault.read("Projects/Atlas.md")
    assert note.version == version_of((root / "Projects/Atlas.md").read_bytes())
    assert note.path == "Projects/Atlas.md"


def test_update_with_the_current_version(setup):
    vault, root, _ = setup
    before = vault.read("Projects/Atlas.md")
    after = vault.update("Projects/Atlas.md", "# Atlas\n\nMore.\n", before.version)
    assert (root / "Projects/Atlas.md").read_text() == "# Atlas\n\nMore.\n"
    assert after.version != before.version
    assert after.version == vault.read("Projects/Atlas.md").version


def test_update_is_refused_if_the_file_changed_on_disk(setup):
    vault, root, _ = setup
    stale = vault.read("Projects/Atlas.md")
    (root / "Projects/Atlas.md").write_text("# Atlas\n\nEdited in Obsidian.\n")
    with pytest.raises(VersionConflict):
        vault.update("Projects/Atlas.md", "my edit", stale.version)
    assert (root / "Projects/Atlas.md").read_text() == "# Atlas\n\nEdited in Obsidian.\n"


def test_update_of_a_missing_note(setup):
    vault, _, _ = setup
    with pytest.raises(NoteNotFound):
        vault.update("Projects/Gone.md", "x", "0" * 64)


def test_create_new_note_and_folder(setup):
    vault, root, _ = setup
    note = vault.create("Meetings/Sync.md", "# Sync\n")
    assert (root / "Meetings/Sync.md").read_text() == "# Sync\n"
    assert note.version == version_of(b"# Sync\n")


def test_create_never_replaces_an_existing_note(setup):
    vault, root, _ = setup
    with pytest.raises(NoteExists):
        vault.create("Projects/Atlas.md", "overwrite")
    assert (root / "Projects/Atlas.md").read_text() == "# Atlas\n"


def test_a_failed_write_leaves_the_note_intact_and_no_temp_file(setup, monkeypatch):
    vault, root, _ = setup
    original = (root / "Projects/Atlas.md").read_bytes()
    note = vault.read("Projects/Atlas.md")

    def crash(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError, match="disk full"):
        vault.update("Projects/Atlas.md", "new text that never lands", note.version)
    assert (root / "Projects/Atlas.md").read_bytes() == original
    assert [p.name for p in (root / "Projects").iterdir()] == ["Atlas.md"]


def test_bytes_round_trip_exactly(setup):
    vault, root, _ = setup
    text = "Line one\r\nLine two — ✓\n\n  trailing spaces  \n"
    vault.create("Exact.md", text)
    assert (root / "Exact.md").read_bytes() == text.encode("utf-8")
    assert vault.read("Exact.md").text == text


def test_update_keeps_file_permissions(setup):
    vault, root, _ = setup
    path = root / "Projects/Atlas.md"
    path.chmod(0o640)
    vault.update("Projects/Atlas.md", "changed", vault.read("Projects/Atlas.md").version)
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_new_notes_are_not_private_temp_files(setup):
    """mkstemp makes 0600 files; a new note should get normal permissions."""
    vault, root, _ = setup
    from onyx.vault import _UMASK

    vault.create("New.md", "x")
    assert stat.S_IMODE((root / "New.md").stat().st_mode) == 0o666 & ~_UMASK
    assert 0o666 & ~_UMASK != 0o600, "this test needs a umask that differs from mkstemp's 0600"


def test_writes_into_hidden_or_outside_places_are_refused(setup):
    vault, root, outside = setup
    for name in (".git/hooks/pre-commit.md", ".obsidian/x.md", "../outside/new.md"):
        with pytest.raises(PathRejected):
            vault.create(name, "planted")
    assert not (outside / "new.md").exists()
    assert not (root / ".git" / "hooks").exists()


def test_dot_segments_are_refused_by_their_own_rule(setup):
    """'..' and '.' also start with '.', so the hidden-file rule would catch
    them too; check the dedicated rule works on its own."""
    vault, _, _ = setup
    for name in ("Projects/../Atlas.md", "./Atlas.md", "Projects/./Atlas.md"):
        with pytest.raises(PathRejected, match=r"'\.' or '\.\.'"):
            vault.resolve(name)


def test_symlinked_folders_are_not_followed_when_listing(setup):
    """A link to a folder inside the vault would otherwise list its notes twice."""
    vault, root, _ = setup
    (root / "Alias").symlink_to(root / "Projects", target_is_directory=True)
    assert vault.list_notes() == ["Projects/Atlas.md", "Unicode — ✓ é 字.md"]


def test_a_symlink_loop_does_not_hang_the_listing(setup):
    """Run in a thread with a time limit, so a regression fails instead of hanging CI."""
    import threading

    vault, root, _ = setup
    (root / "Projects" / "Loop").symlink_to(root, target_is_directory=True)
    result = []
    worker = threading.Thread(target=lambda: result.append(vault.list_notes()), daemon=True)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive(), "listing didn't finish within 5 seconds"
    assert result == [["Projects/Atlas.md", "Unicode — ✓ é 字.md"]]
