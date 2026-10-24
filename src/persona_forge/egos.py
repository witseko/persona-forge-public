"""Alter egos: preset personas, the complement and mirror egos, and custom crafting.

An ego is a short list of instructions layered on top of the work profile. Generated
files are named `pf-<id>`, and `me` is reserved for the plain work profile.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from persona_forge.answers import AnswersError, clean_text
from persona_forge.files import DATA_DIR, read_json_file
from persona_forge.profile import Profile, Statement

PRESET_DIR = DATA_DIR / "egos" / "presets"
RESERVED_IDS = {"me"}
MAX_CUSTOM = 3
CUSTOM_NAME_LIMIT = 30

# Multiple-choice dimensions for crafting a custom ego. Each option adds one instruction.
CUSTOM_DIMENSIONS: dict[str, dict[str, Any]] = {
    "purpose": {
        "question": "What is this ego for?",
        "options": {
            "review": (
                "Reviewing work",
                "Your main job is to review my work critically and find problems.",
            ),
            "brainstorm": (
                "Brainstorming",
                "Your main job is to generate ideas and widen the option space.",
            ),
            "teach": (
                "Teaching",
                "Your main job is to help me understand, not just to produce answers.",
            ),
            "plan": ("Planning", "Your main job is to turn goals into clear, sequenced plans."),
            "unblock": (
                "Getting unstuck",
                "Your main job is to get me unstuck quickly with the next concrete step.",
            ),
        },
    },
    "bluntness": {
        "question": "How blunt should it be?",
        "options": {
            "gentle": ("Gentle", "Deliver criticism gently and constructively."),
            "balanced": ("Balanced", "Be honest and clear, without harshness."),
            "blunt": ("Blunt", "Be blunt; do not soften criticism."),
        },
    },
    "warmth": {
        "question": "How warm should it feel?",
        "options": {
            "cool": ("Cool and businesslike", "Keep a cool, businesslike manner."),
            "neutral": ("Neutral", "Keep a neutral, friendly-enough manner."),
            "warm": ("Warm", "Be warm and encouraging."),
        },
    },
    "detail": {
        "question": "How much detail?",
        "options": {
            "brief": ("Brief", "Keep responses brief."),
            "moderate": ("Moderate", "Give moderate detail: the key points and why."),
            "thorough": ("Thorough", "Be thorough and cover edge cases."),
        },
    },
    "risk": {
        "question": "What risk stance?",
        "options": {
            "cautious": ("Cautious", "Lean cautious: prefer safe, reversible choices."),
            "balanced": ("Balanced", "Weigh risk and speed evenly."),
            "bold": ("Bold", "Lean bold: favour progress and experiments over caution."),
        },
    },
    "humour": {
        "question": "Humour?",
        "options": {
            "none": ("None", "Do not use humour."),
            "light": ("A little", "A little light humour is welcome."),
        },
    },
}


@dataclass(frozen=True)
class Ego:
    """A persona: identifier, display name, one-line description and instructions."""

    id: str
    name: str
    description: str
    instructions: tuple[str, ...]


def slugify(name: str) -> str:
    """Make a safe identifier (letters, digits, single hyphens) from a display name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:CUSTOM_NAME_LIMIT].strip("-")


def load_presets(directory: Path = PRESET_DIR) -> dict[str, Ego]:
    """Load every preset ego, keyed by id."""
    presets = {}
    for path in sorted(directory.glob("*.json")):
        raw = read_json_file(path)
        if not isinstance(raw, dict) or set(raw) != {"id", "name", "description", "instructions"}:
            raise ValueError(f"{path.name} has unexpected fields")
        if raw["id"] != path.stem or slugify(raw["id"]) != raw["id"]:
            raise ValueError(f"{path.name} id must match the file name and be a slug")
        instructions = raw["instructions"]
        if not isinstance(instructions, list) or not all(
            isinstance(line, str) and line for line in instructions
        ):
            raise ValueError(f"{path.name} instructions must be a list of strings")
        presets[raw["id"]] = Ego(raw["id"], raw["name"], raw["description"], tuple(instructions))
    return presets


def complement_ego(growth: list[tuple[Statement, str]]) -> Ego | None:
    """An ego that gently counterbalances accepted growth points; None when there are none."""
    if not growth:
        return None
    instructions = [
        "Act as my complement: gently counterbalance the tendencies below, without lecturing.",
        *[statement.agent_tip for statement, _ in growth],
        "Raise each point only when it is relevant to the task at hand.",
    ]
    return Ego(
        "complement", "Complement", "Counterbalances your growth points.", tuple(instructions)
    )


