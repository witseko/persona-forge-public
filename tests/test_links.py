"""Symlink management: idempotent install, backups, own-links-only removal."""

import os
from datetime import datetime
from pathlib import Path

import pytest

from persona_forge.links import install, planned_links, status, uninstall


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    """A minimal generated output tree."""
    out = tmp_path / "out"
    (out / "claude" / "rules").mkdir(parents=True)
    (out / "claude" / "output-styles").mkdir()
    (out / "codex").mkdir()
    (out / "claude" / "rules" / "persona-forge-profile.md").write_text("profile")
    (out / "claude" / "output-styles" / "pf-mentor.md").write_text("style")
    (out / "codex" / "pf-me.config.toml").write_text("toml")
    return out


def test_install_is_idempotent(out_dir: Path, tmp_path: Path) -> None:
    """A second install reports every link as ok and changes nothing."""
    home = tmp_path / "home"
    first = install(out_dir, home)
    assert sum(line.startswith("linked") for line in first) == 3
    second = install(out_dir, home)
    assert all(line.startswith("ok") for line in second)


def test_install_backs_up_existing_files(out_dir: Path, tmp_path: Path) -> None:
    """Anything in the way is renamed, never deleted."""
    home = tmp_path / "home"
    target = home / ".codex" / "pf-me.config.toml"
    target.parent.mkdir(parents=True)
    target.write_text("mine")
    install(out_dir, home, now=datetime(2026, 1, 2, 3, 4, 5))
    backup = home / ".codex" / "pf-me.config.toml.bak.20260102-030405"
    assert backup.read_text() == "mine"
    assert target.is_symlink()


def test_uninstall_leaves_foreign_links_and_files(out_dir: Path, tmp_path: Path) -> None:
    """Only links into out/ are removed; other links and files survive."""
    home = tmp_path / "home"
    install(out_dir, home)
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text("x")
    foreign = home / ".claude" / "output-styles" / "pf-foreign.md"
    foreign.symlink_to(elsewhere)
    own_file = home / ".codex" / "config.toml"
    own_file.write_text("user config")
    uninstall(out_dir, home)
    assert foreign.is_symlink()
    assert own_file.read_text() == "user config"
    assert not (home / ".codex" / "pf-me.config.toml").exists()


def test_dangling_own_links_are_cleaned_on_install(out_dir: Path, tmp_path: Path) -> None:
    """When an ego is dropped, its stale link is removed on the next install."""
    home = tmp_path / "home"
    install(out_dir, home)
    (out_dir / "claude" / "output-styles" / "pf-mentor.md").unlink()
    log = install(out_dir, home)
    assert not os.path.lexists(home / ".claude" / "output-styles" / "pf-mentor.md")
    assert any("target no longer generated" in line for line in log)


def test_protected_names_are_never_removed(out_dir: Path, tmp_path: Path) -> None:
    """Even a global instruction file that points into out/ is left alone by uninstall."""
    home = tmp_path / "home"
    install(out_dir, home)
    agents = home / ".codex" / "AGENTS.md"
    agents.symlink_to(out_dir / "codex" / "pf-me.config.toml")
    uninstall(out_dir, home)
    assert agents.is_symlink()
    assert all(link.link_path.name != "AGENTS.md" for link in planned_links(out_dir, home))


def test_status_reports_missing_linked_and_blocked(out_dir: Path, tmp_path: Path) -> None:
    """Status distinguishes the three states."""
    home = tmp_path / "home"
    assert all(line.startswith("missing") for line in status(out_dir, home))
    install(out_dir, home)
    assert all(line.startswith("linked") for line in status(out_dir, home))
    link = home / ".codex" / "pf-me.config.toml"
    link.unlink()
    link.write_text("other")
    assert any(line.startswith("blocked") for line in status(out_dir, home))
