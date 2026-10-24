"""Check Likert, reverse-key, aggregation, band and SJT calculations by hand."""

from typing import Any

import pytest

from persona_forge.instruments import parse_instrument
from persona_forge.model import SJTOption, SJTScenario
from persona_forge.scoring import band_for_position, score_instrument, score_sjt


def test_likert_scores_reverse_key_scales_and_domain(synthetic_instrument: dict[str, Any]) -> None:
    """q1=5 and reversed q2=1 give s1 = 5; q3=2, q4=3 give s2 = 2.5; the domain is 3.75."""
    instrument = parse_instrument(synthetic_instrument)
    result = score_instrument(instrument, {"q1": 5, "q2": 1, "q3": 2, "q4": 3})
    scale_one, scale_two = result.scales
    assert (scale_one.score, scale_one.position, scale_one.band) == (5, 1.0, "high")
    assert (scale_two.score, scale_two.band) == (2.5, "low")
    assert scale_two.position == pytest.approx(0.375)
    (domain,) = result.domains
    assert domain.score == 3.75
    assert domain.item_count == 4
    assert domain.normed is False


def test_sum_aggregation_on_a_four_point_scale(synthetic_instrument: dict[str, Any]) -> None:
    """A sum-scored 1-to-4 format reports the sum and bands by the mean position."""
    synthetic_instrument["aggregation"] = "sum"
    synthetic_instrument["response_sets"] = [
        {"id": "four", "options": [{"value": v, "label": str(v)} for v in range(1, 5)]}
    ]
    instrument = parse_instrument(synthetic_instrument)
    result = score_instrument(instrument, {"q1": 4, "q2": 1, "q3": 2, "q4": 3})
    # q2 reverses to 4, so s1 = 4 + 4 = 8 (position 1.0); s2 = 2 + 3 = 5 (position 0.5).
    assert [(s.score, s.position, s.band) for s in result.scales] == [
        (8, 1.0, "high"),
        (5, 0.5, "mid"),
    ]


def test_zero_to_hundred_scale_with_two_response_sets(synthetic_instrument: dict[str, Any]) -> None:
    """Items may use different labels if their numeric range is shared, as in burnout scales."""
    frequency = [100, 75, 50, 25, 0]
    synthetic_instrument["response_sets"] = [
        {"id": "freq", "options": [{"value": v, "label": f"f{v}"} for v in frequency]},
        {"id": "degree", "options": [{"value": v, "label": f"d{v}"} for v in frequency]},
    ]
    synthetic_instrument["items"][0]["response_set"] = "degree"
    instrument = parse_instrument(synthetic_instrument)
    result = score_instrument(instrument, {"q1": 75, "q2": 25, "q3": 0, "q4": 50})
    # q2 reverses to 100 - 25 = 75, so s1 = (75 + 75) / 2 = 75.
    assert result.scales[0].score == 75
    assert result.scales[0].band == "high"
    assert result.scales[1].score == 25


def test_binary_checklist_counts_checked_items(synthetic_instrument: dict[str, Any]) -> None:
    """A 0/1 checklist summed per scale yields the number of checked activities."""
    synthetic_instrument["aggregation"] = "sum"
    synthetic_instrument["response_sets"] = [
        {"id": "check", "options": [{"value": 0, "label": "No"}, {"value": 1, "label": "Yes"}]}
    ]
    for item in synthetic_instrument["items"]:
        item["reverse"] = False
    instrument = parse_instrument(synthetic_instrument)
    result = score_instrument(instrument, {"q1": 1, "q2": 1, "q3": 0, "q4": 1})
    assert [scale.score for scale in result.scales] == [2, 1]


@pytest.mark.parametrize(
    ("mean", "expected"), [(2.59, "low"), (2.6, "mid"), (3.4, "mid"), (3.41, "high")]
)
def test_band_thresholds_match_documented_one_to_five_cutoffs(mean: float, expected: str) -> None:
    """Position bands reproduce "low below 2.6, high above 3.4" on a 1 to 5 mean."""
    assert band_for_position((mean - 1) / 4) == expected


def test_band_rejects_out_of_range_position() -> None:
    """Positions outside 0 to 1 indicate a scoring bug and are refused."""
    with pytest.raises(ValueError):
        band_for_position(1.01)


@pytest.mark.parametrize(
    "answers",
    [
        {"q1": 0, "q2": 2, "q3": 3, "q4": 3},
        {"q1": True, "q2": 2, "q3": 3, "q4": 3},
        {"q1": 2.0, "q2": 2, "q3": 3, "q4": 3},
        {"q1": 2},
        {"q1": 2, "q2": 2, "q3": 3, "q4": 3, "extra": 1},
    ],
)
def test_likert_rejects_invalid_or_incomplete_answers(
    synthetic_instrument: dict[str, Any], answers: dict[str, Any]
) -> None:
    """Scores require complete integer responses drawn from the response set."""
    with pytest.raises(ValueError):
        score_instrument(parse_instrument(synthetic_instrument), answers)


def _scenario(scenario_id: str, weights: dict[str, dict[str, float]]) -> SJTScenario:
    """Build a synthetic scenario from option weights."""
    options = tuple(SJTOption(option_id, "text", w) for option_id, w in weights.items())
    return SJTScenario(scenario_id, "title", "prompt", options)


def test_sjt_means_selected_weights_by_dimension() -> None:
    """Selected fixture choices produce hand-calculated dimension means."""
    scenarios = (
        _scenario("case-a", {"option-1": {"ownership": 1.0, "speed": 0.0}}),
        _scenario("case-b", {"option-2": {"ownership": 0.5, "speed": 1.0}}),
    )
    score = score_sjt(scenarios, {"case-a": "option-1", "case-b": "option-2"})
    assert score.means == {"ownership": 0.75, "speed": 0.5}


def test_sjt_rejects_unknown_option() -> None:
    """Answer identifiers must belong to the selected scenario."""
    scenarios = (_scenario("case-a", {"option-1": {"ownership": 0.5}}),)
    with pytest.raises(ValueError, match="unknown option"):
        score_sjt(scenarios, {"case-a": "missing"})


@pytest.mark.parametrize("weight", [float("nan"), float("inf"), -0.1, 1.1])
def test_sjt_rejects_nonfinite_or_out_of_range_weights(weight: float) -> None:
    """Only finite weights from zero to one can contribute to a score."""
    scenarios = (_scenario("case-a", {"option-1": {"ownership": weight}}),)
    with pytest.raises(ValueError, match="weights"):
        score_sjt(scenarios, {"case-a": "option-1"})


def test_sjt_rejects_empty_scenarios() -> None:
    """An empty scenario set cannot produce a meaningful SJT result."""
    with pytest.raises(ValueError, match="at least one"):
        score_sjt((), {})
