"""Verify the small immutable data models."""

from persona_forge.model import ResponseOption, ResponseSet


def test_response_set_reports_its_range() -> None:
    """Range helpers work regardless of option order (some sources list high to low)."""
    response_set = ResponseSet(
        "burnout", (ResponseOption(100, "Always"), ResponseOption(0, "Never"))
    )
    assert (response_set.minimum, response_set.maximum) == (0, 100)
    assert response_set.values == frozenset({0, 100})
