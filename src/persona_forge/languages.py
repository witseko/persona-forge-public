"""Discover data-only language plugins and translate UI text without an English fallback."""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from string import Formatter

from persona_forge.files import DATA_DIR, read_json_file
from persona_forge.instruments import load_instrument_by_id
from persona_forge.language_constants import (
    CODE_PATTERN,
    LANGUAGE_DIR,
    NUMBER_FIELDS,
    TRANSLATED_FIELDS,
)
from persona_forge.language_validation import (
    LanguageManifest,
    language_text,
    message_fields,
    parse_manifest,
    parse_messages,
)
from persona_forge.translation_validation import apply_translation


def _plugin_folder(code: str, directory: Path) -> Path:
    """Resolve only safe plugin identifiers and refuse symlinked resource paths."""
    if not isinstance(code, str) or not CODE_PATTERN.fullmatch(code):
        raise ValueError("invalid language code")
    folder = directory / code
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError(f"language plugin is not installed: {code}")
    for resource in ("manifest.json", "messages.json", "instruments"):
        if (folder / resource).is_symlink():
            raise ValueError("language plugin resources cannot be symlinks")
    return folder


def _manifest(folder: Path) -> LanguageManifest:
    """Read a bounded manifest and validate its instrument capabilities."""
    source_ids = {path.stem for path in (DATA_DIR / "instruments").glob("*.json")}
    return parse_manifest(read_json_file(folder / "manifest.json"), folder.name, source_ids)


def available_languages(directory: Path = LANGUAGE_DIR) -> tuple[str, ...]:
    """Discover enabled plugins by folder, without importing or executing plugin code."""
    codes = []
    for folder in sorted(directory.iterdir()):
        if folder.is_symlink() or not folder.is_dir() or not CODE_PATTERN.fullmatch(folder.name):
            continue
        manifest = _manifest(_plugin_folder(folder.name, directory))
        if manifest.status == "complete":
            codes.append(manifest.code)
    return tuple(codes)


def _message_pattern(source: str) -> tuple[re.Pattern[str], int]:
    """Compile a trusted English format string and its literal specificity."""
    pattern = ""
    specificity = 0
    seen = set()
    for literal, name, _, _ in Formatter().parse(source):
        pattern += re.escape(literal)
        specificity += len(literal)
        if name is None:
            continue
        value_pattern = r"\d+" if name in NUMBER_FIELDS else ".+?"
        if name == "bar":
            value_pattern = "[#-]{10}"
        pattern += f"(?P={name})" if name in seen else f"(?P<{name}>{value_pattern})"
        seen.add(name)
    return re.compile(pattern, re.DOTALL), specificity


def _templates(messages: dict[str, str]) -> list[tuple[re.Pattern[str], str]]:
    """Match specific messages before generic title/body and title/description templates."""
    templates = []
    for source, translated in messages.items():
        if message_fields(source):
            pattern, specificity = _message_pattern(source)
            templates.append((specificity, pattern, translated))
    templates.sort(key=lambda entry: entry[0], reverse=True)
    return [(pattern, translated) for _, pattern, translated in templates]


def _instrument_literals(folder: Path, manifest: LanguageManifest) -> set[str]:
    """Validate every declared overlay before allowing a plugin to display anything."""
    if manifest.code == "en":
        return set()
    directory = folder / "instruments"
    if {path.stem for path in directory.glob("*.json")} != manifest.instrument_ids:
        raise ValueError(f"language instrument coverage differs from manifest: {manifest.code}")
    literals = set()
    for instrument_id in manifest.instrument_ids:
        path = directory / f"{instrument_id}.json"
        if path.is_symlink():
            raise ValueError("instrument translations cannot be symlinks")
        raw = read_json_file(path)
        apply_translation(load_instrument_by_id(instrument_id), raw, manifest.code)
        literals.add(language_text(raw["instructions"]))
        literals.update(language_text(value) for value in raw["items"].values())
        for labels in raw["response_sets"].values():
            literals.update(language_text(value) for value in labels.values())
    return literals


@dataclass
class LanguagePack:
    """A language's UI catalog and instrument capabilities behind one text lookup."""

    code: str
    name: str
    instrument_ids: frozenset[str]
    messages: dict[str, str]
    instrument_dir: Path
    _literals: set[str] = field(default_factory=set, repr=False)
    _templates: list[tuple[re.Pattern[str], str]] = field(default_factory=list, repr=False)

    def _format(self, translated: str, values: dict[str, object]) -> str:
        """Translate display fragments while preserving numbers, paths and exact payloads."""
        parts = {}
        for name, value in values.items():
            parts[name] = self.text(str(value)) if name in TRANSLATED_FIELDS else value
        return translated.format_map(parts)

    def text(self, source: str, **values: object) -> str:
        """Translate a message or template, failing explicitly when coverage is missing."""
        if not source:
            return source
        if self.code == "en":
            return source.format_map(values) if values else source
        if source in self.messages:
            return self._format(self.messages[source], values) if values else self.messages[source]
        if source in self._literals:
            return source
        for pattern, translated in self._templates:
            match = pattern.fullmatch(source)
            if match:
                return self._format(translated, match.groupdict())
        raise ValueError(f"missing {self.code} UI translation: {source[:100]}")


@lru_cache(maxsize=32)
def load_language(code: str, directory: Path = LANGUAGE_DIR) -> LanguagePack:
    """Load and validate a complete pack before an interactive session can start."""
    folder = _plugin_folder(code, directory)
    manifest = _manifest(folder)
    if manifest.status != "complete":
        raise ValueError(f"language plugin is not complete: {code}")
    reference_folder = _plugin_folder("en", directory)
    messages = parse_messages(
        read_json_file(folder / "messages.json"),
        read_json_file(reference_folder / "messages.json"),
        code,
    )
    literals = set(messages.values()) | _instrument_literals(folder, manifest)
    return LanguagePack(
        code,
        manifest.name,
        manifest.instrument_ids,
        messages,
        folder / "instruments",
        literals,
        _templates(messages),
    )
