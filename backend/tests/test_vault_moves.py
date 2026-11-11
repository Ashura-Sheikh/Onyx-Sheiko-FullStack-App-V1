"""Creating in a folder, renaming and moving to the trash, at the vault layer
(part (d) of issue #8; threat model T5, T8).

Each test builds its own small vault in a temporary folder, with an
"outside" folder next to it that nothing must ever reach.
"""

import os
from datetime import datetime
from pathlib import Path

import pytest

from onyx import vault as vault_module
from onyx.vault import (
    MoveNotSupported,
    NoteExists,
    NoteNotFound,
    PathRejected,
    Vault,
    VersionConflict,
    version_of,
)

NOW = datetime(2031, 4, 16, 9, 30, 15)
ATLAS = "Projects/Atlas.md"
ATLAS_TEXT = "# Atlas\n\nKickoff notes.\n"


@pytest.fixture
def setup(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "vault"
    (root / "Projects").mkdir(parents=True)
    (root / "Projects" / ATLAS.split("/")[1]).write_text(ATLAS_TEXT)
    (root / "Top.md").write_text("top\n")
    return Vault(root), root, outside


def v(root: Path, name: str) -> str:
    return version_of((root / name).read_bytes())


def files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


# --- Folders ------------------------------------------------------------------


def test_resolve_folder(setup):
    vault, root, outside = setup
    assert vault.resolve_folder("") == vault.root
    assert vault.resolve_folder("Projects") == vault.root / "Projects"
    (root / "Out").symlink_to(outside, target_is_directory=True)
    (root / "Alias").symlink_to(root / "Projects", target_is_directory=True)
    (root / ".hidden").mkdir()
    for bad in ["Nope", "Top.md", "Out", "Alias", ".hidden", "..", "../outside", "/srv", "a//b"]:
        with pytest.raises(PathRejected):
            vault.resolve_folder(bad)


# --- Rename -------------------------------------------------------------------


def test_rename_moves_the_note_and_keeps_its_bytes(setup):
    vault, root, _ = setup
    before = (root / ATLAS).read_bytes()
    renamed = vault.rename(ATLAS, "Projects/Atlas plan.md", version_of(before))
    assert renamed == "Projects/Atlas plan.md"
    assert (root / "Projects/Atlas plan.md").read_bytes() == before
    assert not (root / ATLAS).exists()
    assert files(root) == ["Projects/Atlas plan.md", "Top.md"]


def test_rename_never_replaces_an_existing_note(setup):
    vault, root, _ = setup
    (root / "Projects/Taken.md").write_text("someone else's note\n")
    with pytest.raises(NoteExists):
        vault.rename(ATLAS, "Projects/Taken.md", v(root, ATLAS))
    assert (root / "Projects/Taken.md").read_text() == "someone else's note\n"
    assert (root / ATLAS).read_text() == ATLAS_TEXT


def test_rename_of_a_changed_note_is_refused(setup):
    vault, root, _ = setup
    stale = v(root, ATLAS)
    (root / ATLAS).write_text("changed in Obsidian\n")
    with pytest.raises(VersionConflict):
        vault.rename(ATLAS, "Projects/New.md", stale)
    assert files(root) == [ATLAS, "Top.md"]


def test_rename_changing_only_capitals(setup):
    # On the Mac's usual disk (case-insensitive) this takes the in-place path;
    # on a case-sensitive disk (CI) it's an ordinary rename. Same result.
    vault, root, _ = setup
    before = (root / ATLAS).read_bytes()
    assert vault.rename(ATLAS, "Projects/atlas.md", version_of(before)) == "Projects/atlas.md"
    assert os.listdir(root / "Projects") == ["atlas.md"]
    assert (root / "Projects/atlas.md").read_bytes() == before


def test_rename_changing_only_capitals_checks_the_version(setup):
    vault, root, _ = setup
    stale = v(root, ATLAS)
    (root / ATLAS).write_text("changed\n")
    with pytest.raises(VersionConflict):
        vault.rename(ATLAS, "Projects/atlas.md", stale)
    assert os.listdir(root / "Projects") == ["Atlas.md"]


def test_rename_onto_a_hard_link_of_itself_is_refused(setup):
    # Two names for one file: os.rename would quietly do nothing and report
    # success. It must be refused, and both names left alone.
    vault, root, _ = setup
    os.link(root / ATLAS, root / "Projects/Other name.md")
    with pytest.raises(NoteExists):
        vault.rename(ATLAS, "Projects/Other name.md", v(root, ATLAS))
    assert sorted(os.listdir(root / "Projects")) == ["Atlas.md", "Other name.md"]


def test_rename_to_the_same_name_is_refused(setup):
    vault, root, _ = setup
    with pytest.raises(PathRejected):
        vault.rename(ATLAS, ATLAS, v(root, ATLAS))


@pytest.mark.parametrize(
    "new", ["../outside/x.md", "Projects/.hidden.md", "Projects/x.txt", "/srv/x.md", "Nope/x.md"]
)
def test_rename_target_must_pass_the_guard(setup, new):
    vault, root, outside = setup
    with pytest.raises(PathRejected):
        vault.rename(ATLAS, new, v(root, ATLAS))
    assert files(root) == [ATLAS, "Top.md"]
    assert os.listdir(outside) == []


def test_rename_into_a_folder_link_leading_outside_is_refused(setup):
    vault, root, outside = setup
    (root / "Out").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathRejected):
        vault.rename(ATLAS, "Out/x.md", v(root, ATLAS))
    assert os.listdir(outside) == []


