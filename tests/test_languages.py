"""Data-only language plugins, complete localized flows and rejected unsafe packs."""

import json
import shutil
from pathlib import Path

import pytest
from helpers import private_edition_only
from test_questionnaire import ScriptedPrompter

from persona_forge.answers import Answers, load_answers, save_answers
from persona_forge.cli import main
from persona_forge.content import load_preferences
from persona_forge.flow import DEPTHS, ROLES, SENIORITY, depth_instruments, wellbeing_instruments
from persona_forge.languages import LANGUAGE_DIR, available_languages, load_language
from persona_forge.setup import Paths, setup_interactive


def _write(path: Path, value: object) -> None:
    """Write a test plugin resource as UTF-8 JSON."""
    path.write_text(json.dumps(value, ensure_ascii=False))


@pytest.fixture
def plugin_root(tmp_path: Path) -> Path:
    """Copy packs to an isolated directory for mutation and discovery tests."""
    root = tmp_path / "languages"
    shutil.copytree(LANGUAGE_DIR, root)
    return root


@pytest.mark.parametrize("depth", list(DEPTHS))
@pytest.mark.parametrize("role", list(ROLES))
def test_every_ukrainian_role_and_depth_completes_without_english_ui(
    tmp_path: Path, depth: str, role: str
) -> None:
    """Exercise all scenario banks, review statements, choices and optional wellbeing."""

    class UkrainianFlow(ScriptedPrompter):
        """Capture every displayed label, and include the wellbeing module."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            self.messages.extend(label for _, label in choices)
            return super().select(message, choices)

        def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]:
            self.messages.extend(label for _, label in choices)
            return super().checkbox(message, choices)

        def confirm(self, message: str, default: bool) -> bool:
            if message == "Пройти необов'язкову перевірку самопочуття?":
                return True
            return super().confirm(message, default)

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
            questionnaire_language="uk",
        ),
    )
    prompter = UkrainianFlow(confirm=False)
    setup_interactive(paths, prompter, link=False)
    completed = load_answers(paths.answers)
    assert completed.review_done and completed.egos["done"]
    assert bool(completed.wellbeing_opt_in) == bool(wellbeing_instruments("uk"))
    assert set(completed.instrument_languages.values()) == {"uk"}
    assert not {"gse", "onet-ip-sf"} & set(completed.instruments)
    # Exact English UI messages must not survive inside any rendered screen either.
    pack = load_language("uk")
    untranslated = [
        source
        for source, target in pack.messages.items()
        if source != target and len(source) >= 20 and "{" not in source
    ]
    for message in prompter.messages:
        assert not any(source in message for source in untranslated), message


def test_ukrainian_initial_consent_and_options_are_localized(tmp_path: Path) -> None:
    """Reproduce the screenshot's first screen, with a language-only Ukrainian setup."""
    prompter = ScriptedPrompter(confirm=False)
    setup_interactive(
        Paths(tmp_path / "out", tmp_path / "home"),
        prompter,
        link=False,
        questionnaire_language="uk",
    )
    assert any("Приватність і згода" in message for message in prompter.messages)
    assert "Я розумію й хочу продовжити." in prompter.messages
    assert "Ваше ім'я або псевдонім:" in prompter.messages
    assert not any("Privacy and consent" in message for message in prompter.messages)


def test_all_authored_content_and_metadata_has_coverage() -> None:
    """Require translations even for review bands and choices not selected in flow tests."""
    from persona_forge.egos import CUSTOM_DIMENSIONS, load_presets
    from persona_forge.files import DATA_DIR, read_json_file
    from persona_forge.insights import load_rules, load_strength_texts

    pack = load_language("uk")
    sources = (
        list(ROLES.values()) + list(SENIORITY.values()) + [depth.title for depth in DEPTHS.values()]
    )
    sources += [rule.statement for rule in load_rules()]
    via, _ = load_strength_texts()
    sources += [entry.label for entry in via.values()]
    for preference in load_preferences():
        sources += [preference.question, *(option.label for option in preference.options)]
    for ego in load_presets().values():
        sources += [ego.name, ego.description]
    for spec in CUSTOM_DIMENSIONS.values():
        sources += [spec["question"], *(option[0] for option in spec["options"].values())]
    for path in (DATA_DIR / "sjt").glob("*.json"):
        for scenario in read_json_file(path).get("scenarios", []):
            sources += [
                scenario["title"],
                scenario["prompt"],
                *(option["text"] for option in scenario["options"]),
            ]
    # Check for an entry rather than different text: IT terms such as "Junior" or
    # "Scope creep" stay in English on purpose.
    missing = [source for source in sources if not pack.messages.get(source)]
    assert missing == []


def test_new_plugin_is_discovered_without_python_registration(plugin_root: Path) -> None:
    """A synthetic third locale requires only a new folder, manifest and data files."""
    folder = plugin_root / "fr"
    folder.mkdir()
    _write(
        folder / "manifest.json",
        {
            "schema_version": 1,
            "code": "fr",
            "name": "Français",
            "status": "complete",
            "instrument_ids": ["mini-ipip"],
        },
    )
    messages = json.loads((plugin_root / "en" / "messages.json").read_text())
    messages["Privacy and consent"] = "Confidentialité et consentement"
    _write(folder / "messages.json", messages)
    (folder / "instruments").mkdir()
    overlay = json.loads((plugin_root / "uk" / "instruments" / "mini-ipip.json").read_text())
    overlay["language"] = "fr"  # Synthetic coverage fixture, not a real French translation.
    _write(folder / "instruments" / "mini-ipip.json", overlay)
    (folder / "__init__.py").write_text("raise AssertionError('plugin code must never execute')")
    assert available_languages(plugin_root) == ("en", "fr", "uk")
    assert (
        load_language("fr", plugin_root).text("Privacy and consent")
        == "Confidentialité et consentement"
    )


