"""Authored content: scenario banks, dimensions, preferences, insights and presets."""

import json
from pathlib import Path

import pytest
from helpers import private_edition_only

from persona_forge.content import (
    SJT_DIR,
    ContentError,
    load_dimensions,
    load_preferences,
    load_sjt_bank,
)
from persona_forge.egos import load_presets
from persona_forge.flow import DEPTHS, ROLES
from persona_forge.insights import load_rules, load_strength_texts, load_wellbeing_text
from persona_forge.instruments import load_instrument_by_id


@pytest.mark.parametrize("bank_id", ["common", *ROLES])
def test_every_bank_has_twelve_valid_scenarios(bank_id: str) -> None:
    """12 shared plus 12 role scenarios give each role track the planned 24."""
    scenarios = load_sjt_bank(bank_id)
    assert len(scenarios) == 12
    assert all(len(scenario.options) == 4 for scenario in scenarios)


def test_deep_depth_uses_every_scenario() -> None:
    """Deep asks all 24 scenarios available to a role."""
    assert DEPTHS["deep"].common_scenarios + DEPTHS["deep"].role_scenarios == 24


def test_scenario_ids_are_unique_across_banks() -> None:
    """Answers are keyed by scenario id, so ids must be globally unique."""
    ids = [scenario.id for bank in ["common", *ROLES] for scenario in load_sjt_bank(bank)]
    assert len(ids) == len(set(ids))


def test_every_dimension_is_measured() -> None:
    """Each dimension appears in shared scenarios, so every role gets a score for it."""
    used = {d for scenario in load_sjt_bank("common") for d in scenario.options[0].weights}
    assert used == {dimension.id for dimension in load_dimensions()}


def _copy_sjt(tmp_path: Path) -> Path:
    """Copy the scenario folder so a test can corrupt it."""
    target = tmp_path / "sjt"
    target.mkdir()
    for path in SJT_DIR.glob("*.json"):
        (target / path.name).write_text(path.read_text())
    return target


@pytest.mark.parametrize("defect", ["unknown_dimension", "uneven_dimensions", "weight_range"])
def test_bank_validation_rejects_defects(tmp_path: Path, defect: str) -> None:
    """Unknown dimensions, uneven option weights and out-of-range weights are refused."""
    directory = _copy_sjt(tmp_path)
    path = directory / "common.json"
    data = json.loads(path.read_text())
    options = data["scenarios"][0]["options"]
    if defect == "unknown_dimension":
        options[0]["weights"] = {"made-up": 0.5, "assertiveness": 0.5}
    elif defect == "uneven_dimensions":
        options[0]["weights"] = {"assertiveness": 0.5}
    else:
        options[0]["weights"]["assertiveness"] = 1.5
    path.write_text(json.dumps(data))
    with pytest.raises(ContentError):
        load_sjt_bank("common", directory)


@private_edition_only
def test_preferences_and_insight_files_load() -> None:
    """Preferences, rules, strength texts and wellbeing wording are well formed."""
    assert len(load_preferences()) == 11
    rules = load_rules()
    assert rules
    via, riasec = load_strength_texts()
    via_scales = {scale.id for scale in load_instrument_by_id("ipip-via").scales}
    onet_scales = {scale.id for scale in load_instrument_by_id("onet-ip-sf").scales}
    assert set(via) == via_scales
    assert set(riasec) == onet_scales
    assert load_wellbeing_text().practical_tips


def test_statements_are_first_person_tendencies_without_labels() -> None:
    """Rules speak as the user, in tendencies, and never use clinical or labelling words."""
    banned = ("disorder", "diagnos", "neurotic", "you are a", "lazy", "you tend")
    for rule in load_rules():
        for text in (rule.statement, rule.softened):
            lowered = text.lower()
            assert not any(word in lowered for word in banned), text
            assert " I " in f" {text} " or " me" in text or " my " in f" {text} ", text


def test_rule_traits_exist_in_some_depth() -> None:
    """Every rule points at a trait key the profile builder can produce."""
    prefixes = ("big5:", "neo:", "hh:", "gse:", "ncs:", "sjt:")
    for rule in load_rules():
        assert rule.trait.startswith(prefixes), rule.id
        if rule.roles:
            assert set(rule.roles) <= set(ROLES)


def test_eight_presets_load() -> None:
    """The planned preset personas are all present."""
    assert set(load_presets()) == {
        "mentor",
        "strict-reviewer",
        "devils-advocate",
        "pair-programmer",
        "architect",
        "product-thinker",
        "executive-lens",
        "coach",
    }


def test_no_long_dashes_in_authored_content() -> None:
    """Authored text uses plain hyphens only (project rule)."""
    data_dir = SJT_DIR.parent
    for path in [
        *data_dir.glob("sjt/*.json"),
        *data_dir.glob("insights/*.json"),
        *data_dir.glob("egos/presets/*.json"),
        data_dir / "preferences.json",
    ]:
        text = path.read_text(encoding="utf-8")
        assert "–" not in text and "—" not in text, path.name
