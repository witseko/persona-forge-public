"""Build the limited public edition as a fresh folder, leaving this repository untouched.

The private repository keeps every instrument. The public edition drops instrument
files and translation overlays whose permission is unclear in `data/permissions.json`,
then scans the copy for any leftover item text from what was dropped. Only files
tracked by git are copied. The output is a plain folder with no Git history, so
withheld text cannot leak through old commits.

Usage: `make public-export DEST=../persona-forge-public`
"""

import argparse
import json
import shutil
import subprocess  # noqa: S404 - runs a fixed git command with an argument list
import sys
from pathlib import Path

from persona_forge.files import PROJECT_ROOT, read_json_file
from persona_forge.permissions import load_permissions

# Internal planning notes with account details; useful only in the private repository.
PRIVATE_ONLY_FILES = {"PLAN.md"}

# Item texts shorter than this are too generic ("Yes", "Often") to flag as a leak.
MIN_LEAK_TEXT_LENGTH = 20


class PublicExportError(RuntimeError):
    """Raised when the export cannot be built safely."""


def candidate_files(root: Path = PROJECT_ROOT) -> list[str]:
    """List files tracked by git, as paths relative to `root`.

    Untracked files are never copied, so stray local notes cannot reach the public
    edition. Commit new files before exporting.
    """
    git = shutil.which("git")
    if git is None:
        raise PublicExportError("git is required to list project files")
    result = subprocess.run(  # noqa: S603 - fixed arguments, no shell
        [git, "ls-files", "-z", "--cached"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    paths = result.stdout.decode("utf-8").split("\0")
    return sorted(path for path in paths if path and (root / path).is_file())


def withheld_files(root: Path = PROJECT_ROOT) -> set[str]:
    """Return relative paths of instrument data the public edition must not ship."""
    withheld = set()
    for instrument_id, permission in load_permissions().items():
        if not permission.public:
            withheld.add(f"data/instruments/{instrument_id}.json")
        if not permission.translations_public:
            for overlay in (root / "data" / "languages").glob(
                f"*/instruments/{instrument_id}.json"
            ):
                withheld.add(overlay.relative_to(root).as_posix())
    return withheld


def withheld_instrument_ids(withheld: set[str]) -> set[str]:
    """Return the instrument ids whose English source file is withheld."""
    return {Path(path).stem for path in withheld if path.startswith("data/instruments/")}


def withheld_texts(root: Path, withheld: set[str]) -> set[str]:
    """Collect item text from withheld files, for the leak scan."""
    texts = set()
    for relative in withheld:
        raw = read_json_file(root / relative)
        items = raw["items"]
        # Source instruments list item objects; translation overlays map item id to text.
        values = items.values() if isinstance(items, dict) else [item["text"] for item in items]
        texts.update(text for text in values if len(text) >= MIN_LEAK_TEXT_LENGTH)
    return texts


def remove_from_manifests(destination: Path, withheld: set[str]) -> None:
    """Drop withheld instruments and translations from each copied language manifest."""
    withheld_sources = withheld_instrument_ids(withheld)
    for manifest_path in (destination / "data" / "languages").glob("*/manifest.json"):
        code = manifest_path.parent.name
        dropped = withheld_sources | {
            Path(path).stem
            for path in withheld
            if path.startswith(f"data/languages/{code}/instruments/")
        }
        if not dropped:
            continue
        manifest = read_json_file(manifest_path)
        manifest["instrument_ids"] = [
            item for item in manifest["instrument_ids"] if item not in dropped
        ]
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def remove_from_sample_answers(destination: Path, withheld: set[str]) -> None:
    """Drop answers to withheld instruments from sample answer files, so samples still load."""
    withheld_sources = withheld_instrument_ids(withheld)
    for sample_path in (destination / "tests" / "fixtures").glob("answers_*.json"):
        sample = read_json_file(sample_path)
        instruments = sample.get("instruments", {})
        if not withheld_sources & set(instruments):
            continue
        for instrument_id in withheld_sources:
            instruments.pop(instrument_id, None)
        sample_path.write_text(json.dumps(sample, indent=2, ensure_ascii=False) + "\n")


def find_leaks(destination: Path, texts: set[str]) -> list[str]:
    """Return copied files that still contain withheld item text."""
    leaks = []
    for path in sorted(destination.rglob("*")):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary files cannot hold questionnaire text in a usable form
        if any(text in content for text in texts):
            leaks.append(path.relative_to(destination).as_posix())
    return leaks


def export_public_edition(destination: Path, root: Path = PROJECT_ROOT) -> list[str]:
    """Copy the public edition into a new `destination` folder and return what was left out.

    Raises:
        PublicExportError: if the destination exists or sits inside the repository, a
            tracked file is a symlink, or the copy still contains withheld item text
            (the copy is then removed).
    """
    destination = destination.resolve()
    if destination.exists():
        raise PublicExportError(f"{destination} already exists; choose a new folder")
    if destination.is_relative_to(root.resolve()):
        raise PublicExportError("the destination must be outside this repository")
    withheld = withheld_files(root)
    texts = withheld_texts(root, withheld)
    left_out = withheld | PRIVATE_ONLY_FILES
    files = [relative for relative in candidate_files(root) if relative not in left_out]
    links = [relative for relative in files if (root / relative).is_symlink()]
    if links:
        # A link could pull a file from outside the repository into the release.
        raise PublicExportError("tracked symlinks are not exported: " + ", ".join(links))
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    remove_from_manifests(destination, withheld)
    remove_from_sample_answers(destination, withheld)
    leaks = find_leaks(destination, texts)
    if leaks:
        shutil.rmtree(destination)
        raise PublicExportError("withheld item text found in: " + ", ".join(leaks))
    return sorted(left_out)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for `make public-export`."""
    parser = argparse.ArgumentParser(description="Build the limited public edition.")
    parser.add_argument("destination", type=Path, help="new folder outside this repository")
    args = parser.parse_args(argv)
    try:
        withheld = export_public_edition(args.destination)
    except PublicExportError as error:
        print(f"Public export failed: {error}", file=sys.stderr)
        return 1
    print(f"Public edition written to {args.destination.resolve()}")
    print("Left out:")
    for path in withheld:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
