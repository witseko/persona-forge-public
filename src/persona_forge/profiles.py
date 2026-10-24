"""Keep named questionnaire sessions separate inside the private output folder."""

import re
import shutil
from pathlib import Path

from persona_forge.clean import SESSION_PATHS


def profile_directory(root: Path, name: str) -> Path:
    """Resolve a bounded profile slug without following redirected directories."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        raise ValueError("profile names need 1-64 lowercase letters, digits and single hyphens")
    directory = root / "profiles" / name
    for path in (root, root / "profiles", directory):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError("profiles need regular directories, not files or symlinks")
    return directory


def list_profiles(root: Path) -> list[str]:
    """List stored profile names without reading personal answers."""
    profiles = root / "profiles"
    if not profiles.exists():
        return []
    if root.is_symlink() or profiles.is_symlink() or not profiles.is_dir():
        raise ValueError("profiles need regular directories")
    names = []
    for path in sorted(profiles.iterdir()):
        profile_directory(root, path.name)
        if path.is_dir():
            names.append(path.name)
    return names


def create_profile(root: Path, name: str) -> Path:
    """Create an empty private profile, refusing to overwrite an existing one."""
    directory = profile_directory(root, name)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.parent.mkdir(mode=0o700, exist_ok=True)
    if directory.exists():
        raise ValueError(f"profile already exists: {name}")
    directory.mkdir(mode=0o700)
    return directory


def preserve_legacy(root: Path, name: str) -> Path:
    """Copy the original single-user session into a new profile, keeping the original."""
    profile_directory(root, name)
    if not (root / "answers.json").is_file():
        raise ValueError("no original session to preserve")
    entries = [root / entry for entry in SESSION_PATHS]
    entries = [entry for entry in entries if entry.exists() or entry.is_symlink()]
    # Generated session trees should contain only local regular files and directories.
    for entry in entries:
        if entry.is_symlink() or (entry.is_dir() and any(p.is_symlink() for p in entry.rglob("*"))):
            raise ValueError("cannot copy a session containing symlinks")
    directory = create_profile(root, name)
    for entry in entries:
        destination = directory / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination)
        else:
            shutil.copy2(entry, destination)
    return directory
