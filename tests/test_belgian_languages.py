"""French and Dutch packs for Belgium: complete flows, IPIP-only coverage, safe text."""

import json
import re
from pathlib import Path

import pytest
from test_questionnaire import ScriptedPrompter

from persona_forge.answers import Answers, load_answers, save_answers
from persona_forge.flow import DEPTHS, ROLES, depth_instruments, wellbeing_instruments
from persona_forge.instruments import load_instrument_by_id
from persona_forge.languages import LANGUAGE_DIR, available_languages, load_language
from persona_forge.setup import Paths, setup_interactive
from persona_forge.translations import translate_instrument

BELGIAN = ("fr-BE", "nl-BE")
IPIP = {"mini-ipip", "ipip-neo-120", "ipip-hexaco-hh", "ipip-via"}
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


@pytest.mark.parametrize("code", BELGIAN)
def test_pack_is_complete_and_covers_only_ipip(code: str) -> None:
    """Only questionnaires with granted translation permission are included."""
    assert code in available_languages()
    pack = load_language(code)
    assert set(pack.instrument_ids) == IPIP
    permissions = json.loads((LANGUAGE_DIR.parent / "permissions.json").read_text())
    for instrument_id in pack.instrument_ids:
        assert permissions["instruments"][instrument_id]["translation"] == "granted"


@pytest.mark.parametrize("code", BELGIAN)
def test_every_message_keeps_its_placeholders_and_plain_hyphens(code: str) -> None:
    """Placeholders survive translation exactly; no long dashes or control characters."""
    english = json.loads((LANGUAGE_DIR / "en" / "messages.json").read_text())
    translated = json.loads((LANGUAGE_DIR / code / "messages.json").read_text())
    assert list(translated) == list(english)
    for source, target in translated.items():
        assert target.strip(), source
        assert set(PLACEHOLDER.findall(target)) == set(PLACEHOLDER.findall(source)), source
        assert not re.search(r"[–—\x00-\x08\x0b-\x1f]", target), source


@pytest.mark.parametrize("code", BELGIAN)
def test_overlays_keep_items_and_values_and_are_labelled_unvalidated(code: str) -> None:
    """Item ids and response values match the canonical instrument; wording is honest."""
    for instrument_id in IPIP:
        original = load_instrument_by_id(instrument_id)
        translated = translate_instrument(original, code)
        assert [item.id for item in translated.items] == [item.id for item in original.items]
        assert all(
            item.text and item.text != source.text
            for item, source in zip(translated.items, original.items, strict=True)
        )
        overlay = json.loads(
            (LANGUAGE_DIR / code / "instruments" / f"{instrument_id}.json").read_text()
        )
        assert overlay["language"] == code
        assert "not psychometrically validated" in overlay["licence"]


@pytest.mark.parametrize("depth", list(DEPTHS))
@pytest.mark.parametrize("role", list(ROLES))
@pytest.mark.parametrize("code", BELGIAN)
def test_every_role_and_depth_completes_without_english_ui(
    tmp_path: Path, code: str, depth: str, role: str
) -> None:
    """Scenario banks, review, personas and controls all show the selected language."""

    class Flow(ScriptedPrompter):
        """Capture every displayed label."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            self.messages.extend(label for _, label in choices)
            return super().select(message, choices)

        def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]:
            self.messages.extend(label for _, label in choices)
            return super().checkbox(message, choices)

    paths = Paths(tmp_path / "out", tmp_path / "home")
    paths.out_dir.mkdir()
    save_answers(
        paths.answers,
        Answers(
            consent=True,
            name="Tester",
            depth=depth,
            role=role,
            seniority="senior",
            questionnaire_language=code,
        ),
    )
    prompter = Flow(confirm=False)
    setup_interactive(paths, prompter, link=False)
    completed = load_answers(paths.answers)
    assert completed.review_done and completed.egos["done"]
    assert set(completed.instruments) <= IPIP
    assert set(completed.instrument_languages.values()) == {code}
    assert not wellbeing_instruments(code) and not completed.wellbeing_opt_in
    pack = load_language(code)
    untranslated = [
        source
        for source, target in pack.messages.items()
        if source != target and len(source) >= 20 and "{" not in source
    ]
    for message in prompter.messages:
        assert not any(source in message for source in untranslated), message


@pytest.mark.parametrize("code", BELGIAN)
def test_unpermitted_questionnaires_are_left_out(code: str) -> None:
    """GSE, NCS-6, O*NET and CBI are not offered until translation is permitted."""
    for depth in DEPTHS:
        offered = {instrument.id for instrument in depth_instruments(depth, code)}
        assert offered <= IPIP
        assert not offered & {"gse", "ncs-6", "onet-ip-sf", "cbi-work"}