def test_rename_into_a_folder_link_inside_is_refused(setup):
    vault, root, _ = setup
    (root / "Alias").symlink_to(root / "Projects", target_is_directory=True)
    with pytest.raises(PathRejected):
        vault.rename("Top.md", "Alias/Top.md", v(root, "Top.md"))
    assert (root / "Top.md").exists()


def test_a_note_reached_through_a_link_is_not_renamed(setup):
    vault, root, _ = setup
    (root / "alias.md").symlink_to(root / ATLAS)
    with pytest.raises(PathRejected):
        vault.rename("alias.md", "renamed.md", v(root, ATLAS))
    assert (root / ATLAS).read_text() == ATLAS_TEXT
    assert (root / "alias.md").is_symlink()


def test_rename_of_a_missing_note(setup):
    vault, _, _ = setup
    with pytest.raises(NoteNotFound):
        vault.rename("Projects/Nope.md", "Projects/New.md", "0" * 64)


def test_a_change_between_the_check_and_the_link_is_caught(setup, monkeypatch):
    # Another program writes into the file just as it's linked: the new name
    # is removed again and the note stays where it was, with its new text.
    vault, root, _ = setup
    real_link = os.link

    def link_then_edit(src, dst, **kwargs):
        real_link(src, dst, **kwargs)
        Path(src).write_text("written meanwhile\n")

    monkeypatch.setattr(vault_module.os, "link", link_then_edit)
    with pytest.raises(VersionConflict):
        vault.rename(ATLAS, "Projects/New.md", v(root, ATLAS))
    assert files(root) == [ATLAS, "Top.md"]
    assert (root / ATLAS).read_text() == "written meanwhile\n"


def test_a_replacement_before_the_old_name_is_removed_is_caught(setup, monkeypatch):
    # Another program saves the note the safe way (a new file renamed over the
    # old one) just after the link: the old name now holds the new text and
    # must not be removed.
    vault, root, _ = setup
    real_link = os.link

    def link_then_replace(src, dst, **kwargs):
        real_link(src, dst, **kwargs)
        newer = Path(src).with_name("newer.tmp")
        newer.write_text(ATLAS_TEXT)  # same text, different file
        os.replace(newer, src)

    monkeypatch.setattr(vault_module.os, "link", link_then_replace)
    with pytest.raises(VersionConflict):
        vault.rename(ATLAS, "Projects/New.md", v(root, ATLAS))
    assert files(root) == [ATLAS, "Top.md"]


def test_a_disk_without_links_moves_nothing(setup, monkeypatch):
    vault, root, _ = setup

    def no_links(src, dst, **kwargs):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(vault_module.os, "link", no_links)
    with pytest.raises(MoveNotSupported):
        vault.rename(ATLAS, "Projects/New.md", v(root, ATLAS))
    assert files(root) == [ATLAS, "Top.md"]


# --- Trash --------------------------------------------------------------------


def test_trash_moves_the_note_into_trash_keeping_its_folders(setup):
    vault, root, _ = setup
    before = (root / ATLAS).read_bytes()
    assert vault.trash(ATLAS, version_of(before), NOW) == ".trash/Projects/Atlas.md"
    assert (root / ".trash/Projects/Atlas.md").read_bytes() == before
    assert not (root / ATLAS).exists()
    assert vault.list_notes() == ["Top.md"]


