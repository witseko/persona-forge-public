"""Editing individual saved questions preserves other answers and supports resume."""

from copy import deepcopy
from pathlib import Path

import pytest
from helpers import make_answers
from test_questionnaire import ScriptedPrompter

from persona_forge.answers import Answers, load_answers, parse_answers, save_answers
from persona_forge.navigation import BACK_ACTION, NEXT_ACTION, QuestionNavigation
from persona_forge.questionnaire import QuestionaryPrompter, run_navigable_questions
from persona_forge.session_ui import PAUSE_ACTION, SessionPrompter, SetupPaused


def test_edit_one_answer_across_sections_preserves_other_answers(tmp_path: Path) -> None:
    """Navigate from completed work preferences into scenarios and edit only one answer."""
    answers = parse_answers(make_answers())
    original = deepcopy(answers)
    path = tmp_path / "answers.json"

    class EditOne(ScriptedPrompter):
        """Walk back across sections, edit one scenario, and walk forward again."""

        def __init__(self) -> None:
            super().__init__(confirm=False)
            self.navigation = None
            self.changed = False
            self.target = next(reversed(answers.sjt))

        def question_navigation(
            self, navigation: QuestionNavigation | None, default: object
        ) -> None:
            """Observe the presented question without altering saved values."""
            self.navigation = navigation

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if self.navigation is None:
                return super().select(message, choices)
            if message == "Review answers or continue:":
                return "continue" if self.changed else BACK_ACTION
            key = self.navigation.keys[self.navigation.position]
            if key == f"sjt:{self.target}" and not self.changed:
                self.changed = True
                return next(value for value, _ in choices if value != answers.sjt[self.target])
            return NEXT_ACTION if self.changed else BACK_ACTION

    ui = EditOne()

    def save(current: Answers) -> None:
        """Persist the current session for resume checks."""
        save_answers(path, current)

    run_navigable_questions(answers, SessionPrompter(ui, answers, save), save)
    assert ui.changed
    saved = load_answers(path)
    assert saved.instruments == original.instruments
    assert saved.preferences == original.preferences
    assert saved.known_results == original.known_results
    assert saved.sjt[ui.target] != original.sjt[ui.target]
    assert {key: value for key, value in saved.sjt.items() if key != ui.target} == {
        key: value for key, value in original.sjt.items() if key != ui.target
    }
    assert saved.review == {} and not saved.review_done
    assert saved.egos == original.egos


def test_skipping_an_unanswered_question_returns_to_it_before_completion(tmp_path: Path) -> None:
    """Next never manufactures an answer, and completion returns to the first gap."""
    answers = parse_answers(make_answers())
    instrument = next(iter(answers.instruments))
    item = next(iter(answers.instruments[instrument]))
    del answers.instruments[instrument][item]
    path = tmp_path / "answers.json"

    class SkipThenPause(ScriptedPrompter):
        """Skip the gap, pass saved answers, then pause when the gap appears again."""

        def __init__(self) -> None:
            super().__init__(confirm=False)
            self.navigation = None
            self.visits = 0

        def question_navigation(
            self, navigation: QuestionNavigation | None, default: object
        ) -> None:
            """Track navigation context for scripted control choices."""
            self.navigation = navigation

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if self.navigation is None or message == "Review answers or continue:":
                return super().select(message, choices)
            if self.navigation.keys[self.navigation.position] == f"{instrument}:{item}":
                self.visits += 1
                if self.visits == 2:
                    return PAUSE_ACTION
            return NEXT_ACTION

    ui = SkipThenPause()

    def save(current: Answers) -> None:
        """Persist the current session for resume checks."""
        save_answers(path, current)

    with pytest.raises(SetupPaused):
        run_navigable_questions(answers, SessionPrompter(ui, answers, save), save)
    assert ui.visits == 2
    assert item not in load_answers(path).instruments[instrument]


