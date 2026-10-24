"""Overall progress and explicit pause/resume behavior through the interactive setup."""

from pathlib import Path

import pytest
from helpers import private_edition_only
from test_questionnaire import ScriptedPrompter

from persona_forge.answers import Answers, load_answers, save_answers
from persona_forge.instruments import load_instrument_by_id
from persona_forge.questionnaire import QuestionaryPrompter, ask_instrument
from persona_forge.session_ui import PAUSE_ACTION, SessionPrompter, SetupPaused
from persona_forge.setup import Paths, setup_interactive


def test_overall_count_includes_all_sections_and_optional_wellbeing() -> None:
    """Overall progress covers personality, scenarios, preferences, hints and consent."""
    answers = Answers(depth="quick", role="software-engineer")
    session = SessionPrompter(ScriptedPrompter(), answers, lambda _: None)
    assert "0/44 answered (0%)" in session.progress_text()
    instrument = load_instrument_by_id("mini-ipip")
    answers.instruments[instrument.id] = {item.id: 1 for item in instrument.items}
    assert "20/44 answered (45%)" in session.progress_text()
    answers.wellbeing_opt_in = True
    assert "21/51 answered (41%)" in session.progress_text()
    assert "may add" not in session.progress_text()
    answers.wellbeing_opt_in = False
    assert "21/44 answered (47%)" in session.progress_text()


def test_setup_stages_do_not_claim_questionnaire_is_all_of_setup() -> None:
    """Review and persona configuration have visible stages after the questionnaire."""
    answers = Answers()
    session = SessionPrompter(ScriptedPrompter(), answers, lambda _: None)
    session.stage = "review"
    session.review_total = 12
    answers.review = {"one": "yes", "two": "no"}
    assert session.progress_text() == "Setup 2/4: profile review | 2/12 statements reviewed"
    session.stage = "personas"
    assert session.progress_text() == "Setup 3/4: personas"
    session.stage = "generate"
    assert session.progress_text() == "Setup 4/4: generate files"


def test_explicit_pause_saves_without_recording_an_answer_and_resume_skips_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pause menu exits successfully; resuming continues at the next unanswered item."""
    from persona_forge import cli

    class PauseAfterThree(ScriptedPrompter):
        """Answer three instrument questions, then choose the control action."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if message.startswith("I "):
                if self.selects >= 7:  # Language, three initial choices, then three item answers.
                    assert any(value == PAUSE_ACTION for value, _ in choices)
                    return PAUSE_ACTION
            return super().select(message, choices)

    monkeypatch.delenv("ANSWERS", raising=False)
    monkeypatch.delenv("QUESTIONNAIRE_LANGUAGE", raising=False)
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: PauseAfterThree(confirm=False))
    paths = Paths(tmp_path / "out", tmp_path / "home")
    assert cli.main(["setup", "--out", str(paths.out_dir), "--no-link"]) == 0
    answers = load_answers(paths.answers)
    assert len(answers.instruments["mini-ipip"]) == 3
    assert PAUSE_ACTION not in paths.answers.read_text()
    assert not (paths.out_dir / "report.html").exists()
    resumed = ScriptedPrompter(confirm=False)
    setup_interactive(paths, resumed, link=False)
    assert not any(message == "I am the life of the party." for message in resumed.messages)
    assert "I have frequent mood swings." in resumed.messages
    assert any("3/44 answered" in text for text in resumed.messages)
    assert load_answers(paths.answers).review_done


