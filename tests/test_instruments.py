"""Validate loading and rejection of synthetic instrument fixtures."""

import json
from pathlib import Path
from typing import Any

import pytest

from persona_forge.instruments import (
    InstrumentValidationError,
    load_instrument,
    load_instrument_by_id,
    parse_instrument,
)


def test_parse_instrument_validates_and_builds_model(synthetic_instrument: dict[str, Any]) -> None:
    """Valid schema data is converted to immutable typed records."""
    instrument = parse_instrument(synthetic_instrument)
    assert instrument.id == "synthetic-demo"
    assert instrument.items[1].reverse is True
    assert instrument.items[0].response_set == "five"  # defaults to the first set
    assert instrument.scales[0].item_ids == ("q1", "q2")
    assert instrument.domains[0].scale_ids == ("s1", "s2")
    assert instrument.response_set("five").minimum == 1


def test_load_instrument_reads_json_file(
    tmp_path: Path, synthetic_instrument: dict[str, Any]
) -> None:
    """The loader decodes a local JSON fixture."""
    path = tmp_path / "synthetic-demo.json"
    path.write_text(json.dumps(synthetic_instrument), encoding="utf-8")
    assert load_instrument(path).id == "synthetic-demo"
    assert load_instrument_by_id("synthetic-demo", tmp_path).id == "synthetic-demo"


@pytest.mark.parametrize("instrument_id", ["../etc", "a/b", "x.json", ""])
def test_load_by_id_rejects_path_like_identifiers(instrument_id: str, tmp_path: Path) -> None:
    """Identifiers cannot traverse directories or name arbitrary files."""
    with pytest.raises(InstrumentValidationError):
        load_instrument_by_id(instrument_id, tmp_path)


def _mutate(instrument: dict[str, Any], mutation: str) -> None:
    """Apply one named defect to a valid instrument definition."""
    if mutation == "missing_member":
        instrument["scales"][0]["item_ids"] = ["q1"]
    elif mutation == "http_url":
        instrument["source_url"] = "http://example.org/synthetic"
    elif mutation == "bad_reverse":
        instrument["items"][0]["reverse"] = 1
    elif mutation == "extra_field":
        instrument["unrecognized"] = "value"
    elif mutation == "unknown_response_set":
        instrument["items"][0]["response_set"] = "missing"
    elif mutation == "duplicate_values":
        instrument["response_sets"][0]["options"][1]["value"] = 1
    elif mutation == "float_value":
        instrument["response_sets"][0]["options"][0]["value"] = 1.0
    elif mutation == "bad_aggregation":
        instrument["aggregation"] = "median"
    elif mutation == "unknown_domain_scale":
        instrument["domains"][0]["scale_ids"] = ["s1", "missing"]
    elif mutation == "scale_in_two_domains":
        instrument["domains"].append({"id": "d2", "name": "Again", "scale_ids": ["s1"]})
    elif mutation == "mixed_ranges":
        instrument["response_sets"].append(
            {"id": "four", "options": [{"value": v, "label": str(v)} for v in range(1, 5)]}
        )
        instrument["items"][0]["response_set"] = "four"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_member",
        "http_url",
        "bad_reverse",
        "extra_field",
        "unknown_response_set",
        "duplicate_values",
        "float_value",
        "bad_aggregation",
        "unknown_domain_scale",
        "scale_in_two_domains",
        "mixed_ranges",
    ],
)
def test_parse_instrument_rejects_invalid_schema(
    synthetic_instrument: dict[str, Any], mutation: str
) -> None:
    """Invalid sources, membership, response sets, domains and unknown fields are refused."""
    _mutate(synthetic_instrument, mutation)
    with pytest.raises(InstrumentValidationError):
        parse_instrument(synthetic_instrument)


def test_load_instrument_rejects_oversized_file(tmp_path: Path) -> None:
    """The loader refuses files above its fixed one megabyte limit."""
    path = tmp_path / "large.json"
    path.write_text(" " * 1_000_001, encoding="utf-8")
    with pytest.raises(InstrumentValidationError, match="exceeds"):
        load_instrument(path)


def test_parse_instrument_rejects_invalid_retrieval_date(
    synthetic_instrument: dict[str, Any],
) -> None:
    """Instrument metadata must use a parseable ISO retrieval date."""
    synthetic_instrument["retrieved"] = "yesterday"
    with pytest.raises(InstrumentValidationError, match="ISO date"):
        parse_instrument(synthetic_instrument)
