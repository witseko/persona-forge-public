"""Permission catalogue and the limited public edition built from it."""

import json
from pathlib import Path

import pytest
from helpers import private_edition_only

from persona_forge.files import PROJECT_ROOT
from persona_forge.instruments import INSTRUMENT_DIR
from persona_forge.permissions import PermissionCatalogueError, load_permissions
from persona_forge.public_export import PublicExportError, export_public_edition, main

# Release decision recorded on 2026-10-24: these may ship publicly. Everything else
# stays in the private repository until written clarification arrives.
PUBLIC_INSTRUMENTS = {"mini-ipip", "ipip-neo-120", "ipip-hexaco-hh", "ipip-via", "cbi-work"}
PUBLIC_TRANSLATIONS = {"mini-ipip", "ipip-neo-120", "ipip-hexaco-hh", "ipip-via"}


def test_every_installed_instrument_has_a_permission_entry() -> None:
    """A new instrument cannot be added without recording its reuse evidence."""
    installed = {path.stem for path in INSTRUMENT_DIR.glob("*.json")}
    assert installed <= set(load_permissions())


def test_public_release_decision_matches_the_recorded_evidence() -> None:
    """Only fully granted instruments and translations are public."""
    permissions = load_permissions()
    assert {key for key, entry in permissions.items() if entry.public} == PUBLIC_INSTRUMENTS
    assert {
        key for key, entry in permissions.items() if entry.translations_public
    } == PUBLIC_TRANSLATIONS


@pytest.mark.parametrize(
    "mutation",
    ["unknown_status", "missing_field", "http_evidence", "bad_date", "empty_note"],
)
def test_malformed_catalogue_is_rejected(tmp_path: Path, mutation: str) -> None:
    """Typos in the catalogue fail loudly instead of silently publishing content."""
    raw = json.loads((PROJECT_ROOT / "data" / "permissions.json").read_text())
    entry = raw["instruments"]["gse"]
    if mutation == "unknown_status":
        entry["redistribution"] = "probably"
    elif mutation == "missing_field":
        del entry["validation"]
    elif mutation == "http_evidence":
        entry["evidence_url"] = "http://example.com"
    elif mutation == "bad_date":
        raw["checked"] = "yesterday"
    else:
        entry["note"] = " "
    path = tmp_path / "permissions.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(PermissionCatalogueError):
        load_permissions.__wrapped__(path)


@private_edition_only
def test_public_export_leaves_out_withheld_content(tmp_path: Path) -> None:
    """The copy omits withheld files, updates manifests and sample answers, and keeps the rest."""
    destination = tmp_path / "public"
    withheld = export_public_edition(destination)

    assert "data/instruments/gse.json" in withheld
    assert "data/languages/uk/instruments/cbi-work.json" in withheld
    for relative in withheld:
        assert not (destination / relative).exists()
    assert (destination / "data" / "instruments" / "cbi-work.json").is_file()
    assert (destination / "README.md").is_file()
    assert "PLAN.md" in withheld and not (destination / "PLAN.md").exists()
    assert not (destination / ".git").exists()
    assert not (destination / "out").exists()

    uk = json.loads((destination / "data/languages/uk/manifest.json").read_text())
    assert set(uk["instrument_ids"]) == PUBLIC_TRANSLATIONS
    english = json.loads((destination / "data/languages/en/manifest.json").read_text())
    assert set(english["instrument_ids"]) == PUBLIC_INSTRUMENTS
    sample = json.loads((destination / "tests/fixtures/answers_standard.json").read_text())
    assert set(sample["instruments"]) <= PUBLIC_INSTRUMENTS
    # The private repository itself is never modified.
    assert (PROJECT_ROOT / "data" / "instruments" / "gse.json").is_file()


@private_edition_only
def test_public_export_refuses_leaks_and_unsafe_destinations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leftover withheld text aborts the export and removes the partial copy."""
    with pytest.raises(PublicExportError, match="outside this repository"):
        export_public_edition(PROJECT_ROOT / "out" / "public-test")
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(PublicExportError, match="already exists"):
        export_public_edition(existing)

    monkeypatch.setattr(
        "persona_forge.public_export.withheld_texts", lambda root, withheld: {"persona-forge"}
    )
    destination = tmp_path / "leaky"
    assert main([str(destination)]) == 1
    assert not destination.exists()
