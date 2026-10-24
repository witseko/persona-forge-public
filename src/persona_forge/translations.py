"""Load display-only instrument translations from installed language plugins."""

from persona_forge.files import read_json_file
from persona_forge.languages import load_language
from persona_forge.model import Instrument
from persona_forge.translation_validation import apply_translation

# These instruments were translated before per-instrument administration languages
# were recorded. All others in an older saved session were administered in English.
LEGACY_UKRAINIAN_INSTRUMENTS = {
    "mini-ipip",
    "ipip-neo-120",
    "ipip-hexaco-hh",
    "ipip-via",
    "ncs-6",
}
TRANSLATION_NOTICE = (
    "Persona Forge project translation from English, revision 1. "
    "This translation has not been psychometrically validated in this language."
)


def validate_language(language: str) -> None:
    """Require a fully validated installed language pack."""
    load_language(language)


def translate_instrument(instrument: Instrument, language: str) -> Instrument:
    """Translate display text or reject an instrument absent from the selected pack."""
    pack = load_language(language)
    if language == "en":
        return instrument
    if instrument.id not in pack.instrument_ids:
        raise ValueError(f"instrument {instrument.id} is not supported by language {language}")
    raw = read_json_file(pack.instrument_dir / f"{instrument.id}.json")
    return apply_translation(instrument, raw, language)
