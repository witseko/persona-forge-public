"""Setup flow configuration: roles, seniority, depth levels and what each depth asks."""

from dataclasses import dataclass

from persona_forge.content import load_sjt_bank
from persona_forge.instruments import load_instrument_by_id
from persona_forge.languages import load_language
from persona_forge.model import Instrument, SJTScenario
from persona_forge.permissions import instrument_installed

ROLES = {
    "software-engineer": "Software engineer",
    "engineering-manager": "Engineering manager",
    "product-manager": "Product manager",
    "product-owner": "Product owner",
    "cto": "CTO or head of engineering",
}

SENIORITY = {
    "junior": "Junior",
    "mid": "Mid-level",
    "senior": "Senior",
    "staff": "Staff or principal",
    "lead": "Lead or manager",
    "executive": "Director or executive",
}

# Module names shown in the questionnaire for each instrument.
MODULE_TITLES = {
    "mini-ipip": "Personality",
    "ipip-neo-120": "Personality",
    "ipip-hexaco-hh": "Honesty and humility",
    "gse": "Drive: self-efficacy",
    "ncs-6": "Thinking style",
    "ipip-via": "Character strengths",
    "onet-ip-sf": "Career interests",
    "cbi-work": "Wellbeing: work energy",
}

WELLBEING_INSTRUMENTS = ("cbi-work",)

# Rough seconds per answer, used only for the time estimate shown to the user.
SECONDS_PER_ITEM = 6
SECONDS_PER_SCENARIO = 30
SECONDS_PER_PREFERENCE = 10
REVIEW_SECONDS = 180


@dataclass(frozen=True)
class Depth:
    """What one depth level asks: instruments in order and scenarios per bank."""

    id: str
    title: str
    instrument_ids: tuple[str, ...]
    common_scenarios: int
    role_scenarios: int


DEPTHS = {
    "quick": Depth("quick", "Quick", ("mini-ipip",), 4, 4),
    "standard": Depth("standard", "Standard", ("ipip-neo-120", "gse", "ncs-6"), 8, 8),
    "deep": Depth(
        "deep",
        "Deep",
        ("ipip-neo-120", "ipip-hexaco-hh", "gse", "ncs-6", "ipip-via", "onet-ip-sf"),
        12,
        12,
    ),
}


def depth_instruments(depth_id: str, language: str = "en") -> tuple[Instrument, ...]:
    """Load the installed instruments a depth level asks, in questionnaire order.

    The public edition omits instruments whose reuse permission is unclear, so a
    missing data file means "not offered here", not an error.
    """
    supported = load_language(language).instrument_ids
    return tuple(
        load_instrument_by_id(instrument_id)
        for instrument_id in DEPTHS[depth_id].instrument_ids
        if instrument_id in supported and instrument_installed(instrument_id)
    )


def depth_scenarios(depth_id: str, role: str) -> tuple[SJTScenario, ...]:
    """Return the scenarios for a depth and role: the first N shared, then the first N for the role.

    Taking a fixed prefix keeps the selection stable, so a resumed session asks the same
    scenarios it started with.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role {role}")
    depth = DEPTHS[depth_id]
    common = load_sjt_bank("common")[: depth.common_scenarios]
    role_bank = load_sjt_bank(role)[: depth.role_scenarios]
    return common + role_bank


def wellbeing_instruments(language: str = "en") -> tuple[Instrument, ...]:
    """Return only the optional wellbeing instruments covered by a language pack."""
    supported = load_language(language).instrument_ids
    return tuple(
        load_instrument_by_id(item)
        for item in WELLBEING_INSTRUMENTS
        if item in supported and instrument_installed(item)
    )


def estimated_minutes(depth_id: str, preference_count: int, language: str = "en") -> int:
    """Estimate the time a depth takes, from rough per-answer timings."""
    depth = DEPTHS[depth_id]
    items = sum(len(instrument.items) for instrument in depth_instruments(depth_id, language))
    seconds = (
        items * SECONDS_PER_ITEM
        + (depth.common_scenarios + depth.role_scenarios) * SECONDS_PER_SCENARIO
        + preference_count * SECONDS_PER_PREFERENCE
        + REVIEW_SECONDS
    )
    return round(seconds / 60)