def mirror_ego(profile: Profile, communication: list[tuple[Statement, str]]) -> Ego:
    """An ego that drafts text in the user's own voice, from their accepted preferences."""
    instructions = [
        "Act as my mirror: when drafting messages, pull request descriptions or docs, "
        "write as I would.",
    ]
    for key in ("tone", "length", "format", "language"):
        if key in profile.preference_instructions:
            instructions.append(profile.preference_instructions[key])
    for _, text in communication:
        instructions.append(f"About me: {text}")
    instructions.append("Avoid phrases I would not use; keep my wording plain and specific.")
    return Ego("mirror", "Mirror", "Writes in your voice.", tuple(instructions))


def custom_ego(raw: dict[str, Any]) -> Ego:
    """Build a custom ego from validated multiple-choice answers."""
    name = clean_text(str(raw.get("name", "")), CUSTOM_NAME_LIMIT)
    ego_id = slugify(name)
    if not ego_id or ego_id in RESERVED_IDS:
        raise AnswersError("custom ego names need letters or digits and cannot be 'me'")
    if set(raw) != {"name", *CUSTOM_DIMENSIONS}:
        raise AnswersError("a custom ego needs a name and one answer per crafting question")
    instructions = [f"Act as {name}, a custom persona."]
    for dimension, spec in CUSTOM_DIMENSIONS.items():
        choice = raw[dimension]
        if choice not in spec["options"]:
            raise AnswersError(f"unknown {dimension} option {choice!r}")
        instructions.append(spec["options"][choice][1])
    purpose_label = CUSTOM_DIMENSIONS["purpose"]["options"][raw["purpose"]][0].lower()
    return Ego(ego_id, name, f"Custom persona for {purpose_label}.", tuple(instructions))


def validate_ego_choices(raw: Any) -> dict[str, Any]:
    """Check the shape of the egos section of an answers file."""
    if not isinstance(raw, dict) or set(raw) - {
        "presets",
        "complement",
        "mirror",
        "custom",
        "done",
        "custom_draft",
    }:
        raise AnswersError("unknown egos field")
    presets = raw.get("presets", [])
    known = load_presets()
    if not isinstance(presets, list) or not all(isinstance(p, str) and p in known for p in presets):
        raise AnswersError("egos.presets must list known preset ids")
    for key in ("complement", "mirror", "done"):
        if type(raw.get(key, False)) is not bool:
            raise AnswersError(f"egos.{key} must be true or false")
    custom = raw.get("custom", [])
    if not isinstance(custom, list) or len(custom) > MAX_CUSTOM:
        raise AnswersError(f"egos.custom must be a list of at most {MAX_CUSTOM} entries")
    for entry in custom:
        if not isinstance(entry, dict):
            raise AnswersError("each custom ego must be an object")
        custom_ego(entry)
    if "custom_draft" in raw:
        draft = raw["custom_draft"]
        if (
            raw.get("done")
            or len(custom) >= MAX_CUSTOM
            or not isinstance(draft, dict)
            or "name" not in draft
            or set(draft) - {"name", *CUSTOM_DIMENSIONS}
        ):
            raise AnswersError("invalid unfinished custom ego")
        name = draft["name"]
        if not isinstance(name, str) or clean_text(name, CUSTOM_NAME_LIMIT) != name:
            raise AnswersError("custom ego draft name must be clean text")
        if not slugify(name) or slugify(name) in RESERVED_IDS:
            raise AnswersError("custom ego names need letters or digits and cannot be 'me'")
        for dimension, choice in draft.items():
            if dimension != "name" and (
                not isinstance(choice, str) or choice not in CUSTOM_DIMENSIONS[dimension]["options"]
            ):
                raise AnswersError("unknown custom ego draft option")
    return raw


def build_egos(
    choices: dict[str, Any] | None,
    profile: Profile,
    accepted: dict[str, list[tuple[Statement, str]]],
) -> list[Ego]:
    """Return the chosen egos in a stable order, with unique ids."""
    if not choices:
        return []
    validate_ego_choices(choices)
    presets = load_presets()
    egos = [presets[preset_id] for preset_id in choices.get("presets", [])]
    if choices.get("complement"):
        complement = complement_ego(accepted["growth"])
        if complement:
            egos.append(complement)
    if choices.get("mirror"):
        egos.append(mirror_ego(profile, accepted["communication"]))
    egos.extend(custom_ego(entry) for entry in choices.get("custom", []))
    unique: dict[str, Ego] = {}
    for ego in egos:
        if ego.id in unique:
            raise AnswersError(f"two egos share the id {ego.id}")
        unique[ego.id] = ego
    return list(unique.values())
