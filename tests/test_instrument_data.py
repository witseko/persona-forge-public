"""Check the shipped instrument files against counts and keys read from their sources.

The expected values below were transcribed by hand from the primary source pages
listed in docs/instruments.md, independently of the script that extracted the items.
"""

import pytest
from helpers import private_edition_only

from persona_forge.instruments import INSTRUMENT_DIR, load_instrument, load_instrument_by_id
from persona_forge.permissions import instrument_installed

EXPECTED_ITEM_COUNTS = {
    "mini-ipip": 20,
    "ipip-neo-120": 120,
    "ipip-hexaco-hh": 40,
    "ipip-via": 213,
    "gse": 10,
    "ncs-6": 6,
    "onet-ip-sf": 60,
    "cbi-work": 7,
}

# Reverse-keyed ("- keyed") items per facet on https://ipip.ori.org/30FacetNEO-PI-RItems.htm.
NEO_REVERSED_PER_FACET = {
    "n1": 0, "n2": 1, "n3": 1, "n4": 1, "n5": 3, "n6": 1,
    "e1": 2, "e2": 2, "e3": 1, "e4": 1, "e5": 0, "e6": 0,
    "o1": 0, "o2": 2, "o3": 2, "o4": 3, "o5": 3, "o6": 2,
    "a1": 1, "a2": 4, "a3": 2, "a4": 4, "a5": 4, "a6": 2,
    "c1": 0, "c2": 3, "c3": 2, "c4": 2, "c5": 2, "c6": 4,
}  # fmt: skip

MINI_IPIP_REVERSED = {
    "Don't talk a lot.",
    "Keep in the background.",
    "Am not really interested in others.",
    "Am not interested in other people's problems.",
    "Often forget to put things back in their proper place.",
    "Make a mess of things.",
    "Am relaxed most of the time.",
    "Seldom feel blue.",
    "Have difficulty understanding abstract ideas.",
    "Am not interested in abstract ideas.",
    "Do not have a good imagination.",
}

# Item counts declared in each scale heading on https://ipip.ori.org/newVIAKey.htm.
VIA_SCALE_SIZES = [8, 9, 9, 10, 9, 9, 8, 8, 9, 8, 9, 9, 10, 7, 10, 9, 8, 9, 9, 11, 7, 9, 10, 9]


def _reversed_by_scale(instrument_id: str) -> dict[str, int]:
    """Count reverse-keyed items in each scale."""
    instrument = load_instrument_by_id(instrument_id)
    counts = {scale.id: 0 for scale in instrument.scales}
    for item in instrument.items:
        counts[item.scale] += item.reverse
    return counts


@private_edition_only
def test_every_shipped_file_is_expected_and_valid() -> None:
    """The data folder holds exactly the approved instruments, each passing validation."""
    files = sorted(path.stem for path in INSTRUMENT_DIR.glob("*.json"))
    assert files == sorted(EXPECTED_ITEM_COUNTS)
    for path in INSTRUMENT_DIR.glob("*.json"):
        instrument = load_instrument(path)
        assert len(instrument.items) == EXPECTED_ITEM_COUNTS[instrument.id]
        assert instrument.source_url.startswith("https://")
        assert instrument.licence and instrument.citation and instrument.retrieved
        assert all(scale.item_ids for scale in instrument.scales)


def test_dropped_instruments_are_absent() -> None:
    """Instruments without verified permission are not shipped (decision of 2026-10-23)."""
    shipped = {path.stem for path in INSTRUMENT_DIR.glob("*.json")}
    assert not shipped & {"grit-s", "nfc-15", "rmeq", "asrs"}


def test_mini_ipip_keys_match_source() -> None:
    """Exactly the eleven items listed as negatively keyed are reversed."""
    instrument = load_instrument_by_id("mini-ipip")
    assert {item.text for item in instrument.items if item.reverse} == MINI_IPIP_REVERSED
    assert all(len(scale.item_ids) == 4 for scale in instrument.scales)


def test_neo_120_facets_domains_and_keys_match_source() -> None:
    """Thirty four-item facets, five 24-item domains and the source's reverse keys."""
    instrument = load_instrument_by_id("ipip-neo-120")
    assert all(len(scale.item_ids) == 4 for scale in instrument.scales)
    assert _reversed_by_scale("ipip-neo-120") == NEO_REVERSED_PER_FACET
    scale_sizes = {scale.id: len(scale.item_ids) for scale in instrument.scales}
    assert [sum(scale_sizes[s] for s in domain.scale_ids) for domain in instrument.domains] == [
        24
    ] * 5


def test_hexaco_honesty_humility_keys_match_source() -> None:
    """Sincerity 9, Fairness 5, Greed Avoidance 8 and Modesty 6 negatively keyed items."""
    assert _reversed_by_scale("ipip-hexaco-hh") == {
        "sincerity": 9,
        "fairness": 5,
        "greed-avoidance": 8,
        "modesty": 6,
    }


def test_via_scale_sizes_match_source_headings() -> None:
    """Each revised IPIP-VIA scale holds the number of items its heading declares."""
    instrument = load_instrument_by_id("ipip-via")
    assert [len(scale.item_ids) for scale in instrument.scales] == VIA_SCALE_SIZES


@pytest.mark.parametrize(
    ("instrument_id", "reversed_ids"),
    [
        ("gse", set()),  # "No recoding."
        ("ncs-6", {"ncs-03", "ncs-04"}),  # items marked (R)
        ("onet-ip-sf", set()),
        ("cbi-work", {"cbi-work-7"}),  # "Reversed score for last question."
    ],
)
def test_short_scale_keys_match_source(instrument_id: str, reversed_ids: set[str]) -> None:
    """Reverse keys of the short non-IPIP scales follow their scoring instructions."""
    if not instrument_installed(instrument_id):
        pytest.skip("left out of the public edition")
    instrument = load_instrument_by_id(instrument_id)
    assert {item.id for item in instrument.items if item.reverse} == reversed_ids


@private_edition_only
def test_scoring_formats_match_sources() -> None:
    """GSE sums 1-4 answers, O*NET counts checks, CBI averages 0-100 answers."""
    gse = load_instrument_by_id("gse")
    assert (gse.aggregation, gse.response_sets[0].minimum, gse.response_sets[0].maximum) == (
        "sum",
        1,
        4,
    )
    onet = load_instrument_by_id("onet-ip-sf")
    assert onet.aggregation == "sum"
    assert [len(scale.item_ids) for scale in onet.scales] == [10] * 6
    cbi = load_instrument_by_id("cbi-work")
    assert cbi.aggregation == "mean"
    assert {(s.minimum, s.maximum) for s in cbi.response_sets} == {(0, 100)}
    assert [item.response_set for item in cbi.items] == ["degree"] * 3 + ["frequency"] * 4
