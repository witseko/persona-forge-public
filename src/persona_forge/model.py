"""Shared data types for instruments, scenarios and score results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseOption:
    """One answer choice: the stored integer value and the label shown to the user."""

    value: int
    label: str


@dataclass(frozen=True)
class ResponseSet:
    """A named, ordered list of answer choices copied from the instrument source."""

    id: str
    options: tuple[ResponseOption, ...]

    @property
    def minimum(self) -> int:
        """Return the lowest allowed value."""
        return min(option.value for option in self.options)

    @property
    def maximum(self) -> int:
        """Return the highest allowed value."""
        return max(option.value for option in self.options)

    @property
    def values(self) -> frozenset[int]:
        """Return every allowed value."""
        return frozenset(option.value for option in self.options)


@dataclass(frozen=True)
class Item:
    """A question belonging to exactly one leaf scale."""

    id: str
    text: str
    scale: str
    reverse: bool
    response_set: str


@dataclass(frozen=True)
class Scale:
    """A named leaf scale (a facet or a stand-alone scale) with its item identifiers."""

    id: str
    name: str
    item_ids: tuple[str, ...]


@dataclass(frozen=True)
class Domain:
    """A higher-order score that pools the items of several leaf scales, such as a Big Five
    domain built from its six facets."""

    id: str
    name: str
    scale_ids: tuple[str, ...]


@dataclass(frozen=True)
class Instrument:
    """A sourced instrument definition."""

    id: str
    name: str
    source_url: str
    retrieved: str
    citation: str
    licence: str
    attribution: str
    instructions: str
    notes: str
    aggregation: str  # "mean" or "sum", as the source specifies
    response_sets: tuple[ResponseSet, ...]
    items: tuple[Item, ...]
    scales: tuple[Scale, ...]
    domains: tuple[Domain, ...]

    def response_set(self, set_id: str) -> ResponseSet:
        """Return a response set by identifier."""
        for response_set in self.response_sets:
            if response_set.id == set_id:
                return response_set
        raise KeyError(set_id)


@dataclass(frozen=True)
class ScaleScore:
    """A scale or domain score with its descriptive, non-normed band.

    `score` is the mean or the sum of keyed item values, following the instrument.
    `position` places the mean keyed item value in the response range, from 0 (lowest
    possible) to 1 (highest possible), so bands work for any response format.
    """

    id: str
    name: str
    score: float
    position: float
    band: str
    item_count: int
    normed: bool = False


@dataclass(frozen=True)
class InstrumentScore:
    """All scale and domain scores for one completed instrument."""

    instrument_id: str
    scales: tuple[ScaleScore, ...]
    domains: tuple[ScaleScore, ...]


@dataclass(frozen=True)
class SJTOption:
    """One answer to an authored scenario and its weight on each scenario dimension."""

    id: str
    text: str
    weights: dict[str, float]


@dataclass(frozen=True)
class SJTScenario:
    """An authored work scenario. Every option weights the same set of dimensions."""

    id: str
    title: str
    prompt: str
    options: tuple[SJTOption, ...]

    def option(self, option_id: str) -> SJTOption:
        """Return an option by identifier."""
        for option in self.options:
            if option.id == option_id:
                return option
        raise KeyError(option_id)


@dataclass(frozen=True)
class SJTScore:
    """Mean selected weight for each SJT dimension, from 0 to 1."""

    means: dict[str, float]
