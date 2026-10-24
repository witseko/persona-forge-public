"""Validate language manifests and message catalogs without performing file operations."""

import unicodedata
from dataclasses import dataclass
from string import Formatter

from persona_forge.language_constants import (
    CORE_INSTRUMENT_IDS,
    INSTRUMENT_PATTERN,
    MANIFEST_FIELDS,
)


@dataclass(frozen=True)
class LanguageManifest:
    """Validated identity, readiness and instrument coverage of a language plugin."""

    code: str
    name: str
    status: str
    instrument_ids: frozenset[str]


def language_text(value: object) -> str:
    """Require bounded plain text, allowing line breaks but no terminal controls."""
    if not isinstance(value, str) or not value.strip() or len(value) > 10000:
        raise ValueError("language text must be non-empty plain text")
    if any(unicodedata.category(letter).startswith("C") and letter != "\n" for letter in value):
        raise ValueError("language text cannot contain control characters")
    return value


def message_fields(text: str) -> set[str]:
    """Accept named placeholders without attributes, conversions or format expressions."""
    fields = set()
    for _, name, spec, conversion in Formatter().parse(text):
        if name is None:
            continue
        if not name.isidentifier() or spec or conversion:
            raise ValueError("language messages use plain named placeholders only")
        fields.add(name)
    return fields


def _instrument_ids(raw: object, source_ids: set[str]) -> frozenset[str]:
    """Require a non-empty list of unique known instrument identifiers."""
    if not isinstance(raw, list) or not raw:
        raise ValueError("language instrument_ids must be a non-empty list")
    if not all(isinstance(entry, str) and INSTRUMENT_PATTERN.fullmatch(entry) for entry in raw):
        raise ValueError("language instrument_ids must contain instrument slugs")
    if len(raw) != len(set(raw)) or not set(raw) <= source_ids:
        raise ValueError("language instrument_ids must be unique known instruments")
    if not set(raw) & CORE_INSTRUMENT_IDS:
        raise ValueError("a language pack needs a core personality instrument")
    return frozenset(raw)


def parse_manifest(raw: object, code: str, source_ids: set[str]) -> LanguageManifest:
    """Validate a manifest against its folder name and the canonical instrument catalog."""
    if not isinstance(raw, dict) or set(raw) != MANIFEST_FIELDS:
        raise ValueError(f"invalid language manifest: {code}")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("unsupported language plugin schema")
    if raw["code"] != code or not isinstance(raw["status"], str):
        raise ValueError(f"language manifest identity or status mismatch: {code}")
    if raw["status"] not in {"complete", "draft"}:
        raise ValueError(f"language manifest identity or status mismatch: {code}")
    return LanguageManifest(
        code,
        language_text(raw["name"]),
        raw["status"],
        _instrument_ids(raw["instrument_ids"], source_ids),
    )


def parse_messages(raw: object, reference: object, code: str) -> dict[str, str]:
    """Require exact English message coverage and matching safe placeholders."""
    if not isinstance(raw, dict) or not isinstance(reference, dict) or set(raw) != set(reference):
        raise ValueError(f"language message coverage differs from English: {code}")
    messages = {}
    for source, translated in raw.items():
        source, translated = language_text(source), language_text(translated)
        if message_fields(source) != message_fields(translated):
            raise ValueError(f"language placeholders differ: {code}: {source[:80]}")
        messages[source] = translated
    return messages