def test_section_break_can_pause_before_starting_the_next_section(tmp_path: Path) -> None:
    """Completing an instrument offers a break before any scenario is asked."""

    class PauseBetweenSections(ScriptedPrompter):
        """Stop at the first between-section menu."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if message.startswith("Section complete"):
                return PAUSE_ACTION
            return super().select(message, choices)

    paths = Paths(tmp_path / "out", tmp_path / "home")
    with pytest.raises(SetupPaused):
        setup_interactive(paths, PauseBetweenSections(confirm=False), link=False)
    answers = load_answers(paths.answers)
    assert len(answers.instruments["mini-ipip"]) == 20
    assert answers.sjt == {}


@private_edition_only
def test_checkbox_pause_does_not_submit_a_partial_block(tmp_path: Path) -> None:
    """Pause is a control, including when checked alongside an activity."""

    class CheckboxPause(ScriptedPrompter):
        """Check an activity and pause together."""

        def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]:
            return [choices[0][0], PAUSE_ACTION]

    answers = Answers(depth="deep", role="software-engineer")
    path = tmp_path / "answers.json"
    session = SessionPrompter(CheckboxPause(), answers, lambda current: save_answers(path, current))
    with pytest.raises(SetupPaused):
        ask_instrument(load_instrument_by_id("onet-ip-sf"), answers, session, lambda _: None)
    assert load_answers(path).instruments["onet-ip-sf"] == {}


def test_ctrl_c_is_a_successful_pause_in_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stopping no longer makes make report an error; the saved session remains usable."""
    from persona_forge import cli

    monkeypatch.delenv("ANSWERS", raising=False)
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: ScriptedPrompter(stop_after=5))
    out = tmp_path / "out"
    assert cli.main(["setup", "--out", str(out), "--no-link"]) == 0
    assert load_answers(out / "answers.json").instruments


def test_ukrainian_pause_and_progress_labels() -> None:
    """New controls follow the selected language without changing the instrument text."""

    class UkrainianPause(ScriptedPrompter):
        """Select the Ukrainian pause action."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            assert (PAUSE_ACTION, "Зробити паузу й продовжити пізніше") in choices
            return PAUSE_ACTION

    answers = Answers(questionnaire_language="uk", depth="quick", role="software-engineer")
    session = SessionPrompter(UkrainianPause(), answers, lambda _: None)
    assert "Загалом" in session.progress_text()
    with pytest.raises(SetupPaused):
        session.select("Your role:", [("1", "Software engineer")])


def test_real_questionary_menu_accepts_pause_from_keyboard() -> None:
    """Exercise the actual terminal menu: the P key pauses, without a real TTY."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    saved = []
    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        keyboard.send_text("p")
        session = SessionPrompter(QuestionaryPrompter(), Answers(), lambda _: saved.append(True))
        with pytest.raises(SetupPaused):
            session.select("Choose an answer or pause:", [("answer", "Answer")])
    assert saved == [True]


def test_optional_known_results_resume_without_reasking_skipped_questions(tmp_path: Path) -> None:
    """Even an explicitly blank optional answer is saved and counted before pausing."""
    from persona_forge.questionnaire import SetupInterrupted, ask_known_results

    class StopOnSecondText(ScriptedPrompter):
        """Submit a blank result, then interrupt the next text prompt."""

        def __init__(self) -> None:
            super().__init__()
            self.text_count = 0

        def text(self, message: str, limit: int) -> str:
            self.text_count += 1
            if self.text_count == 2:
                raise SetupInterrupted
            return ""

    path = tmp_path / "answers.json"
    answers = Answers(depth="quick", role="software-engineer")
    prompter = StopOnSecondText()
    with pytest.raises(SetupInterrupted):
        ask_known_results(answers, prompter, lambda current: save_answers(path, current))
    resumed = load_answers(path)
    assert resumed.known_results == {"sixteen_personalities": ""}
    ui = SessionPrompter(ScriptedPrompter(), resumed, lambda _: None)
    assert "1/44 answered" in ui.progress_text()
    remaining = ScriptedPrompter()
    ask_known_results(resumed, remaining, lambda _: None)
    assert not any("16Personalities type" in text for text in remaining.messages)


