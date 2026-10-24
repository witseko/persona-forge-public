"""Saved CLI settings: the active profile and the language for new questionnaires.

Settings live in the private, git-ignored output folder as `settings.json`. They hold no
answers or results, only a profile name and a language code, and both are validated on
every read so a hand-edited file cannot point outside the profiles folder.
"""

from dataclasses import dataclass
from pathlib import Path

from persona_forge.files import read_json_file, write_private_json
from persona_forge.languages import available_languages
from persona_forge.profiles import profile_directory

SETTINGS_FILE = "settings.json"
SETTINGS_KEYS = {"version", "profile", "language"}


@dataclass(frozen=True)
class Settings:
    """The active profile (None until chosen) and the language for new sessions."""

    profile: str | None = None
    language: str | None = None


def settings_path(root: Path) -> Path:
    """Where settings are stored for one output folder."""
    return root / SETTINGS_FILE


def _checked(root: Path, profile: object, language: object) -> Settings:
    """Validate a profile slug and an installed language code."""
    if profile is not None:
        if not isinstance(profile, str):
            raise ValueError("settings profile must be a name")
        profile_directory(root, profile)
    if language is not None and language not in available_languages():
        raise ValueError("settings language is not an installed language plugin")
    return Settings(profile, language)  # type: ignore[arg-type]


def load_settings(root: Path) -> Settings:
    """Read saved settings, or defaults when none are saved yet."""
    path = settings_path(root)
    if path.is_symlink():
        raise ValueError("settings must be a regular file")
    if not path.exists():
        return Settings()
    data = read_json_file(path, max_bytes=10_000)
    if not isinstance(data, dict) or set(data) - SETTINGS_KEYS:
        raise ValueError("settings.json has unexpected content")
    return _checked(root, data.get("profile"), data.get("language"))


def save_settings(root: Path, settings: Settings) -> None:
    """Validate and store settings with owner-only permissions."""
    checked = _checked(root, settings.profile, settings.language)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_private_json(
        settings_path(root),
        {"version": 1, "profile": checked.profile, "language": checked.language},
    )
