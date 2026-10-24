"""Update the public repository's working copy from a fresh public export, then commit.

Steps: build the public edition in a temporary folder, mirror it into the public
repository (tracked files that no longer exist are removed; `.git` is never touched),
run that repository's tests and lint, and commit. Pushing stays a manual step, because
a public push cannot be taken back.

Usage: `make public-sync` (or `make public-sync PUBLIC=<path to the public repository>`)
"""

import argparse
import os
import shutil
import subprocess  # noqa: S404 - runs fixed git and make commands with argument lists
import sys
import tempfile
from pathlib import Path

from persona_forge.files import PROJECT_ROOT
from persona_forge.public_export import PublicExportError, candidate_files, export_public_edition

COMMIT_MESSAGE = "update public edition"


def _run(command: list[str], cwd: Path) -> str:
    """Run a fixed command without a shell and return its standard output."""
    executable = shutil.which(command[0])
    if executable is None:
        raise PublicExportError(f"{command[0]} is required")
    # Drop this repository's virtual environment so the public copy uses its own.
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    result = subprocess.run(  # noqa: S603 - fixed arguments, no shell
        [executable, *command[1:]], cwd=cwd, capture_output=True, text=True, env=environment
    )
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip().splitlines()[-20:]
        raise PublicExportError(f"{' '.join(command)} failed:\n" + "\n".join(output))
    return result.stdout


def check_target(target: Path, root: Path) -> None:
    """Require a clean, separate git repository, so nothing unsaved gets overwritten."""
    if target.is_relative_to(root.resolve()) or root.resolve().is_relative_to(target):
        raise PublicExportError("the public repository must be outside this repository")
    if not (target / ".git").is_dir():
        raise PublicExportError(f"{target} is not a git repository")
    if _run(["git", "status", "--porcelain"], target).strip():
        raise PublicExportError(f"{target} has uncommitted changes; commit or discard them first")


def mirror(edition: Path, target: Path) -> None:
    """Make the target's tracked files match the exported edition exactly."""
    exported = {
        path.relative_to(edition).as_posix() for path in edition.rglob("*") if path.is_file()
    }
    for relative in candidate_files(target):
        if relative not in exported:
            (target / relative).unlink()
    for relative in sorted(exported):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(edition / relative, destination)


def sync_public_repository(
    target: Path, root: Path = PROJECT_ROOT, run_checks: bool = True
) -> bool:
    """Refresh and commit the public repository. Returns False when nothing changed.

    Raises:
        PublicExportError: if the target is unsafe, the export fails, or the public
            repository's checks fail (its working copy is then left for inspection).
    """
    target = target.resolve()
    check_target(target, root)
    with tempfile.TemporaryDirectory() as temporary:
        edition = Path(temporary) / "edition"
        export_public_edition(edition, root)
        mirror(edition, target)
    if not _run(["git", "status", "--porcelain"], target).strip():
        return False
    if run_checks:
        _run(["make", "test", "lint"], target)
    _run(["git", "add", "-A"], target)
    _run(["git", "commit", "-q", "-m", COMMIT_MESSAGE], target)
    return True


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for `make public-sync`."""
    parser = argparse.ArgumentParser(description="Update and commit the public repository.")
    parser.add_argument("target", type=Path, help="path to the public repository")
    args = parser.parse_args(argv)
    try:
        changed = sync_public_repository(args.target)
    except PublicExportError as error:
        print(f"Public sync failed: {error}", file=sys.stderr)
        return 1
    target = args.target.resolve()
    if not changed:
        print(f"{target} is already up to date.")
        return 0
    print(f"Committed '{COMMIT_MESSAGE}' in {target}. Review it, then push:")
    print(f"  git -C {target} show --stat")
    print(f"  git -C {target} push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
