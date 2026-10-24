"""Load the table-driven interpretation rules in data/insights."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from persona_forge.files import DATA_DIR, read_json_file

INSIGHTS_DIR = DATA_DIR / "insights"
SECTIONS = ("communication", "decisions", "strengths", "growth", "collaboration")
BANDS = ("low", "mid", "high")


class InsightError(ValueError):
    """Raised when an insight file is malformed."""


@dataclass(frozen=True)
class Rule:
    """When `trait` falls in `band`, offer a statement for the user to review."""

    id: str
    trait: str
    band: str
    section: str
    statement: str
    softened: str
    agent_tip: str
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrengthText:
    """Label and agent tip for one character strength or interest area."""

    label: str
    text: str


@dataclass(frozen=True)
class WellbeingText:
    """Non-diagnostic wording for the opt-in wellbeing module."""

    report_note_high: str
    report_note_other: str
    practical_tips: tuple[str, ...]


def _text(value: Any, field: str) -> str:
    """Return a non-empty string of at most 600 characters."""
    if not isinstance(value, str) or not value.strip() or len(value) > 600:
        raise InsightError(f"{field} must be a non-empty string of at most 600 characters")
    return value


def load_rules(directory: Path = INSIGHTS_DIR) -> tuple[Rule, ...]:
    """Load and validate the trait rules."""
    raw = read_json_file(directory / "traits.json")
    if (
        not isinstance(raw, dict)
        or set(raw) != {"authored", "rules"}
        or not isinstance(raw["rules"], list)
    ):
        raise InsightError("traits.json must have authored and rules fields")
    required = {"id", "trait", "band", "section", "statement", "softened", "agent_tip"}
    rules = []
    for entry in raw["rules"]:
        if not isinstance(entry, dict) or not required <= set(entry) <= required | {"roles"}:
            raise InsightError("each rule needs id, trait, band, section and three texts")
        if entry["band"] not in BANDS or entry["section"] not in SECTIONS:
            raise InsightError(f"rule {entry.get('id')} has an unknown band or section")
        roles = entry.get("roles", [])
        if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
            raise InsightError("rule roles must be a list of strings")
        rules.append(
            Rule(
                _text(entry["id"], "id"),
                _text(entry["trait"], "trait"),
                entry["band"],
                entry["section"],
                _text(entry["statement"], "statement"),
                _text(entry["softened"], "softened"),
                _text(entry["agent_tip"], "agent_tip"),
                tuple(roles),
            )
        )
    if len({rule.id for rule in rules}) != len(rules):
        raise InsightError("rule identifiers must be unique")
    return tuple(rules)


def load_strength_texts(
    directory: Path = INSIGHTS_DIR,
) -> tuple[dict[str, StrengthText], dict[str, StrengthText]]:
    """Return (character strength texts, RIASEC interest texts) keyed by scale id."""
    raw = read_json_file(directory / "strengths.json")
    if not isinstance(raw, dict) or set(raw) != {"authored", "via", "riasec"}:
        raise InsightError("strengths.json must have authored, via and riasec fields")
    via = {
        key: StrengthText(_text(value["label"], "label"), _text(value["tip"], "tip"))
        for key, value in raw["via"].items()
    }
    riasec = {
        key: StrengthText(
            _text(value["label"], "label"), _text(value["description"], "description")
        )
        for key, value in raw["riasec"].items()
    }
    return via, riasec


def load_wellbeing_text(directory: Path = INSIGHTS_DIR) -> WellbeingText:
    """Return the wellbeing wording."""
    raw = read_json_file(directory / "wellbeing.json")
    expected = {"authored", "report_note_high", "report_note_other", "practical_tips"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise InsightError("wellbeing.json has unexpected fields")
    return WellbeingText(
        _text(raw["report_note_high"], "report_note_high"),
        _text(raw["report_note_other"], "report_note_other"),
        tuple(_text(tip, "tip") for tip in raw["practical_tips"]),
    )
