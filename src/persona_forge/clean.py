"""Reset a questionnaire session by archiving its files and removing managed links."""

import tempfile
from pathlib import Path

from persona_forge.links import uninstall

# Only these session outputs move. Unrelated files and earlier backups stay put.
SESSION_PATHS = (
    "answers.json",
    "profile.json",
    "report.html",
    "polished-profile.json",
    "claude",
    "codex",
)


def clean_session(out_dir: Path, home: Path) -> list[str]:
    """Archive session outputs under out/backups/ without deleting personal answers."""
    if out_dir.is_symlink() or (out_dir.exists() and not out_dir.is_dir()):
        raise ValueError("clean needs a regular output directory, not a file or symlink")
    backups = out_dir / "backups"
    if backups.is_symlink() or (backups.exists() and not backups.is_dir()):
        raise ValueError("clean needs a regular backups directory, not a file or symlink")
    entries = [out_dir / name for name in SESSION_PATHS]
    entries = [path for path in entries if path.exists() or path.is_symlink()]
    log = []
    try:
        if entries:
            backups.mkdir(mode=0o700, exist_ok=True)
            # mkdtemp creates a unique, owner-only directory, even for rapid resets.
            backup = Path(tempfile.mkdtemp(prefix="session-", dir=backups))
            for path in entries:
                path.rename(backup / path.name)
            log.append(f"Session backed up to {backup}")
        else:
            log.append("No saved session to clean.")
        log.extend(uninstall(out_dir, home))
    except OSError as error:
        raise ValueError(
            f"could not clean session: {error}; any archived files were kept"
        ) from error
    log.append("To start in another language, choose it in `make settings` first.")
    return log
