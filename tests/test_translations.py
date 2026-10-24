"""Questionnaire translation coverage, scoring, privacy and resumable language choice."""

import json
from pathlib import Path

import pytest
from helpers import make_answers, private_edition_only
from test_questionnaire import ScriptedPrompter

from persona_forge.answers import Answers, AnswersError, load_answers, parse_answers, save_answers
from persona_forge.instruments import load_instrument_by_id
from persona_forge.languages import load_language
from persona_forge.questionnaire import SetupInterrupted, ask_instrument, run_questionnaire
from persona_forge.scoring import score_instrument
from persona_forge.setup import Paths, setup_interactive, setup_non_interactive
from persona_forge.translations import translate_instrument


def _ukrainian_cbi_item(index: int) -> str:
    """Read Ukrainian CBI item text from its overlay instead of quoting it here."""
    return translate_instrument(load_instrument_by_id("cbi-work"), "uk").items[index].text


@pytest.mark.parametrize("instrument_id", sorted(load_language("uk").instrument_ids))
def test_translation_covers_every_item_and_preserves_scoring(instrument_id: str) -> None:
    """Only display strings change, including reverse-keyed items and response labels."""
    original = load_instrument_by_id(instrument_id)
    translated = translate_instrument(original, "uk")
    assert translated.scales == original.scales
    assert translated.domains == original.domains
    assert translated.aggregation == original.aggregation
    assert translated.instructions != original.instructions
    assert len(translated.items) == len(original.items)
    for before, after in zip(original.items, translated.items, strict=True):
        assert (before.id, before.scale, before.reverse, before.response_set) == (
            after.id,
            after.scale,
            after.reverse,
            after.response_set,
        )
        assert before.text != after.text
        assert any("а" <= letter <= "я" for letter in after.text)
    responses = {}
    for index, item in enumerate(original.items):
        options = original.response_set(item.response_set).options
        responses[item.id] = options[index % len(options)].value
    assert score_instrument(original, responses) == score_instrument(translated, responses)
    for before, after in zip(original.response_sets, translated.response_sets, strict=True):
        assert before.values == after.values
        assert [option.value for option in before.options] == [
            option.value for option in after.options
        ]


def test_ukrainian_prompts_use_translated_items_and_options() -> None:
    """Translated IPIP text is already first person and must not gain an English 'I'."""

    class CapturingPrompter(ScriptedPrompter):
        """Keep answer labels as well as the question text."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            self.messages.extend(label for _, label in choices)
            return super().select(message, choices)

    answers = Answers(questionnaire_language="uk")
    prompter = CapturingPrompter(confirm=False)
    ask_instrument(load_instrument_by_id("mini-ipip"), answers, prompter, lambda _: None)
    assert "Я душа компанії." in prompter.messages
    assert "Дуже точно" in prompter.messages
    assert any("не проходив психометричної валідації" in text for text in prompter.messages)
    assert not any(text.startswith("I Я") for text in prompter.messages)


@private_edition_only
def test_ukrainian_wellbeing_questions_and_response_labels() -> None:
    """The reported wellbeing screen uses Ukrainian wording and both response sets."""

    class CapturingPrompter(ScriptedPrompter):
        """Record the response labels as well as the prompt."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            self.messages.extend(label for _, label in choices)
            return super().select(message, choices)

    prompter = CapturingPrompter()
    ask_instrument(
        load_instrument_by_id("cbi-work"),
        Answers(questionnaire_language="uk"),
        prompter,
        lambda _: None,
    )
    assert _ukrainian_cbi_item(0) in prompter.messages
    assert "Дуже значною мірою" in prompter.messages
    assert "Завжди" in prompter.messages
    assert any("Думайте про свою роботу." in text for text in prompter.messages)
    assert any("Самопочуття: енергія на роботі" in text for text in prompter.messages)
    assert not any("Think about your work" in text for text in prompter.messages)


@private_edition_only
@pytest.mark.parametrize("instrument_id", ["gse", "onet-ip-sf"])
def test_untranslated_instruments_keep_source_wording(instrument_id: str) -> None:
    """Unverified translation permission produces an explicit English fallback."""
    instrument = load_instrument_by_id(instrument_id)
    with pytest.raises(ValueError, match="not supported"):
        translate_instrument(instrument, "uk")