def test_custom_persona_draft_resumes_at_the_next_dimension(tmp_path: Path) -> None:
    """Pause preserves earlier persona choices and the completed part of a custom persona."""
    from helpers import make_answers

    from persona_forge.answers import parse_answers
    from persona_forge.egos import validate_ego_choices
    from persona_forge.profile import build_profile
    from persona_forge.setup import run_ego_step

    class CraftThenPause(ScriptedPrompter):
        """Start one custom persona and pause after answering its purpose."""

        def confirm(self, message: str, default: bool) -> bool:
            return message.startswith("Craft a custom")

        def text(self, message: str, limit: int) -> str:
            return "Navigator"

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if "blunt" in message:
                return PAUSE_ACTION
            return super().select(message, choices)

    answers = parse_answers(make_answers())
    answers.egos = None
    path = tmp_path / "answers.json"

    def save(current: Answers) -> None:
        """Persist accepted persona choices and the unfinished draft."""
        save_answers(path, current)

    session = SessionPrompter(CraftThenPause(), answers, save)
    session.stage = "personas"
    with pytest.raises(SetupPaused):
        run_ego_step(answers, build_profile(answers), session, save)
    resumed = load_answers(path)
    validate_ego_choices(resumed.egos)
    assert resumed.egos["custom_draft"] == {"name": "Navigator", "purpose": "review"}
    prompter = ScriptedPrompter(confirm=False)
    run_ego_step(resumed, build_profile(resumed), prompter, save)
    assert "Pick presets (space to toggle):" not in prompter.messages
    assert "What is this ego for?" not in prompter.messages
    assert "How blunt should it be?" in prompter.messages
    assert resumed.egos["done"] and "custom_draft" not in resumed.egos


@pytest.mark.parametrize(
    "draft",
    [
        {"name": "Navigator", "purpose": "execute-shell"},
        {"name": "Navigator", "unknown": "value"},
        {"name": "\x1bNavigator"},
    ],
)
def test_custom_persona_drafts_are_strictly_validated(draft: dict[str, str]) -> None:
    """Saving partial progress does not permit unknown fields, values or control characters."""
    from persona_forge.answers import AnswersError
    from persona_forge.egos import validate_ego_choices

    with pytest.raises(AnswersError):
        validate_ego_choices({"done": False, "custom_draft": draft})


@pytest.mark.parametrize("keys, direction", [("\x1b[C", 1), ("\x1b[D", -1)])
def test_horizontal_arrows_move_questions_without_submitting(keys: str, direction: int) -> None:
    """Horizontal keys navigate immediately, rather than changing the highlighted answer."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from persona_forge.navigation import QuestionMoved, QuestionNavigation

    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        keyboard.send_text(keys)
        terminal = QuestionaryPrompter()
        navigation = QuestionNavigation([("a", True), ("b", False)])
        terminal.question_navigation(navigation, "b")
        with pytest.raises(QuestionMoved) as raised:
            terminal.select("Choose", [("a", "A"), ("b", "B")])
        assert raised.value.direction == direction


@pytest.mark.parametrize("confirmed", [True, False])
def test_start_over_preserves_answers_and_restarts_only_when_confirmed(
    tmp_path: Path, confirmed: bool
) -> None:
    """Restart archives the session; declining keeps the original answers active."""
    from persona_forge.session_ui import RESTART_ACTION

    class RestartThenPause(ScriptedPrompter):
        """Request one restart and pause at the next choice."""

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if message == "Choose your language:":
                return "en"
            self.selects += 1
            assert choices[-2][0] == PAUSE_ACTION
            assert choices[-1][0] == RESTART_ACTION
            return RESTART_ACTION if self.selects == 1 else PAUSE_ACTION

    paths = Paths(tmp_path / "out", tmp_path / "home")
    original = Answers(name="Original", depth="quick", role="software-engineer")
    save_answers(paths.answers, original)
    with pytest.raises(SetupPaused):
        setup_interactive(paths, RestartThenPause(confirm=confirmed), link=False)
    backups = list(paths.out_dir.glob("backups/session-*/answers.json"))
    if confirmed:
        assert len(backups) == 1
        assert load_answers(backups[0]).name == "Original"
        assert load_answers(paths.answers).name != "Original"
    else:
        assert not backups
        assert load_answers(paths.answers).name == "Original"


def test_checkbox_restart_does_not_record_partial_selection() -> None:
    """Restart is a control even when an answer is checked alongside it."""
    from persona_forge.session_ui import RESTART_ACTION, SetupRestarted

    class RestartCheckbox(ScriptedPrompter):
        """Choose both a regular answer and restart."""

        def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]:
            return [choices[0][0], RESTART_ACTION]

    answers = Answers()
    session = SessionPrompter(RestartCheckbox(), answers, lambda _: None)
    with pytest.raises(SetupRestarted):
        session.checkbox("Choose", [("a", "A")])
    assert answers.egos is None
