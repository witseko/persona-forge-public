"""Small file helpers: bounded JSON reads, atomic private writes and path containment."""

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

# Data files shipped with the project live here; tests may point loaders elsewhere.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class DataFileError(ValueError):
    """Raised when a JSON file is missing, too large, not a regular file or malformed."""


def read_json_file(path: Path, max_bytes: int = 1_000_000) -> Any:
    """Read one regular UTF-8 JSON file, refusing anything larger than `max_bytes`."""
    try:
        mode = path.stat().st_mode
    except FileNotFoundError as error:
        raise DataFileError(f"{path.name} does not exist") from error
    if not stat.S_ISREG(mode):
        raise DataFileError(f"{path.name} must be a regular file")
    with path.open("rb") as handle:
        content = handle.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise DataFileError(f"{path.name} exceeds {max_bytes} bytes")
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DataFileError(f"{path.name} is not valid UTF-8 JSON") from error


def write_private_text(path: Path, text: str) -> None:
    """Write text atomically with owner-only permissions (personal data stays private).

    The content goes to a temporary file in the same directory, then replaces the
    target in one step, so an interrupted run never leaves a half-written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def write_private_json(path: Path, data: Any) -> None:
    """Write JSON atomically with owner-only permissions."""
    write_private_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_private_text_if_changed(path: Path, text: str) -> bool:
    """Write only when the content differs, so unchanged files keep their timestamps.

    Returns True when the file was written.
    """
    if path.is_file() and not path.is_symlink() and path.read_text(encoding="utf-8") == text:
        return False
    write_private_text(path, text)
    return True