def test_trash_never_replaces_an_earlier_deleted_note(setup):
    vault, root, _ = setup
    (root / ".trash/Projects").mkdir(parents=True)
    (root / ".trash/Projects/Atlas.md").write_text("deleted last week\n")
    to = vault.trash(ATLAS, v(root, ATLAS), NOW)
    assert to == ".trash/Projects/Atlas (deleted 2031-04-16 093015).md"
    assert (root / ".trash/Projects/Atlas.md").read_text() == "deleted last week\n"
    assert (root / to).read_text() == ATLAS_TEXT


def test_trash_twice_in_the_same_second(setup):
    vault, root, _ = setup
    first = vault.trash(ATLAS, v(root, ATLAS), NOW)
    (root / ATLAS).write_text("again\n")
    second = vault.trash(ATLAS, v(root, ATLAS), NOW)
    (root / ATLAS).write_text("and again\n")
    third = vault.trash(ATLAS, v(root, ATLAS), NOW)
    assert [first, second, third] == [
        ".trash/Projects/Atlas.md",
        ".trash/Projects/Atlas (deleted 2031-04-16 093015).md",
        ".trash/Projects/Atlas (deleted 2031-04-16 093015 2).md",
    ]


def test_trash_of_a_changed_note_is_refused(setup):
    vault, root, _ = setup
    stale = v(root, ATLAS)
    (root / ATLAS).write_text("changed in Obsidian\n")
    with pytest.raises(VersionConflict):
        vault.trash(ATLAS, stale, NOW)
    assert (root / ATLAS).read_text() == "changed in Obsidian\n"
    assert not list((root / ".trash").rglob("*.md"))


@pytest.mark.parametrize("where", [".trash", ".trash/Projects"])
def test_a_trash_folder_link_leading_outside_is_refused(setup, where):
    vault, root, outside = setup
    (root / where).parent.mkdir(parents=True, exist_ok=True)
    (root / where).symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathRejected):
        vault.trash(ATLAS, v(root, ATLAS), NOW)
    assert (root / ATLAS).read_text() == ATLAS_TEXT
    assert os.listdir(outside) == []


def test_a_trash_folder_link_inside_the_vault_is_refused(setup):
    vault, root, _ = setup
    (root / ".trash").symlink_to(root / "Projects", target_is_directory=True)
    with pytest.raises(PathRejected):
        vault.trash("Top.md", v(root, "Top.md"), NOW)
    assert (root / "Top.md").exists()


def test_a_file_where_the_trash_folder_should_be_is_refused(setup):
    vault, root, _ = setup
    (root / ".trash").write_text("not a folder")
    with pytest.raises(PathRejected):
        vault.trash(ATLAS, v(root, ATLAS), NOW)
    assert (root / ATLAS).exists()


def test_a_note_reached_through_a_link_is_not_trashed(setup):
    vault, root, _ = setup
    (root / "alias.md").symlink_to(root / ATLAS)
    (root / "Shortcut").symlink_to(root / "Projects", target_is_directory=True)
    for name in ["alias.md", "Shortcut/Atlas.md"]:
        with pytest.raises(PathRejected):
            vault.trash(name, v(root, ATLAS), NOW)
    assert (root / ATLAS).read_text() == ATLAS_TEXT
    assert not (root / ".trash").exists() or not list((root / ".trash").rglob("*.md"))


def test_trash_of_a_missing_note(setup):
    vault, _, _ = setup
    with pytest.raises(NoteNotFound):
        vault.trash("Projects/Nope.md", "0" * 64, NOW)


def test_trash_needs_a_name_that_passes_the_guard(setup):
    vault, root, outside = setup
    (outside / "secret.md").write_text("secret")
    for bad in ["../outside/secret.md", ".trash/x.md", "/etc/x.md"]:
        with pytest.raises(PathRejected):
            vault.trash(bad, version_of(b"secret"), NOW)
    assert (outside / "secret.md").read_text() == "secret"


# --- Create in a folder ----------------------------------------------------------


def test_create_never_replaces(setup):
    vault, root, _ = setup
    with pytest.raises(NoteExists):
        vault.create(ATLAS, "")
    assert (root / ATLAS).read_text() == ATLAS_TEXT