def test_ukrainian_session_resumes_in_the_saved_language(tmp_path: Path) -> None:
    """Ctrl-C saves the language along with progress; no flag is needed on resume."""
    paths = Paths(tmp_path / "out", tmp_path / "home")
    with pytest.raises(SetupInterrupted):
        setup_interactive(
            paths, ScriptedPrompter(stop_after=6), link=False, questionnaire_language="uk"
        )
    resumed = load_answers(paths.answers)
    assert resumed.questionnaire_language == "uk"
    assert resumed.instruments["mini-ipip"]
    prompter = ScriptedPrompter(confirm=False)
    run_questionnaire(resumed, prompter, lambda current: save_answers(paths.answers, current))
    assert "Я відчуваю емоції інших людей." in prompter.messages
    assert "Я душа компанії." not in prompter.messages
    before = paths.answers.read_bytes()
    with pytest.raises(AnswersError, match="cannot change"):
        setup_interactive(paths, prompter, link=False, questionnaire_language="en")
    assert paths.answers.read_bytes() == before


@pytest.mark.parametrize("language", ["../../uk", "fr", "UK", [], None])
def test_answers_reject_invalid_languages(language: object) -> None:
    """A language is an allowlisted identifier, never a caller-selected path."""
    with pytest.raises((AnswersError, ValueError)):
        parse_answers({"questionnaire_language": language})


def test_old_answers_default_to_english() -> None:
    """Existing answers files need no migration and retain their administered language."""
    assert parse_answers({}).questionnaire_language == "en"


@pytest.mark.parametrize("via_settings", [False, True])
def test_cli_selects_ukrainian_for_new_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, via_settings: bool
) -> None:
    """The saved settings language and the scripting flag both select Ukrainian."""
    from persona_forge import cli
    from persona_forge.settings import Settings, save_settings

    monkeypatch.delenv("ANSWERS", raising=False)
    monkeypatch.delenv("QUESTIONNAIRE_LANGUAGE", raising=False)
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: ScriptedPrompter(confirm=False))
    out_dir = tmp_path / "out"
    arguments = ["setup", "--out", str(out_dir), "--no-link"]
    if via_settings:
        save_settings(out_dir, Settings(None, "uk"))
    else:
        arguments.extend(["--questionnaire-language", "uk"])
    assert cli.main(arguments) == 0
    assert load_answers(out_dir / "answers.json").questionnaire_language == "uk"
    assert "not psychometrically validated in Ukrainian" in (out_dir / "report.html").read_text()


def test_cli_does_not_relabel_existing_answer_files(tmp_path: Path) -> None:
    """A language flag cannot misrepresent how a non-interactive file was answered."""
    from persona_forge.cli import main

    source = tmp_path / "source.json"
    source.write_text(json.dumps(make_answers()))
    out_dir = tmp_path / "out"
    assert (
        main(
            [
                "setup",
                "--answers",
                str(source),
                "--out",
                str(out_dir),
                "--questionnaire-language",
                "uk",
                "--no-link",
            ]
        )
        == 1
    )
    assert not out_dir.exists()


