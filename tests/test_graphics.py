"""README and docs graphics: generated from data, readable, honest and themed."""

import re

import pytest

from persona_forge.graphics import (
    GRAPHICS,
    IMAGES_DIR,
    PILOT_NOTE,
    fit_average,
    fits,
    judge_counts,
    load_summary,
    render_all,
)


def test_committed_images_match_the_generator() -> None:
    """Run `make graphics` after changing the numbers; the images never drift."""
    for name, content in render_all(load_summary()).items():
        assert (IMAGES_DIR / name).read_text(encoding="utf-8") == content, name


def test_every_graphic_is_described_and_themed() -> None:
    """Screen readers get the finding in words; light and dark both have colors."""
    for name, content in render_all(load_summary()).items():
        assert re.search(r"<title[^>]*>[^<]+</title>", content), name
        assert re.search(r"<desc[^>]*>[^<]{20,}</desc>", content), name
        assert "prefers-color-scheme: dark" in content, name
        assert "#" + "e34948" not in content.lower(), name  # no red anywhere


def test_pilot_graphics_carry_their_caveat() -> None:
    """Every pilot image says it used made-up people; the product diagram does not need to."""
    images = render_all(load_summary())
    for name, content in images.items():
        if name == "how-it-works.svg":
            assert PILOT_NOTE not in content
        else:
            assert PILOT_NOTE in content, name


def test_plain_words_and_plain_hyphens_only() -> None:
    """No statistics jargon and no long dashes in what readers see."""
    jargon = ("pairwise", "bootstrap", "interval", "condition", "baseline", "signal")
    for name, content in render_all(load_summary()).items():
        visible = " ".join(re.findall(r">([^<>]+)<", content)).lower()
        assert not [word for word in jargon if word in visible], name
        assert "–" not in content and "—" not in content, name


def test_text_that_would_overflow_stops_the_build() -> None:
    """A label wider than its box raises instead of being drawn past the edge."""
    assert fits("Same", 24, 100, bold=True) == "Same"
    with pytest.raises(ValueError, match="does not fit"):
        fits("Inconclusive and then some", 24, 160, bold=True)


def test_numbers_come_from_the_summary() -> None:
    """Averages and judge totals are computed from the data file, not typed in."""
    summary = load_summary()
    average = fit_average(summary)
    assert max(average, key=average.get) == "note"
    counts = dict(judge_counts(summary))
    assert counts["vs no instructions"] == [22, 4, 7, 15]
    assert counts["vs a short note"] == [0, 4, 36, 8]
    assert all(sum(row) == 48 for row in counts.values())
    assert len(GRAPHICS) <= 7
