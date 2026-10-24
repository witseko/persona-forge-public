"""The answers file: what the user chose, saved after every answer so setup can resume.

The same format serves the non-interactive path (`make setup ANSWERS=path`), so every
field is validated strictly when loaded: unknown keys, wrong types, unknown item or
option identifiers and over-long text are all refused.
"""

import json
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from persona_forge.files import read_json_file, write_private_text_if_changed
from persona_forge.translations import LEGACY_UKRAINIAN_INSTRUMENTS, validate_language

ANSWERS_VERSION = 1
NAME_LIMIT = 40
NOTE_LIMIT = 500
KNOWN_RESULT_LIMITS = {
    "sixteen_personalities": 10,
    "cliftonstrengths_top5": 200,
    "disc": 50,
    "enneagram": 50,
}
REVIEW_CHOICES = ("yes", "partly", "no")


class AnswersError(ValueError):
    """Raised when an answers file is malformed."""


@dataclass
class Answers:
    """Everything the user answered. Empty values mean "not asked yet"."""

    consent: bool = False
    name: str = ""
    role: str = ""
    seniority: str = ""
    depth: str = ""
    instruments: dict[str, dict[str, int]] = field(default_factory=dict)
    sjt: dict[str, str] = field(default_factory=dict)
    preferences: dict[str, str] = field(default_factory=dict)
    known_results: dict[str, str] = field(default_factory=dict)
    known_results_done: bool = False
    wellbeing_opt_in: bool | None = None
    wellbeing_tips: bool = False
    review: dict[str, str] = field(default_factory=dict)
    review_done: bool = False
    note: str = ""
    egos: dict[str, Any] | None = None
    questionnaire_language: str = "en"
    instrument_languages: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready dictionary including the format version."""
        return {"version": ANSWERS_VERSION, **asdict(self)}


def clean_text(value: str, limit: int) -> str:
    """Normalise user text: one line, no control characters, trimmed, within `limit`.

    Generated files embed this text, so control characters and line breaks are removed
    rather than trusted.
    """
    normalised = unicodedata.normalize("NFC", value)
    printable = "".join(
        " " if character in "\r\n\t" else character
        for character in normalised
        if character in "\r\n\t" or unicodedata.category(character)[0] != "C"
    )
    collapsed = " ".join(printable.split())
    if len(collapsed) > limit:
        raise AnswersError(f"text must be at most {limit} characters")
    return collapsed


def _require(condition: bool, message: str) -> None:
    """Raise AnswersError with `message` unless `condition` holds."""
    if not condition:
        raise AnswersError(message)


def _string_map(value: Any, what: str, limit: int = 2000) -> dict[str, str]:
    """Validate a mapping of short identifier strings to short strings."""
    _require(isinstance(value, dict) and len(value) <= limit, f"{what} must be an object")
    for key, entry in value.items():
        _require(
            isinstance(key, str)
            and len(key) <= 100
            and isinstance(entry, str)
            and len(entry) <= 100,
            f"{what} entries must be short strings",
        )
    return dict(value)


def parse_answers(raw: Any) -> Answers:
    """Validate the structure of a decoded answers document.

    Identifier checks against the shipped content happen in `check_known_identifiers`,
    which needs the loaded instruments and scenario banks.
    """
    _require(isinstance(raw, dict), "answers must be a JSON object")
    expected = set(Answers().to_dict())
    _require(set(raw) <= expected, f"unknown answer fields: {sorted(set(raw) - expected)}")
    _require(raw.get("version", ANSWERS_VERSION) == ANSWERS_VERSION, "unsupported answers version")
    answers = Answers()
    language = raw.get("questionnaire_language", "en")
    _require(isinstance(language, str), "questionnaire_language must be a string")
    validate_language(language)
    answers.questionnaire_language = language
    answers.consent = raw.get("consent", False)
    _require(type(answers.consent) is bool, "consent must be true or false")
    for key in ("name", "role", "seniority", "depth"):
        value = raw.get(key, "")
        _require(isinstance(value, str), f"{key} must be a string")
        setattr(answers, key, clean_text(value, NAME_LIMIT))
    instruments = raw.get("instruments", {})
    _require(
        isinstance(instruments, dict) and len(instruments) <= 20, "instruments must be an object"
    )
    for instrument_id, responses in instruments.items():
        _require(isinstance(instrument_id, str), "instrument ids must be strings")
        _require(
            isinstance(responses, dict) and len(responses) <= 1000, "responses must be an object"
        )
        for item_id, response in responses.items():
            _require(
                isinstance(item_id, str) and type(response) is int, "responses must be integers"
            )
        answers.instruments[instrument_id] = dict(responses)
    languages = _string_map(raw.get("instrument_languages", {}), "instrument_languages", 20)
    _require(
        set(languages) <= set(answers.instruments), "instrument languages need instrument entries"
    )
    for instrument_id, responses in answers.instruments.items():
        if instrument_id in languages:
            validate_language(languages[instrument_id])
        elif responses:
            # Preserve the actual language of pre-migration answers, including fallbacks.
            languages[instrument_id] = (
                "uk"
                if answers.questionnaire_language == "uk"
                and instrument_id in LEGACY_UKRAINIAN_INSTRUMENTS
                else "en"
            )
    answers.instrument_languages = languages
    answers.sjt = _string_map(raw.get("sjt", {}), "sjt")
    answers.preferences = _string_map(raw.get("preferences", {}), "preferences")
    known = raw.get("known_results", {})
    _require(
        isinstance(known, dict) and set(known) <= set(KNOWN_RESULT_LIMITS), "unknown known_results"
    )
    for key, value in known.items():
        _require(isinstance(value, str), "known results must be strings")
        answers.known_results[key] = clean_text(value, KNOWN_RESULT_LIMITS[key])
    for key in ("known_results_done", "wellbeing_tips", "review_done"):
        value = raw.get(key, False)
        _require(type(value) is bool, f"{key} must be true or false")
        setattr(answers, key, value)
    opt_in = raw.get("wellbeing_opt_in")
    _require(opt_in is None or type(opt_in) is bool, "wellbeing_opt_in must be true, false or null")
    answers.wellbeing_opt_in = opt_in
    answers.review = _string_map(raw.get("review", {}), "review")
    _require(all(value in REVIEW_CHOICES for value in answers.review.values()), "bad review value")
    note = raw.get("note", "")
    _require(isinstance(note, str), "note must be a string")
    answers.note = clean_text(note, NOTE_LIMIT)
    egos = raw.get("egos")
    _require(egos is None or isinstance(egos, dict), "egos must be an object or null")
    answers.egos = egos
    return answers


def load_answers(path: Path) -> Answers:
    """Read and structurally validate an answers file."""
    return parse_answers(read_json_file(path))


def save_answers(path: Path, answers: Answers) -> None:
    """Persist answers atomically with owner-only permissions."""
    write_private_text_if_changed(
        path, json.dumps(answers.to_dict(), indent=2, ensure_ascii=False) + "\n"
    )
