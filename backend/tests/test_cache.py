"""The SQLite cache (threat model T10): where it lives, who can read it, and
that it can always be rebuilt from the files."""

import os
import stat
from pathlib import Path

import pytest

from onyx.__main__ import main
from onyx.app import create_app
from onyx.cache import (
    REPO_ROOT,
    SCHEMA_VERSION,
    CacheLocationError,
    NoteCache,
    cache_file_for,
    default_cache_dir,
)
from onyx.config import load_settings
from onyx.vault import Vault

DEV_VAULT = Path(__file__).resolve().parents[2] / "dev-vault"


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Projects").mkdir(parents=True)
    (root / "Projects" / "Atlas.md").write_text("# Atlas\n")
    (root / "Inbox.md").write_text("# Inbox\n")
    return Vault(root)


# --- Location -------------------------------------------------------------


def test_default_location_on_macos():
    path = default_cache_dir({"HOME": "/home-x"}, platform="darwin")
    assert path == Path("/home-x/Library/Caches/onyx-sheiko")


def test_default_location_elsewhere():
    assert default_cache_dir({"HOME": "/home-x"}, platform="linux") == Path(
        "/home-x/.cache/onyx-sheiko"
    )
    assert default_cache_dir({"HOME": "/home-x", "XDG_CACHE_HOME": "/xdg"}, "linux") == Path(
        "/xdg/onyx-sheiko"
    )


def test_env_override():
    assert default_cache_dir({"HOME": "/h", "ONYX_CACHE_DIR": "/c"}, "darwin") == Path("/c")


def test_real_default_is_outside_the_vault_and_the_repo():
    path = Path(os.path.realpath(default_cache_dir({"HOME": str(Path.home())})))
    assert not path.is_relative_to(REPO_ROOT)
    assert not path.is_relative_to(DEV_VAULT.resolve())


def test_cache_inside_the_vault_is_refused(vault):
    with pytest.raises(CacheLocationError, match="inside the vault"):
        cache_file_for(vault.root, vault.root / "cache")
    with pytest.raises(CacheLocationError, match="inside the vault"):
        cache_file_for(vault.root, vault.root)


def test_cache_inside_the_repo_is_refused(vault):
    with pytest.raises(CacheLocationError, match="inside the repository"):
        cache_file_for(vault.root, REPO_ROOT / "backend" / "cache")


def test_cache_reached_through_a_symlink_into_the_vault_is_refused(vault, tmp_path):
    link = tmp_path / "innocent-looking"
    link.symlink_to(vault.root, target_is_directory=True)
    with pytest.raises(CacheLocationError):
        cache_file_for(vault.root, link)


def test_file_name_does_not_reveal_the_vault(vault, tmp_path):
    path = cache_file_for(vault.root, tmp_path / "c")
    assert "vault" not in str(path.parent)
    assert vault.root.name not in path.stem.removeprefix("vault-")
    assert path.suffix == ".sqlite3"


def test_each_vault_gets_its_own_file(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    assert cache_file_for(first, tmp_path / "c") != cache_file_for(second, tmp_path / "c")


def test_app_refuses_to_start_with_cache_in_vault(monkeypatch, capsys):
    monkeypatch.setenv("ONYX_CACHE_DIR", str(DEV_VAULT / "cache"))
    assert main(["--vault", str(DEV_VAULT)]) == 2
    assert "inside the vault" in capsys.readouterr().err
    assert not (DEV_VAULT / "cache").exists()


# --- Privacy ----------------------------------------------------------------


def test_cache_folder_and_file_are_private(vault, tmp_path):
    cache = NoteCache(vault, tmp_path / "c")
    cache.rebuild()
    assert stat.S_IMODE(cache.path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(cache.path.stat().st_mode) == 0o600


def test_rebuild_tightens_an_existing_open_folder(vault, tmp_path):
    folder = tmp_path / "c"
    folder.mkdir(mode=0o755)
    folder.chmod(0o755)
    NoteCache(vault, folder).rebuild()
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700


# --- Rebuildable from the files -----------------------------------------------


def test_rebuild_indexes_every_note(vault, tmp_path):
    cache = NoteCache(vault, tmp_path / "c")
    assert cache.rebuild() == 2
    assert cache.paths() == ["Inbox.md", "Projects/Atlas.md"]
    assert cache.version("Inbox.md") == vault.read("Inbox.md").version
    assert cache.schema_version() == SCHEMA_VERSION


def test_deleting_the_cache_is_safe(vault, tmp_path):
    cache = NoteCache(vault, tmp_path / "c")
    cache.rebuild()
    before = cache.paths()
    cache.path.unlink()
    cache.rebuild()
    assert cache.paths() == before


def test_rebuild_picks_up_changes_made_on_disk(vault, tmp_path):
    cache = NoteCache(vault, tmp_path / "c")
    cache.rebuild()
    (vault.root / "Inbox.md").write_text("# Inbox\n\nEdited elsewhere.\n")
    (vault.root / "New.md").write_text("# New\n")
    (vault.root / "Projects" / "Atlas.md").unlink()
    cache.rebuild()
    assert cache.paths() == ["Inbox.md", "New.md"]
    assert cache.version("Inbox.md") == vault.read("Inbox.md").version


def test_a_corrupt_cache_is_replaced(vault, tmp_path):
    cache = NoteCache(vault, tmp_path / "c")
    cache.rebuild()
    cache.path.write_bytes(b"not a database")
    cache.rebuild()
    assert cache.paths() == ["Inbox.md", "Projects/Atlas.md"]


def test_cache_never_writes_into_the_vault(vault, tmp_path):
    before = sorted(p.relative_to(vault.root) for p in vault.root.rglob("*"))
    NoteCache(vault, tmp_path / "c").rebuild()
    assert sorted(p.relative_to(vault.root) for p in vault.root.rglob("*")) == before


def test_app_start_builds_the_cache_from_dev_vault(private_cache_dir):
    app = create_app(load_settings(DEV_VAULT))
    cache = app.state.cache
    assert cache.path.parent == Path(os.path.realpath(private_cache_dir))
    assert cache.paths() == app.state.vault.list_notes()
    assert len(cache.paths()) == 28
