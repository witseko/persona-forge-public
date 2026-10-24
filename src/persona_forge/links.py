"""Install or remove symlinks from the agents' config folders to generated files in out/.

A port of agent-config/links.sh: anything already in the way is moved to
`<name>.bak.<timestamp>` (never deleted), installing twice is a no-op, and uninstall
removes only links that point into this project's out/ folder.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from persona_forge.render_claude import RULES_FILE_NAME

LOGGER = logging.getLogger(__name__)

# Files this project must never create, replace or remove, whatever out/ contains.
PROTECTED_NAMES = {"CLAUDE.md", "AGENTS.md", "AGENTS.override.md", "config.toml", "settings.json"}


@dataclass(frozen=True)
class Link:
    """One managed link: `link_path` should point at `target`."""

    target: Path
    link_path: Path


def planned_links(out_dir: Path, home: Path) -> list[Link]:
    """Every link for the files currently in out/."""
    out_dir = out_dir.resolve()
    links = []
    rules = out_dir / "claude" / "rules" / RULES_FILE_NAME
    if rules.is_file():
        links.append(Link(rules, home / ".claude" / "rules" / RULES_FILE_NAME))
    for style in sorted((out_dir / "claude" / "output-styles").glob("pf-*.md")):
        links.append(Link(style, home / ".claude" / "output-styles" / style.name))
    for config in sorted((out_dir / "codex").glob("pf-*.config.toml")):
        links.append(Link(config, home / ".codex" / config.name))
    for link in links:
        if link.link_path.name in PROTECTED_NAMES:
            raise ValueError(f"refusing to manage protected file {link.link_path}")
    return links


def _points_into(link_path: Path, out_dir: Path) -> bool:
    """True when `link_path` is a symlink whose target lies inside out/."""
    if not link_path.is_symlink():
        return False
    target = Path(os.readlink(link_path))
    if not target.is_absolute():
        target = link_path.parent / target
    resolved_out = out_dir.resolve()
    return target == resolved_out or resolved_out in target.parents


def install(out_dir: Path, home: Path, now: datetime | None = None) -> list[str]:
    """Create missing links, backing up anything in the way. Returns a log of actions."""
    links = planned_links(out_dir, home)
    if not links:
        raise ValueError("no generated files to link; complete this profile's setup first")
    log = _unlink_other_profiles(out_dir, home)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    for link in links:
        path = link.link_path
        if path.is_symlink() and Path(os.readlink(path)) == link.target:
            log.append(f"ok       {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            backup = path.with_name(f"{path.name}.bak.{stamp}")
            path.rename(backup)
            log.append(f"backup   {path} -> {backup}")
        path.symlink_to(link.target)
        log.append(f"linked   {path} -> {link.target}")
    log += remove_dangling(out_dir, home)
    return log


def _unlink_other_profiles(out_dir: Path, home: Path) -> list[str]:
    """Remove active links to other profiles before installing a complete replacement."""
    root = out_dir.parent.parent if out_dir.parent.name == "profiles" else out_dir
    log = []
    for directory in managed_directories(home):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            managed_name = path.name == RULES_FILE_NAME or (
                path.name.startswith("pf-")
                and (path.name.endswith(".md") or path.name.endswith(".config.toml"))
            )
            same_profile = _points_into(path, out_dir)
            if out_dir == root and _points_into(path, root / "profiles"):
                same_profile = False
            if managed_name and _points_into(path, root) and not same_profile:
                path.unlink()
                log.append(f"removed  {path} (switching profile)")
    return log


def managed_directories(home: Path) -> list[Path]:
    """Folders where this project places links."""
    return [home / ".claude" / "rules", home / ".claude" / "output-styles", home / ".codex"]


def remove_dangling(out_dir: Path, home: Path) -> list[str]:
    """Remove our own links whose target no longer exists (for example a dropped ego)."""
    log = []
    for directory in managed_directories(home):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if _points_into(path, out_dir) and not path.exists():
                path.unlink()
                log.append(f"removed  {path} (target no longer generated)")
    return log


def uninstall(out_dir: Path, home: Path) -> list[str]:
    """Remove every link that points into out/; leave everything else, including backups."""
    log = []
    for directory in managed_directories(home):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.name in PROTECTED_NAMES:
                continue
            if _points_into(path, out_dir):
                path.unlink()
                log.append(f"removed  {path}")
    if not log:
        log.append("nothing to remove")
    log.append("Backups from earlier installs (*.bak.*) were kept; restore one by renaming it.")
    return log


def status(out_dir: Path, home: Path) -> list[str]:
    """Describe each planned link: linked, missing or blocked by another file."""
    lines = []
    for link in planned_links(out_dir, home):
        path = link.link_path
        if path.is_symlink() and Path(os.readlink(path)) == link.target:
            lines.append(f"linked   {path}")
        elif path.exists() or path.is_symlink():
            lines.append(f"blocked  {path} (another file is there; `make link` backs it up)")
        else:
            lines.append(f"missing  {path}")
    return lines or ["no generated files yet; run `make setup`"]
