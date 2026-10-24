"""Load and validate JSON instrument definitions.

Instrument files hold items copied verbatim from a primary source. The loader checks
the structure strictly so that a typo in a data file fails loudly instead of silently
changing a score.
"""

from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from persona_forge.files import DATA_DIR, DataFileError, read_json_file
from persona_forge.model import Domain, Instrument, Item, ResponseOption, ResponseSet, Scale

INSTRUMENT_DIR = DATA_DIR / "instruments"

INSTRUMENT_FIELDS = {
    "id",
    "name",
    "source_url",
    "retrieved",
    "citation",
    "licence",
    "attribution",
    "instructions",
    "notes",
    "aggregation",
    "response_sets",
    "items",
    "scales",
    "domains",
}
AGGREGATIONS = {"mean", "sum"}


class InstrumentValidationError(ValueError):
    """Raised when an instrument file is malformed or internally inconsistent."""


def load_instrument(path: Path) -> Instrument:
    """Read one bounded-size JSON instrument file and validate its schema."""
    try:
        raw = read_json_file(path)
    except DataFileError as error:
        raise InstrumentValidationError(str(error)) from error
    return parse_instrument(raw)


def load_instrument_by_id(instrument_id: str, directory: Path = INSTRUMENT_DIR) -> Instrument:
    """Load `<directory>/<instrument_id>.json`, accepting only simple identifiers."""
    if not instrument_id.replace("-", "").isalnum():
        raise InstrumentValidationError("instrument identifiers use letters, digits and '-'")
    instrument = load_instrument(directory / f"{instrument_id}.json")
    if instrument.id != instrument_id:
        raise InstrumentValidationError("instrument id does not match its file name")
    return instrument


def parse_instrument(raw: Any) -> Instrument:
    """Validate a decoded instrument object and convert it to immutable data types."""
    if not isinstance(raw, dict):
        raise InstrumentValidationError("instrument must be a JSON object")
    if set(raw) != INSTRUMENT_FIELDS:
        raise InstrumentValidationError("instrument fields do not match the required schema")
    for field in ("id", "name", "retrieved", "citation", "licence"):
        _require_text(raw[field], field, 1000)
    for field in ("attribution", "instructions", "notes"):
        _require_text(raw[field], field, 4000, allow_empty=True)
    _validate_source_url(raw["source_url"])
    try:
        date.fromisoformat(raw["retrieved"])
    except ValueError as error:
        raise InstrumentValidationError("retrieved must be an ISO date") from error
    if raw["aggregation"] not in AGGREGATIONS:
        raise InstrumentValidationError("aggregation must be 'mean' or 'sum'")

    response_sets = _parse_list(raw["response_sets"], "response_sets", 20, _parse_response_set)
    set_by_id = {response_set.id: response_set for response_set in response_sets}
    if len(set_by_id) != len(response_sets):
        raise InstrumentValidationError("response set identifiers must be unique")
    default_set = response_sets[0].id
    items = _parse_list(raw["items"], "items", 1000, lambda item: _parse_item(item, default_set))
    scales = _parse_list(raw["scales"], "scales", 100, _parse_scale)
    domains = tuple(_parse_domain(domain) for domain in _require_list(raw["domains"], 20))

    _check_unique([item.id for item in items], "item")
    _check_unique([scale.id for scale in scales], "scale")
    _check_unique([domain.id for domain in domains], "domain")
    item_by_id = {item.id: item for item in items}
    for item in items:
        if item.response_set not in set_by_id:
            raise InstrumentValidationError(f"item {item.id} uses an unknown response set")
    _check_membership(items, scales, item_by_id)
    _check_scale_ranges(scales, item_by_id, set_by_id)
    _check_domains(domains, {scale.id for scale in scales})

    return Instrument(
        id=raw["id"],
        name=raw["name"],
        source_url=raw["source_url"],
        retrieved=raw["retrieved"],
        citation=raw["citation"],
        licence=raw["licence"],
        attribution=raw["attribution"],
        instructions=raw["instructions"],
        notes=raw["notes"],
        aggregation=raw["aggregation"],
        response_sets=response_sets,
        items=items,
        scales=scales,
        domains=domains,
    )


def _require_text(value: Any, field: str, limit: int, allow_empty: bool = False) -> str:
    """Return `value` if it is a string within `limit` characters."""
    if not isinstance(value, str) or len(value) > limit or (not allow_empty and not value.strip()):
        raise InstrumentValidationError(f"{field} must be a string of at most {limit} characters")
    return value


def _require_list(value: Any, limit: int) -> list[Any]:
    """Return `value` if it is a list with at most `limit` entries."""
    if not isinstance(value, list) or len(value) > limit:
        raise InstrumentValidationError(f"expected a list of at most {limit} entries")
    return value


def _parse_list(value: Any, field: str, limit: int, parse: Any) -> tuple[Any, ...]:
    """Parse a required, non-empty list with a per-entry parser."""
    if not isinstance(value, list) or not value or len(value) > limit:
        raise InstrumentValidationError(
            f"{field} must be a non-empty list of at most {limit} entries"
        )
    return tuple(parse(entry) for entry in value)