@pytest.mark.parametrize("checkbox", [False, True])
def test_saved_selection_is_restored_on_revisit(checkbox: bool) -> None:
    """Pressing Enter on an unchanged revisited question preserves its saved selection."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        keyboard.send_text("\r")
        terminal = QuestionaryPrompter()
        terminal.question_navigation(
            QuestionNavigation([("question", False)]), ["b"] if checkbox else "b"
        )
        choices = [("a", "A"), ("b", "B")]
        result = (
            terminal.checkbox("Choose", choices) if checkbox else terminal.select("Choose", choices)
        )
        assert result == (["b"] if checkbox else "b")


def test_resume_go_back_edit_and_pause_preserves_later_answers(tmp_path: Path) -> None:
    """Resume at the first gap, move back twice, and change just the selected item."""
    answers = parse_answers(make_answers(depth="quick"))
    responses = answers.instruments["mini-ipip"]
    items = list(responses)
    del responses[items[3]]
    original = dict(responses)
    path = tmp_path / "answers.json"

    class EditEarlier(ScriptedPrompter):
        """Move back to item two, edit it, then pause on item three."""

        def __init__(self) -> None:
            super().__init__(confirm=False)
            self.navigation = None
            self.actions = iter(
                [BACK_ACTION, BACK_ACTION, str(6 - responses[items[1]]), PAUSE_ACTION]
            )

        def question_navigation(
            self, navigation: QuestionNavigation | None, default: object
        ) -> None:
            """Track active question prompts."""
            self.navigation = navigation

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if self.navigation is not None:
                return next(self.actions)
            return super().select(message, choices)

    def save(current: Answers) -> None:
        """Persist the current session for resume checks."""
        save_answers(path, current)

    with pytest.raises(SetupPaused):
        run_navigable_questions(answers, SessionPrompter(EditEarlier(), answers, save), save)
    saved = load_answers(path).instruments["mini-ipip"]
    assert saved[items[1]] == 6 - original[items[1]]
    assert {key: value for key, value in saved.items() if key != items[1]} == {
        key: value for key, value in original.items() if key != items[1]
    }


@pytest.mark.parametrize("keys", ["\x1b[D\r", "\r"])
def test_first_question_left_does_not_exit_or_change_answer(keys: str) -> None:
    """The first question has no previous question; Enter still saves normally."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        keyboard.send_text(keys)
        terminal = QuestionaryPrompter()
        terminal.question_navigation(QuestionNavigation([("question", False)]), "b")
        assert terminal.select("Choose", [("a", "A"), ("b", "B")]) == "b"


def test_browsing_unchanged_optional_answers_keeps_review() -> None:
    """Back and Next work in optional wellbeing items without invalidating saved review."""
    answers = parse_answers(make_answers(depth="quick", wellbeing=True))
    original = deepcopy(answers.to_dict())

    class Browse(ScriptedPrompter):
        """Visit the last wellbeing item and return to the completion screen."""

        def __init__(self) -> None:
            super().__init__(confirm=False)
            self.navigation = None
            self.visited = False

        def question_navigation(
            self, navigation: QuestionNavigation | None, default: object
        ) -> None:
            """Observe the active navigation context."""
            self.navigation = navigation

        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            if message == "Review answers or continue:":
                return "continue" if self.visited else BACK_ACTION
            if self.navigation is not None:
                assert self.navigation.keys[self.navigation.position].startswith("cbi-work:")
                self.visited = True
                return NEXT_ACTION
            return super().select(message, choices)

    run_navigable_questions(
        answers, SessionPrompter(Browse(), answers, lambda _: None), lambda _: None
    )
    assert answers.instruments == original["instruments"]
    assert answers.review_done


