"""Read the reuse-permission catalogue that decides what the public edition may ship.

The private repository keeps every instrument. The public edition is a copy without
the instruments, or translations, whose redistribution or commercial-use permission
is still unclear. Statuses are recorded separately because item provenance,
permission and psychometric validation are different questions.
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from persona_forge.files import DATA_DIR, read_json_file
from persona_forge.instruments import INSTRUMENT_DIR

PERMISSIONS_FILE = DATA_DIR / "permissions.json"
ENTRY_FIELDS = {
    "item_provenance",
    "redistribution",
    "commercial_use",
    "translation",
    "evidence_url",
    "validation",
    "note",
}
PERMISSION_FIELDS = ("redistribution", "commercial_use", "translation")
PERMISSION_STATUSES = {"granted", "unclear"}
PROVENANCE_STATUSES = {"verified"}


@dataclass(frozen=True)
class InstrumentPermission:
    """Reuse evidence for one instrument, kept apart from its validation evidence."""

    instrument_id: str
    item_provenance: str
    redistribution: str
    commercial_use: str
    translation: str
    evidence_url: str
    validation: str
    note: str

    @property
    def public(self) -> bool:
        """True when the English items may ship in a public, commercially usable release."""
        return self.redistribution == "granted" and self.commercial_use == "granted"

    @property
    def translations_public(self) -> bool:
        """True when project translations of the items may also ship publicly."""
        return self.public and self.translation == "granted"


class PermissionCatalogueError(ValueError):
    """Raised when the permission catalogue is malformed."""


def instrument_installed(instrument_id: str, directory: Path = INSTRUMENT_DIR) -> bool:
    """True when the instrument's data file is present (the public edition omits some)."""
    return (directory / f"{instrument_id}.json").is_file()


@lru_cache(maxsize=1)
def load_permissions(path: Path = PERMISSIONS_FILE) -> dict[str, InstrumentPermission]:
    """Load and validate the catalogue, keyed by instrument identifier."""
    raw = read_json_file(path)
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "checked", "instruments"}:
        raise PermissionCatalogueError("permission catalogue fields do not match the schema")
    if raw["schema_version"] != 1:
        raise PermissionCatalogueError("unsupported permission catalogue schema")
    try:
        date.fromisoformat(raw["checked"])
    except (TypeError, ValueError) as error:
        raise PermissionCatalogueError("checked must be an ISO date") from error
    entries = raw["instruments"]
    if not isinstance(entries, dict) or not entries:
        raise PermissionCatalogueError("instruments must be a non-empty object")
    return {
        instrument_id: _parse_entry(instrument_id, entry)
        for instrument_id, entry in entries.items()
    }


def _parse_entry(instrument_id: str, raw: Any) -> InstrumentPermission:
    """Validate one catalogue entry."""
    if not isinstance(raw, dict) or set(raw) != ENTRY_FIELDS:
        raise PermissionCatalogueError(f"{instrument_id}: entry fields do not match the schema")
    if raw["item_provenance"] not in PROVENANCE_STATUSES:
        raise PermissionCatalogueError(f"{instrument_id}: unknown item_provenance status")
    for field in PERMISSION_FIELDS:
        if raw[field] not in PERMISSION_STATUSES:
            raise PermissionCatalogueError(f"{instrument_id}: {field} must be granted or unclear")
    for field in ("validation", "note"):
        if not isinstance(raw[field], str) or not raw[field].strip() or len(raw[field]) > 1000:
            raise PermissionCatalogueError(f"{instrument_id}: {field} must be short text")
    url = raw["evidence_url"]
    if not isinstance(url, str) or urlparse(url).scheme != "https" or len(url) > 2048:
        raise PermissionCatalogueError(f"{instrument_id}: evidence_url must be an HTTPS URL")
    return InstrumentPermission(instrument_id=instrument_id, **raw)