def _validate_source_url(value: Any) -> None:
    """Accept only HTTPS source links of a reasonable length."""
    if not isinstance(value, str) or len(value) > 2048:
        raise InstrumentValidationError("source_url must be an HTTPS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise InstrumentValidationError("source_url must be an HTTPS URL")


def _check_unique(identifiers: list[str], kind: str) -> None:
    """Refuse duplicated identifiers."""
    if len(set(identifiers)) != len(identifiers):
        raise InstrumentValidationError(f"{kind} identifiers must be unique")


def _parse_response_set(raw: Any) -> ResponseSet:
    """Validate one response set: at least two options with distinct integer values."""
    if not isinstance(raw, dict) or set(raw) != {"id", "options"}:
        raise InstrumentValidationError("each response set needs id and options fields")
    _require_text(raw["id"], "response set id", 100)
    options = []
    for option in _require_list(raw["options"], 20):
        if not isinstance(option, dict) or set(option) != {"value", "label"}:
            raise InstrumentValidationError("each response option needs value and label")
        if type(option["value"]) is not int:
            raise InstrumentValidationError("response option values must be integers")
        _require_text(option["label"], "response option label", 200)
        options.append(ResponseOption(option["value"], option["label"]))
    if len(options) < 2 or len({option.value for option in options}) != len(options):
        raise InstrumentValidationError("a response set needs at least two distinct values")
    return ResponseSet(raw["id"], tuple(options))


def _parse_item(raw: Any, default_set: str) -> Item:
    """Validate one item entry. `response_set` is optional and defaults to the first set."""
    required = {"id", "text", "scale", "reverse"}
    if not isinstance(raw, dict) or not required <= set(raw) <= required | {"response_set"}:
        raise InstrumentValidationError("each item needs id, text, scale and reverse fields")
    for key in ("id", "scale"):
        _require_text(raw[key], f"item {key}", 100)
    _require_text(raw["text"], "item text", 2000)
    if type(raw["reverse"]) is not bool:
        raise InstrumentValidationError("item reverse must be a boolean")
    response_set = raw.get("response_set", default_set)
    _require_text(response_set, "item response_set", 100)
    return Item(raw["id"], raw["text"], raw["scale"], raw["reverse"], response_set)


def _parse_id_list(value: Any, field: str) -> tuple[str, ...]:
    """Validate a non-empty list of identifier strings."""
    if (
        not isinstance(value, list)
        or not value
        or len(value) > 1000
        or not all(isinstance(entry, str) and entry for entry in value)
    ):
        raise InstrumentValidationError(f"{field} must be a non-empty list of strings")
    return tuple(value)


def _parse_scale(raw: Any) -> Scale:
    """Validate one scale entry."""
    if not isinstance(raw, dict) or set(raw) != {"id", "name", "item_ids"}:
        raise InstrumentValidationError("each scale needs id, name and item_ids fields")
    _require_text(raw["id"], "scale id", 100)
    _require_text(raw["name"], "scale name", 200)
    return Scale(raw["id"], raw["name"], _parse_id_list(raw["item_ids"], "scale item_ids"))


def _parse_domain(raw: Any) -> Domain:
    """Validate one domain entry."""
    if not isinstance(raw, dict) or set(raw) != {"id", "name", "scale_ids"}:
        raise InstrumentValidationError("each domain needs id, name and scale_ids fields")
    _require_text(raw["id"], "domain id", 100)
    _require_text(raw["name"], "domain name", 200)
    return Domain(raw["id"], raw["name"], _parse_id_list(raw["scale_ids"], "domain scale_ids"))


def _check_membership(
    items: tuple[Item, ...], scales: tuple[Scale, ...], item_by_id: dict[str, Item]
) -> None:
    """Every item belongs to exactly one scale, and both sides of the link agree."""
    membership: list[str] = []
    for scale in scales:
        for item_id in scale.item_ids:
            if item_id not in item_by_id or item_by_id[item_id].scale != scale.id:
                raise InstrumentValidationError(
                    "scale membership does not match item scale references"
                )
            membership.append(item_id)
    if sorted(membership) != sorted(item.id for item in items):
        raise InstrumentValidationError("every item must belong to exactly one scale")


def _check_scale_ranges(
    scales: tuple[Scale, ...],
    item_by_id: dict[str, Item],
    set_by_id: dict[str, ResponseSet],
) -> None:
    """Items pooled in one scale must share a response range, or the mean is meaningless."""
    for scale in scales:
        ranges = {
            (
                set_by_id[item_by_id[item_id].response_set].minimum,
                set_by_id[item_by_id[item_id].response_set].maximum,
            )
            for item_id in scale.item_ids
        }
        if len(ranges) != 1:
            raise InstrumentValidationError(f"scale {scale.id} mixes response ranges")


def _check_domains(domains: tuple[Domain, ...], scale_ids: set[str]) -> None:
    """Domains reference known scales, and a scale sits in at most one domain."""
    seen: set[str] = set()
    for domain in domains:
        for scale_id in domain.scale_ids:
            if scale_id not in scale_ids:
                raise InstrumentValidationError(f"domain {domain.id} names an unknown scale")
            if scale_id in seen:
                raise InstrumentValidationError(f"scale {scale_id} is in more than one domain")
            seen.add(scale_id)