def _terminal_select(keys: str, choices: list[tuple[str, str]], checkbox: bool = False):
    """Run the real terminal prompt with scripted keys and return its result."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        keyboard.send_text(keys)
        terminal = QuestionaryPrompter()
        if checkbox:
            return terminal.checkbox("Choose", choices)
        return terminal.select("Choose", choices)


def test_session_controls_are_keys_not_answer_rows(monkeypatch) -> None:
    """Pause and Start over leave the answer list; P and R still return them."""
    import questionary

    from persona_forge.navigation import RESTART_ACTION

    seen: list[list[str]] = []
    original = questionary.select

    def capture(message, options, **kwargs):
        seen.append([option.value for option in options])
        return original(message, options, **kwargs)

    monkeypatch.setattr(questionary, "select", capture)
    controls = [("a", "A"), (PAUSE_ACTION, "Pause"), (RESTART_ACTION, "Start over")]
    assert _terminal_select("p", controls) == PAUSE_ACTION
    assert _terminal_select("R", controls) == RESTART_ACTION
    assert _terminal_select("\r", controls) == "a"
    assert seen == [["a"], ["a"], ["a"]]


def test_checkbox_pause_key_returns_the_control_in_a_list() -> None:
    """Checkbox results are lists, so the pause key returns one."""
    choices = [("a", "A"), (PAUSE_ACTION, "Pause")]
    assert _terminal_select("p", choices, checkbox=True) == [PAUSE_ACTION]


def test_letters_without_a_control_do_nothing() -> None:
    """Without Start over on offer, R is ignored and Enter still answers."""
    assert _terminal_select("r\r", [("a", "A"), ("b", "B")]) == "a"


def test_control_bar_shows_keys_and_the_saved_answer() -> None:
    """The key bar lists each control with its key, and the saved answer when revisiting."""
    from persona_forge.terminal_ui import control_bar_tokens

    tokens = control_bar_tokens([("←", "Back"), ("P", "Pause")], "Very Accurate", "Saved answer:")
    text = "".join(part for _, part in tokens)
    assert "✓ Saved answer: Very Accurate" in text
    assert " ← " in text and "Back" in text and " P " in text and "Pause" in text
    assert "Saved" not in "".join(part for _, part in control_bar_tokens([("P", "Pause")]))


@pytest.mark.parametrize("checkbox", [False, True])
def test_control_bar_sits_right_under_the_answers(checkbox: bool, monkeypatch) -> None:
    """The answer list keeps its own height, so the bar is not pushed to the screen bottom."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    heights: list[bool] = []

    def inspect(self, question):
        children = question.application.layout.container.children
        heights.append(children[1].content.dont_extend_height())
        return [] if checkbox else "a"

    monkeypatch.setattr(QuestionaryPrompter, "_ask", inspect)
    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        terminal = QuestionaryPrompter()
        choices = [("a", "A"), (PAUSE_ACTION, "Pause")]
        terminal.checkbox("Choose", choices) if checkbox else terminal.select("Choose", choices)
    assert heights == [True]


def test_known_results_get_one_screen_each_and_raw_saved_values() -> None:
    """Each optional known-result question opens its own screen; saved text is not translated."""
    from persona_forge.questionnaire import KNOWN_RESULTS_TITLE, ask_known_results

    class Recorder(ScriptedPrompter):
        """Record screens and raw output."""

        def __init__(self) -> None:
            super().__init__()
            self.screens: list[str] = []
            self.raw: list[str] = []

        def screen(self, header: str, body: str) -> None:
            self.screens.append(header)

        def show_raw(self, text: str) -> None:
            self.raw.append(text)

    answers = Answers(depth="quick", role="software-engineer")
    answers.known_results = {"sixteen_personalities": "INTJ-A"}
    navigation = QuestionNavigation(
        [
            (f"known:{key}", key == "sixteen_personalities")
            for key in ("sixteen_personalities", "cliftonstrengths_top5", "disc", "enneagram")
        ]
    )
    navigation.position = 0
    recorder = Recorder()
    ask_known_results(answers, recorder, lambda _: None, navigation)
    assert len(recorder.screens) == 4
    assert all(header.startswith(KNOWN_RESULTS_TITLE) for header in recorder.screens)
    assert recorder.screens[0].endswith("1 of 4") and recorder.screens[-1].endswith("4 of 4")
    assert recorder.raw == ["INTJ-A"]


def test_terminal_starts_a_screen_once_and_clears_between_notices(monkeypatch) -> None:
    """The stepper prints once per screen; a notice after an answer clears the old screen."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from persona_forge.terminal_ui import SetupProgress

    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        terminal = QuestionaryPrompter()
    printed: list[str] = []
    clears: list[bool] = []
    monkeypatch.setattr(terminal._console, "print", lambda *a, **k: printed.append(repr(a)))
    monkeypatch.setattr(terminal._console, "clear", lambda *a, **k: clears.append(True))
    state = SetupProgress(1, ("Q", "R", "P", "G"), "Overall", 1, 4, "1/4")
    terminal.progress(state)
    terminal.progress(state)
    assert sum("Group" in item for item in printed) == 1
    terminal.notice("Optional wellbeing check", "Body.")
    assert clears == [True]
    terminal.moment("welcome", "Hello.")
    terminal.notice("Privacy and consent", "Body.")
    assert clears == [True]
