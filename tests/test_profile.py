"""Profile building, statement selection, review and the derived label."""

import pytest
from helpers import make_answers, private_edition_only

from persona_forge.answers import parse_answers
from persona_forge.profile import (
    SECTION_LIMITS,
    Trait,
    accepted_statements,
    build_profile,
    derive_label,
    select_statements,
)


def _profile(**kwargs: object):  # type: ignore[no-untyped-def]
    """Build a profile from a synthetic answers document."""
    return build_profile(parse_answers(make_answers(**kwargs)))  # type: ignore[arg-type]


def _trait(key: str, position: float) -> Trait:
    """A trait with a band matching its position."""
    band = "low" if position < 0.4 else "high" if position > 0.6 else "mid"
    return Trait(key, key, position, band)


@pytest.mark.parametrize("depth", ["quick", "standard", "deep"])
def test_every_depth_builds_a_profile(depth: str) -> None:
    """All three depths produce Big Five traits and stay within section limits."""
    profile = _profile(depth=depth)
    assert "big5:extraversion" in profile.traits
    assert profile.derived_label is not None
    for section, limit in SECTION_LIMITS.items():
        assert len([s for s in profile.statements if s.section == section]) <= limit + (
            5 if section == "strengths" else 0
        )


@private_edition_only
def test_deep_profile_has_strengths_and_interests() -> None:
    """Deep adds signature strengths (high band only) and a ranked RIASEC list."""
    profile = _profile(depth="deep")
    assert [interest["id"] for interest in profile.interests]
    assert len(profile.interests) == 6
    for strength in profile.signature_strengths:
        assert profile.traits[f"via:{strength['id']}"].band == "high"


def test_rules_fire_on_matching_bands_and_roles() -> None:
    """A high extraversion fires its rule; role-only rules stay with their roles."""
    traits = {
        "big5:extraversion": _trait("big5:extraversion", 0.9),
        "sjt:directness": _trait("sjt:directness", 0.1),
    }
    engineer = {s.id for s in select_statements(traits, "software-engineer")}
    manager = {s.id for s in select_statements(traits, "engineering-manager")}
    assert "big5-e-high" in engineer
    assert "em-directness-low" not in engineer
    assert "em-directness-low" in manager


def test_strongest_tendencies_come_first() -> None:
    """Statements are ordered by distance from the midpoint."""
    traits = {
        "big5:extraversion": _trait("big5:extraversion", 0.65),
        "big5:agreeableness": _trait("big5:agreeableness", 0.95),
    }
    ids = [s.id for s in select_statements(traits, "software-engineer")]
    assert ids.index("big5-a-high") < ids.index("big5-e-high")


def test_review_keeps_softens_or_drops() -> None:
    """yes keeps the text, partly uses the softened text, no removes the statement."""
    profile = _profile()
    first, second, third = profile.statements[:3]
    review = {first.id: "yes", second.id: "partly", third.id: "no"}
    accepted = dict((s.id, text) for s, text in accepted_statements(profile, review))
    assert accepted[first.id] == first.text
    assert accepted[second.id] == second.softened
    assert third.id not in accepted


@pytest.mark.parametrize(
    ("positions", "expected"),
    [
        ((0.9, 0.9, 0.9, 0.9), "ENFJ"),
        ((0.1, 0.1, 0.1, 0.1), "ISTP"),
        ((0.5, 0.9, 0.1, 0.9), "XNTJ"),
    ],
)
def test_derived_label(positions: tuple[float, ...], expected: str) -> None:
    """Letters follow E, O, A and C; an exact midpoint shows X."""
    keys = ["big5:extraversion", "big5:openness", "big5:agreeableness", "big5:conscientiousness"]
    traits = {key: _trait(key, position) for key, position in zip(keys, positions, strict=True)}
    assert derive_label(traits) == expected


def test_wellbeing_stays_out_of_traits_and_statements() -> None:
    """The burnout scale is summarised for the report only."""
    profile = _profile(wellbeing=True)
    assert profile.wellbeing is not None
    assert not any("cbi" in key for key in profile.traits)
    assert all("cbi" not in s.source for s in profile.statements)
    assert all(score.instrument_id != "cbi-work" for score in profile.instrument_scores)
