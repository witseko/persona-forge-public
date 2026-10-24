"""Paths, identifiers and placeholder rules shared by language plugin modules."""

import re

from persona_forge.files import DATA_DIR

LANGUAGE_DIR = DATA_DIR / "languages"
CODE_PATTERN = re.compile(r"[a-z]{2,3}(?:-[A-Z]{2})?")
INSTRUMENT_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TRANSLATED_FIELDS = frozenset({"title", "description", "body", "depth", "label", "name", "error"})
MANIFEST_FIELDS = frozenset({"schema_version", "code", "name", "status", "instrument_ids"})
CORE_INSTRUMENT_IDS = frozenset({"mini-ipip", "ipip-neo-120"})
NUMBER_FIELDS = frozenset(
    {"count", "done", "total", "number", "minutes", "limit", "stage", "percent"}
)
