"""Shared synthetic fixtures. They contain no real questionnaire content."""

import copy
from typing import Any

import pytest

SYNTHETIC_INSTRUMENT: dict[str, Any] = {
    "id": "synthetic-demo",
    "name": "Synthetic demo only",
    "source_url": "https://example.org/synthetic",
    "retrieved": "2026-10-23",
    "citation": "Synthetic fixture created for software tests",
    "licence": "Test fixture, not an instrument",
    "attribution": "",
    "instructions": "Synthetic instructions.",
    "notes": "",
    "aggregation": "mean",
    "response_sets": [
        {
            "id": "five",
            "options": [{"value": value, "label": f"Option {value}"} for value in range(1, 6)],
        }
    ],
    "items": [
        {"id": "q1", "text": "Synthetic prompt one", "scale": "s1", "reverse": False},
        {"id": "q2", "text": "Synthetic prompt two", "scale": "s1", "reverse": True},
        {"id": "q3", "text": "Synthetic prompt three", "scale": "s2", "reverse": False},
        {"id": "q4", "text": "Synthetic prompt four", "scale": "s2", "reverse": False},
    ],
    "scales": [
        {"id": "s1", "name": "Demo scale one", "item_ids": ["q1", "q2"]},
        {"id": "s2", "name": "Demo scale two", "item_ids": ["q3", "q4"]},
    ],
    "domains": [{"id": "d1", "name": "Demo domain", "scale_ids": ["s1", "s2"]}],
}


@pytest.fixture
def synthetic_instrument() -> dict[str, Any]:
    """Return a fresh, mutable copy of the synthetic instrument definition."""
    return copy.deepcopy(SYNTHETIC_INSTRUMENT)