@pytest.mark.parametrize(
    "mutation", ["missing", "placeholder", "control", "scoring", "item", "unknown_instrument"]
)
def test_incomplete_or_unsafe_plugins_are_rejected(plugin_root: Path, mutation: str) -> None:
    """Reject missing coverage, bad substitutions, terminal controls and scoring changes."""
    folder = plugin_root / "uk"
    messages = json.loads((folder / "messages.json").read_text())
    if mutation == "missing":
        messages.pop("Privacy and consent")
    elif mutation == "placeholder":
        messages["Your role:"] = "{secret.__class__}"
    elif mutation == "control":
        messages["Your role:"] = "\x1b[2J"
    elif mutation in {"scoring", "item"}:
        path = folder / "instruments" / "mini-ipip.json"
        overlay = json.loads(path.read_text())
        if mutation == "scoring":
            overlay["reverse"] = True
        else:
            overlay["items"].popitem()
        _write(path, overlay)
    else:
        path = folder / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["instrument_ids"].append("unknown")
        _write(path, manifest)
    _write(folder / "messages.json", messages)
    with pytest.raises(ValueError):
        load_language("uk", plugin_root)


def test_draft_packs_are_not_selectable(plugin_root: Path) -> None:
    """Contributors can work on a draft without enabling it in setup."""
    path = plugin_root / "uk" / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["status"] = "draft"
    _write(path, manifest)
    assert available_languages(plugin_root) == ("en",)
    with pytest.raises(ValueError, match="not complete"):
        load_language("uk", plugin_root)


@pytest.mark.parametrize("resource", ["messages.json", "instruments/mini-ipip.json"])
def test_symlinked_plugin_resources_are_rejected(plugin_root: Path, resource: str) -> None:
    """Refuse catalog and instrument redirects outside a plugin's resources."""
    path = plugin_root / "uk" / resource
    target = plugin_root / "saved-resource.json"
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(ValueError, match="symlinks"):
        load_language("uk", plugin_root)


@pytest.mark.parametrize("code", ["../uk", "/uk", "uk/../../en"])
def test_language_codes_cannot_escape_plugin_root(plugin_root: Path, code: str) -> None:
    """Reject path traversal before reading plugin resources."""
    with pytest.raises(ValueError, match="invalid language code"):
        load_language(code, plugin_root)


def test_no_missing_message_can_silently_fall_back_to_english() -> None:
    """New UI text requires an explicit translation rather than a mixed-language screen."""
    with pytest.raises(ValueError, match="missing uk UI translation"):
        load_language("uk").text("A brand new English prompt with no translation")
    with pytest.raises(ValueError, match="missing uk UI translation"):
        load_language("uk").text("A new scenario full of untranslated words")


def test_polish_tool_names_and_errors_are_translated() -> None:
    """The polish tool picker and its failure reasons render in Ukrainian without crashing."""
    pack = load_language("uk")
    assert pack.text("claude") == "claude"
    assert pack.text("codex") == "codex"
    assert (
        pack.text(
            "Polish skipped: {error}. The template wording is kept.",
            error="claude did not finish: timed out",
        )
        == "Покращення пропущено: claude не завершив роботу: timed out. Збережено початковий текст."
    )
    assert pack.text("codex exited with status 2") == "codex завершився з кодом 2"


@private_edition_only
def test_language_capabilities_keep_english_only_modules_out_of_ukrainian() -> None:
    """Depths remain useful while showing only fully translated instruments."""
    assert {instrument.id for instrument in depth_instruments("standard", "uk")} == {
        "ipip-neo-120",
        "ncs-6",
    }
    assert "gse" in {instrument.id for instrument in depth_instruments("standard", "en")}
    assert "onet-ip-sf" not in {instrument.id for instrument in depth_instruments("deep", "uk")}


@private_edition_only
def test_languages_command_validates_the_installed_plugins(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The contributor check exercises UI coverage and complete instrument overlays."""
    assert main(["languages"]) == 0
    assert "en: English (8)" in caplog.text
    assert "uk: Українська (6)" in caplog.text


@pytest.mark.parametrize("language", ["en", "uk"])
def test_new_setup_asks_language_first_and_preserves_it_on_resume(
    tmp_path: Path, language: str
) -> None:
    """Choose a language before consent and retain it when setup resumes."""
    from persona_forge.questionnaire import SetupInterrupted

    class ChooseLanguage(ScriptedPrompter):
        """Choose the requested pack, then stop before answering anything else."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if message == "Choose your language:":
                assert not self.messages
                assert dict(choices) == {
                    code: load_language(code).name for code in available_languages()
                }
                self.messages.append(message)
                return language
            raise SetupInterrupted

    paths = Paths(tmp_path / "out", tmp_path / "home")
    prompter = ChooseLanguage()
    with pytest.raises(SetupInterrupted):
        setup_interactive(paths, prompter, link=False)
    assert prompter.messages[0] == "Choose your language:"
    assert load_answers(paths.answers).questionnaire_language == language
    consent = load_language(language).text("I understand and want to continue.")
    assert consent in prompter.messages

    resumed = ScriptedPrompter(stop_after=0)
    with pytest.raises(SetupInterrupted):
        setup_interactive(paths, resumed, link=False)
    assert "Choose your language:" not in resumed.messages
    assert load_answers(paths.answers).questionnaire_language == language