def test_language_and_profile_variables_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Language and profile come from `make settings`, not from environment variables."""
    from persona_forge import cli

    monkeypatch.delenv("ANSWERS", raising=False)
    monkeypatch.setenv("QUESTIONNAIRE_LANGUAGE", "uk")
    monkeypatch.setenv("PROFILE", "someone")
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: ScriptedPrompter(confirm=False))
    out_dir = tmp_path / "out"
    assert cli.main(["setup", "--out", str(out_dir), "--no-link"]) == 0
    assert load_answers(out_dir / "answers.json").questionnaire_language == "en"
    assert not (out_dir / "profiles").exists()


def test_invalid_language_in_settings_fails_without_answers(tmp_path: Path) -> None:
    """A hand-edited settings file gets the same allowlist validation as the flag."""
    from persona_forge.cli import main

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "settings.json").write_text('{"language": "../../etc"}')
    assert main(["setup", "--out", str(out_dir), "--no-link"]) == 1
    assert not (out_dir / "answers.json").exists()


@pytest.mark.parametrize("mutation", ["item", "value", "extra_field", "identity"])
def test_incomplete_or_structural_overlays_are_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """Overlays must fully cover text and cannot inject scoring fields or unknown values."""
    from persona_forge import translations

    instrument = load_instrument_by_id("mini-ipip")
    raw = translations.read_json_file(
        translations.load_language("uk").instrument_dir / "mini-ipip.json"
    )
    if mutation == "item":
        raw["items"].popitem()
    elif mutation == "value":
        raw["response_sets"]["accuracy"]["999"] = "invalid"
    elif mutation == "extra_field":
        raw["reverse"] = True
    else:
        raw["instrument_id"] = "another-instrument"
    monkeypatch.setattr(translations, "read_json_file", lambda _: raw)
    with pytest.raises(ValueError):
        translate_instrument(instrument, "uk")


def test_report_records_translation_without_changing_agent_outputs(tmp_path: Path) -> None:
    """The private report discloses project wording; agent text remains in English."""
    original = make_answers()
    source = tmp_path / "source.json"
    source.write_text(json.dumps(original))
    english_paths = Paths(tmp_path / "en", tmp_path / "home")
    setup_non_interactive(source, english_paths, link=False)
    original["questionnaire_language"] = "uk"
    source.write_text(json.dumps(original))
    ukrainian_paths = Paths(tmp_path / "uk", tmp_path / "home")
    setup_non_interactive(source, ukrainian_paths, link=False)
    report = (ukrainian_paths.out_dir / "report.html").read_text()
    assert "not psychometrically validated in Ukrainian" in report
    assert "GSE and O*NET" in report
    for directory in ("claude", "codex"):
        for path in (english_paths.out_dir / directory).rglob("*"):
            if path.is_file():
                relative = path.relative_to(english_paths.out_dir)
                assert path.read_bytes() == (ukrainian_paths.out_dir / relative).read_bytes()


@private_edition_only
def test_ukrainian_wellbeing_resumes_without_switching_languages(tmp_path: Path) -> None:
    """A newly translated wellbeing session stays Ukrainian after saving its first item."""
    path = tmp_path / "answers.json"
    answers = Answers(questionnaire_language="uk")
    with pytest.raises(SetupInterrupted):
        ask_instrument(
            load_instrument_by_id("cbi-work"),
            answers,
            ScriptedPrompter(stop_after=1),
            lambda current: save_answers(path, current),
        )
    resumed = load_answers(path)
    assert resumed.instrument_languages["cbi-work"] == "uk"
    prompter = ScriptedPrompter()
    ask_instrument(load_instrument_by_id("cbi-work"), resumed, prompter, lambda _: None)
    assert _ukrainian_cbi_item(1) in prompter.messages
    assert _ukrainian_cbi_item(0) not in prompter.messages


def test_old_english_wellbeing_answers_do_not_silently_switch_to_ukrainian() -> None:
    """Old Ukrainian sessions actually administered CBI in English before this fix."""
    answers = parse_answers(
        {
            "questionnaire_language": "uk",
            "instruments": {"cbi-work": {"cbi-work-1": 100}},
        }
    )
    assert answers.instrument_languages["cbi-work"] == "en"
    prompter = ScriptedPrompter()
    ask_instrument(load_instrument_by_id("cbi-work"), answers, prompter, lambda _: None)
    assert "Do you feel burnt out because of your work?" in prompter.messages
    assert any("як і попередні відповіді" in text for text in prompter.messages)


@pytest.mark.parametrize("languages", [{"cbi-work": "../../uk"}, {"unknown": "uk"}])
def test_invalid_instrument_language_records_are_rejected(languages: dict[str, str]) -> None:
    """Recorded languages cannot select paths or refer to instruments absent from answers."""
    with pytest.raises(ValueError):
        parse_answers({"instruments": {"cbi-work": {}}, "instrument_languages": languages})
