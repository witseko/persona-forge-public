"""Score sourced instruments and authored situational judgment scenarios.

Bands are descriptive only. They are not population norms: "low" and "high" describe
where a mean answer sits within the response range, nothing more.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from math import isfinite

from persona_forge.model import Instrument, InstrumentScore, Item, ScaleScore, SJTScenario, SJTScore

# The approved cutoffs are "low below 2.6, high above 3.4" on a 1 to 5 mean. As positions
# in the response range ((mean - 1) / 4) they are 0.4 and 0.6, which lets the same rule
# apply to 1-to-4, 0-to-100 and 0-or-1 formats without inventing new numbers.
LOW_BELOW = 0.4
HIGH_ABOVE = 0.6


def validate_answers(instrument: Instrument, answers: Mapping[str, int]) -> None:
    """Require exactly one allowed integer answer for every item."""
    known_items = {item.id: item for item in instrument.items}
    if set(answers) != set(known_items):
        raise ValueError("answers must contain exactly one response for each instrument item")
    for item_id, answer in answers.items():
        allowed = instrument.response_set(known_items[item_id].response_set).values
        if type(answer) is not int or answer not in allowed:
            raise ValueError(f"answer for {item_id} is not an allowed response value")


def keyed_value(instrument: Instrument, item: Item, answer: int) -> int:
    """Apply the reverse key: the answer is mirrored inside its response range."""
    if not item.reverse:
        return answer
    response_set = instrument.response_set(item.response_set)
    return response_set.minimum + response_set.maximum - answer


def item_position(instrument: Instrument, item: Item, answer: int) -> float:
    """Place a keyed answer in its response range, from 0 to 1."""
    response_set = instrument.response_set(item.response_set)
    span = response_set.maximum - response_set.minimum
    return (keyed_value(instrument, item, answer) - response_set.minimum) / span


def score_instrument(instrument: Instrument, answers: Mapping[str, int]) -> InstrumentScore:
    """Calculate every scale and domain score for a complete answer set."""
    validate_answers(instrument, answers)
    item_by_id = {item.id: item for item in instrument.items}
    scale_by_id = {scale.id: scale for scale in instrument.scales}
    scales = tuple(
        _pooled_score(instrument, scale.id, scale.name, scale.item_ids, item_by_id, answers)
        for scale in instrument.scales
    )
    domains = tuple(
        _pooled_score(
            instrument,
            domain.id,
            domain.name,
            [
                item_id
                for scale_id in domain.scale_ids
                for item_id in scale_by_id[scale_id].item_ids
            ],
            item_by_id,
            answers,
        )
        for domain in instrument.domains
    )
    return InstrumentScore(instrument.id, scales, domains)


def _pooled_score(
    instrument: Instrument,
    score_id: str,
    name: str,
    item_ids: Iterable[str],
    item_by_id: Mapping[str, Item],
    answers: Mapping[str, int],
) -> ScaleScore:
    """Aggregate keyed values of the given items with the instrument's mean or sum rule."""
    items = [item_by_id[item_id] for item_id in item_ids]
    keyed = [keyed_value(instrument, item, answers[item.id]) for item in items]
    positions = [item_position(instrument, item, answers[item.id]) for item in items]
    total = sum(keyed)
    score = total if instrument.aggregation == "sum" else total / len(keyed)
    position = sum(positions) / len(positions)
    return ScaleScore(score_id, name, score, position, band_for_position(position), len(items))


def band_for_position(position: float) -> str:
    """Return the descriptive, non-normed band for a 0-to-1 position."""
    if not 0 <= position <= 1:
        raise ValueError("position must be between 0 and 1")
    # Rounding removes floating point noise, so 2.6 on a 1-to-5 scale is exactly 0.4.
    position = round(position, 9)
    if position < LOW_BELOW:
        return "low"
    if position > HIGH_ABOVE:
        return "high"
    return "mid"


def score_sjt(scenarios: tuple[SJTScenario, ...], answers: Mapping[str, str]) -> SJTScore:
    """Average chosen option weights by dimension across answered scenarios."""
    if not scenarios:
        raise ValueError("at least one scenario is required")
    by_id = {scenario.id: scenario for scenario in scenarios}
    if len(by_id) != len(scenarios) or set(answers) != set(by_id):
        raise ValueError("answers must contain exactly one response for each unique scenario")
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for scenario_id, option_id in answers.items():
        scenario = by_id[scenario_id]
        try:
            option = scenario.option(option_id)
        except KeyError as error:
            raise ValueError(f"unknown option {option_id} for scenario {scenario_id}") from error
        for dimension, weight in option.weights.items():
            if (
                not isinstance(weight, int | float)
                or isinstance(weight, bool)
                or not isfinite(weight)
                or not 0 <= weight <= 1
            ):
                raise ValueError("SJT weights must be numbers from 0 to 1")
            totals[dimension] += weight
            counts[dimension] += 1
    return SJTScore({dimension: totals[dimension] / counts[dimension] for dimension in totals})
