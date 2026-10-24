"""Build complete, synthetic answer sets for tests. No real person's answers are used."""

from typing import Any

import pytest

from persona_forge.content import load_preferences
from persona_forge.flow import depth_instruments, depth_scenarios
from persona_forge.instruments import load_instrument_by_id
from persona_forge.permissions import instrument_installed, load_permissions

# The public edition omits instruments with unclear reuse permission. Tests that check
# those instruments, or outputs that depend on them, run only in the private edition.
PRIVATE_EDITION = all(instrument_installed(item) for item in load_permissions())
private_edition_only = pytest.mark.skipif(
    not PRIVATE_EDITION, reason="checks instruments the public edition leaves out"
)

DEFAULT_EGOS: dict[str, Any] = {
    "presets": ["mentor", "strict-reviewer"],
    "complement": True,
    "mirror": True,
    "custom": [
        {
            "name": "Rubber Duck",
            "purpose": "unblock",
            "bluntness": "gentle",
            "warmth": "warm",
            "detail": "brief",
            "risk": "balanced",
            "humour": "light",
        }
    ],
    "done": True,
}


def make_answers(
    depth: str = "standard",
    role: str = "software-engineer",
    shift: int = 0,
    wellbeing: bool = False,
) -> dict[str, Any]:
    """Return a complete answers document with a fixed, varied response pattern."""
    answers: dict[str, Any] = {
        "version": 1,
        "consent": True,
        "name": "Test Person",
        "role": role,
        "seniority": "senior",
        "depth": depth,
        "instruments": {},
        "sjt": {},
        "preferences": {},
        "known_results": {"sixteen_personalities": "INTJ-A"},
        "known_results_done": True,
        "wellbeing_opt_in": wellbeing,
        "wellbeing_tips": False,
        "review": {},
        "review_done": True,
        "note": "I use British spelling.",
        "egos": DEFAULT_EGOS,
    }
    instruments = list(depth_instruments(depth))
    if wellbeing:
        instruments.append(load_instrument_by_id("cbi-work"))
    for instrument in instruments:
        responses = {}
        for index, item in enumerate(instrument.items):
            values = sorted(instrument.response_set(item.response_set).values)
            responses[item.id] = values[(index * 7 + shift + len(item.id)) % len(values)]
        answers["instruments"][instrument.id] = responses
    for index, scenario in enumerate(depth_scenarios(depth, role)):
        answers["sjt"][scenario.id] = scenario.options[(index + shift) % len(scenario.options)].id
    for index, preference in enumerate(load_preferences()):
        answers["preferences"][preference.id] = preference.options[
            index % len(preference.options)
        ].id
    return answers
