"""Interactive flow with scripted prompts: order, saving, resuming and review."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from persona_forge.answers import Answers, load_answers, save_answers
from persona_forge.flow import DEPTHS, depth_instruments, depth_scenarios, estimated_minutes
from persona_forge.instruments import load_instrument_by_id
from persona_forge.permissions import instrument_installed
from persona_forge.questionnaire import (
    SetupInterrupted,
    display_text,
    missing_questionnaire_parts,
    run_questionnaire,
)
from persona_forge.setup import Paths, setup_interactive


class ScriptedPrompter:
    """Answers prompts automatically: the first choice, fixed text, a set confirm value.

    `stop_after` raises SetupInterrupted after that many select calls, like Ctrl-C.
    """

    def __init__(self, confirm: bool = True, stop_after: int | None = None) -> None:
        self.confirm_value = confirm
        self.stop_after = stop_after
        self.selects = 0
        self.messages: list[str] = []

    def start_session(self) -> None:
        """Scripted prompts have no terminal history to clear."""

    def show(self, text: str) -> None:
        self.messages.append(text)

    def screen(self, header: str, body: str) -> None:
        self.messages.append(f"{header}\n{body}")

    def pause(self, message: str) -> None:
        self.messages.append(message)

    def select(self, message: str, choices: Sequence[tuple[str, str]]) -> str:
        if self.stop_after is not None and self.selects >= self.stop_after:
            raise SetupInterrupted
        self.selects += 1
        self.messages.append(message)
        return choices[0][0]

    def checkbox(self, message: str, choices: Sequence[tuple[str, str]]) -> list[str]:
        self.messages.append(message)
        return [choices[0][0]]

    def text(self, message: str, limit: int) -> str:
        self.messages.append(message)
        # Name prompts in every installed pack: English, Ukrainian, French, Dutch.
        keywords = ("name", "ім'я", "назва", "nom", "naam")
        return "Tester" if any(word in message.lower() for word in keywords) else ""

    def confirm(self, message: str, default: bool) -> bool:
        self.messages.append(message)
        if message.startswith(("I understand", "Я розумію")):
            return True
        if message.startswith(
            ("Craft a custom ego", "Polish", "Створити власну", "Покращити формулювання")
        ):
            return False
        return self.confirm_value


def test_quick_questionnaire_completes_and_saves(tmp_path: Path) -> None:
    """Every answer is saved, and the result is complete for the Quick depth."""
    saved: list[int] = []
    answers = Answers()
    prompter = ScriptedPrompter(confirm=False)

    def save(current: Answers) -> None:
        saved.append(1)

    # The first depth choice is Quick; the first role is software engineer.
    run_questionnaire(answers, prompter, save)
    assert answers.depth == "quick" and answers.role == "software-engineer"
    assert missing_questionnaire_parts(answers) == []
    items = sum(len(instrument.items) for instrument in depth_instruments("quick"))
    scenarios = len(depth_scenarios("quick", "software-engineer"))
    assert len(saved) >= items + scenarios
    assert answers.wellbeing_opt_in is False


def test_interrupted_questionnaire_resumes_where_it_stopped(tmp_path: Path) -> None:
    """Ctrl-C keeps saved progress; the next run asks only what is missing."""
    path = tmp_path / "answers.json"
    answers = Answers()

    def save(current: Answers) -> None:
        save_answers(path, current)

    with pytest.raises(SetupInterrupted):
        run_questionnaire(answers, ScriptedPrompter(stop_after=10), save)
    resumed = load_answers(path)
    answered_before = len(resumed.instruments.get("mini-ipip", {}))
    assert answered_before > 0
    prompter = ScriptedPrompter(confirm=False)
    run_questionnaire(resumed, prompter, save)
    assert missing_questionnaire_parts(resumed) == []
    first_item = depth_instruments("quick")[0].items[0].text
    assert not any(first_item in message for message in prompter.messages)


def test_full_interactive_setup_reviews_and_generates(tmp_path: Path) -> None:
    """The interactive path reviews every statement and writes linked outputs."""
    paths = Paths(tmp_path / "out", tmp_path / "home")
    outputs = setup_interactive(paths, ScriptedPrompter(confirm=False))
    answers = load_answers(paths.answers)
    assert answers.review_done and answers.egos and answers.egos["done"]
    assert set(answers.review) == {statement.id for statement in outputs.profile.statements}
    assert outputs.unreviewed == 0
    assert (paths.home / ".claude" / "rules" / "persona-forge-profile.md").is_symlink()


def test_depth_estimates_are_reported_honestly() -> None:
    """Estimates come from item counts, so Deep is far longer than Quick."""
    quick = estimated_minutes("quick", 11)
    standard = estimated_minutes("standard", 11)
    deep = estimated_minutes("deep", 11)
    assert quick < standard < deep
    assert set(DEPTHS) == {"quick", "standard", "deep"}


def test_ipip_items_are_shown_in_first_person_without_other_changes() -> None:
    """Only "I " is added (IPIP allows wording edits); the rest of each item is verbatim."""
    prompter = ScriptedPrompter(confirm=False)
    run_questionnaire(Answers(), prompter, lambda current: None)
    for item in depth_instruments("quick")[0].items:
        shown = f"I {item.text[0].lower()}{item.text[1:]}"
        assert shown in prompter.messages
    assert display_text("mini-ipip", "Am the life of the party.") == "I am the life of the party."
    assert display_text("mini-ipip", "Don't talk a lot.") == "I don't talk a lot."


def test_non_ipip_items_are_never_reworded() -> None:
    """GSE, NCS-6, O*NET and CBI items are shown exactly as published."""
    for instrument_id in ("gse", "ncs-6", "onet-ip-sf", "cbi-work"):
        if not instrument_installed(instrument_id):
            continue  # left out of the public edition
        for item in load_instrument_by_id(instrument_id).items:
            assert display_text(instrument_id, item.text) == item.text


def test_progress_header() -> None:
    """The header shows the module, a ten-step bar and the position."""
    from persona_forge.questionnaire import progress_header

    assert progress_header("Personality", 1, 20) == "Personality   [----------]  1 of 20"
    assert progress_header("Personality", 11, 20) == "Personality   [#####-----]  11 of 20"
