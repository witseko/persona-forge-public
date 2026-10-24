"""Load and validate project-authored content: scenario banks, dimensions and preferences."""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from persona_forge.files import DATA_DIR, read_json_file
from persona_forge.model import SJTOption, SJTScenario

SJT_DIR = DATA_DIR / "sjt"
PREFERENCES_PATH = DATA_DIR / "preferences.json"


class ContentError(ValueError):
    """Raised when an authored content file is malformed."""


@dataclass(frozen=True)
class Dimension:
    """A bipolar scenario dimension scored from 0 (low pole) to 1 (high pole)."""

    id: str
    name: str
    low_label: str
    high_label: str


@dataclass(frozen=True)
class PreferenceOption:
    """One explicit collaboration choice and the instruction it adds to the profile."""

    id: str
    label: str
    instruction: str


@dataclass(frozen=True)
class Preference:
    """A multiple-choice collaboration preference."""

    id: str
    question: str
    options: tuple[PreferenceOption, ...]

    def option(self, option_id: str) -> PreferenceOption:
        """Return an option by identifier."""
        for option in self.options:
            if option.id == option_id:
                return option
        raise KeyError(option_id)


def _text(value: Any, field: str, limit: int = 1000) -> str:
    """Return a non-empty string within `limit` characters."""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ContentError(f"{field} must be a non-empty string of at most {limit} characters")
    return value


def _object(value: Any, fields: set[str], what: str) -> dict[str, Any]:
    """Return `value` if it is an object with exactly `fields`."""
    if not isinstance(value, dict) or set(value) != fields:
        raise ContentError(f"{what} must have exactly these fields: {sorted(fields)}")
    return value


def _list(value: Any, what: str, limit: int = 200) -> list[Any]:
    """Return `value` if it is a non-empty list within `limit` entries."""
    if not isinstance(value, list) or not value or len(value) > limit:
        raise ContentError(f"{what} must be a non-empty list")
    return value


def load_dimensions(directory: Path = SJT_DIR) -> tuple[Dimension, ...]:
    """Load the scenario dimension definitions."""
    raw = _object(read_json_file(directory / "dimensions.json"), {"note", "dimensions"}, "file")
    dimensions = []
    for entry in _list(raw["dimensions"], "dimensions"):
        entry = _object(entry, {"id", "name", "low_label", "high_label"}, "dimension")
        dimensions.append(
            Dimension(
                _text(entry["id"], "dimension id", 50),
                _text(entry["name"], "dimension name"),
                _text(entry["low_label"], "low_label"),
                _text(entry["high_label"], "high_label"),
            )
        )
    if len({dimension.id for dimension in dimensions}) != len(dimensions):
        raise ContentError("dimension identifiers must be unique")
    return tuple(dimensions)


def load_sjt_bank(bank_id: str, directory: Path = SJT_DIR) -> tuple[SJTScenario, ...]:
    """Load one scenario bank (`common` or a role id) and validate its weights."""
    if not bank_id.replace("-", "").isalnum():
        raise ContentError("bank identifiers use letters, digits and '-'")
    known_dimensions = {dimension.id for dimension in load_dimensions(directory)}
    raw = _object(
        read_json_file(directory / f"{bank_id}.json"),
        {"id", "title", "authored", "scenarios"},
        "scenario bank",
    )
    if raw["id"] != bank_id:
        raise ContentError("bank id does not match its file name")
    scenarios = tuple(
        _parse_scenario(entry, known_dimensions) for entry in _list(raw["scenarios"], "scenarios")
    )
    if len({scenario.id for scenario in scenarios}) != len(scenarios):
        raise ContentError("scenario identifiers must be unique")
    return scenarios


def _parse_scenario(raw: Any, known_dimensions: set[str]) -> SJTScenario:
    """Validate one scenario: 2 to 6 options that all weight the same known dimensions."""
    raw = _object(raw, {"id", "title", "prompt", "options"}, "scenario")
    options = []
    for entry in _list(raw["options"], "options", limit=6):
        entry = _object(entry, {"id", "text", "weights"}, "option")
        weights = entry["weights"]
        if not isinstance(weights, dict) or not weights:
            raise ContentError("option weights must be a non-empty object")
        for dimension, weight in weights.items():
            if dimension not in known_dimensions:
                raise ContentError(f"unknown dimension {dimension}")
            if (
                isinstance(weight, bool)
                or not isinstance(weight, int | float)
                or not isfinite(weight)
                or not 0 <= weight <= 1
            ):
                raise ContentError("weights must be numbers from 0 to 1")
        options.append(
            SJTOption(
                _text(entry["id"], "option id", 20),
                _text(entry["text"], "option text"),
                dict(weights),
            )
        )
    if len(options) < 2 or len({option.id for option in options}) != len(options):
        raise ContentError("a scenario needs at least two uniquely named options")
    if len({frozenset(option.weights) for option in options}) != 1:
        # Otherwise a dimension mean would be biased by which option happens to mention it.
        raise ContentError(f"options of {raw['id']} must weight the same dimensions")
    return SJTScenario(
        _text(raw["id"], "scenario id", 100),
        _text(raw["title"], "scenario title"),
        _text(raw["prompt"], "scenario prompt", 2000),
        tuple(options),
    )


def load_preferences(path: Path = PREFERENCES_PATH) -> tuple[Preference, ...]:
    """Load the collaboration preference questions."""
    raw = _object(read_json_file(path), {"authored", "preferences"}, "preferences file")
    preferences = []
    for entry in _list(raw["preferences"], "preferences"):
        entry = _object(entry, {"id", "question", "options"}, "preference")
        options = tuple(
            PreferenceOption(
                _text(option["id"], "option id", 50),
                _text(option["label"], "option label"),
                _text(option["instruction"], "option instruction"),
            )
            for option in (
                _object(option, {"id", "label", "instruction"}, "preference option")
                for option in _list(entry["options"], "options", limit=8)
            )
        )
        if len({option.id for option in options}) != len(options):
            raise ContentError("preference option identifiers must be unique")
        preferences.append(
            Preference(
                _text(entry["id"], "preference id", 50),
                _text(entry["question"], "question"),
                options,
            )
        )
    if len({preference.id for preference in preferences}) != len(preferences):
        raise ContentError("preference identifiers must be unique")
    return tuple(preferences)
