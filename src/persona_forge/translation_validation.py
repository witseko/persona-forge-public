"""Validate display-only instrument translations without depending on language discovery."""

from dataclasses import replace

from persona_forge.model import Instrument


def apply_translation(instrument: Instrument, raw: object, language: str) -> Instrument:
    """Validate complete translated text while retaining every scoring definition."""
    if not isinstance(raw, dict) or set(raw) != {
        "instrument_id",
        "language",
        "revision",
        "translated",
        "source_url",
        "citation",
        "licence",
        "permission_url",
        "instructions",
        "items",
        "response_sets",
    }:
        raise ValueError("translation fields do not match the required schema")
    if raw["instrument_id"] != instrument.id or raw["language"] != language or raw["revision"] != 1:
        raise ValueError("translation identity or revision does not match")
    for field in ("translated", "source_url", "citation", "licence", "permission_url"):
        _text(raw[field], field, 2000)
    instructions = _text(raw["instructions"], "instructions", 4000)
    items = raw["items"]
    if not isinstance(items, dict) or set(items) != {item.id for item in instrument.items}:
        raise ValueError("translation must cover every item exactly")
    translated_items = tuple(
        replace(item, text=_text(items[item.id], "item", 2000)) for item in instrument.items
    )
    response_sets = raw["response_sets"]
    if not isinstance(response_sets, dict) or set(response_sets) != {
        response_set.id for response_set in instrument.response_sets
    }:
        raise ValueError("translation must cover every response set exactly")
    translated_sets = []
    for response_set in instrument.response_sets:
        labels = response_sets[response_set.id]
        if not isinstance(labels, dict) or set(labels) != {
            str(option.value) for option in response_set.options
        }:
            raise ValueError("translation must preserve every response value")
        options = tuple(
            replace(option, label=_text(labels[str(option.value)], "label", 200))
            for option in response_set.options
        )
        translated_sets.append(replace(response_set, options=options))
    # Scores always use the original instrument. Overlays cannot carry keys or weights.
    return replace(
        instrument,
        instructions=instructions,
        items=translated_items,
        response_sets=tuple(translated_sets),
    )


def _text(value: object, field: str, limit: int) -> str:
    """Require bounded, non-empty text without terminal control characters."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"translation {field} must be non-empty plain text")
    return value
