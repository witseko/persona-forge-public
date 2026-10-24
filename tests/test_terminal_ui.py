"""Terminal look: panels, stepper, plan table and the display hooks used by setup."""

import io
from collections.abc import Sequence

import pytest
from rich.console import Console

from persona_forge.answers import Answers
from persona_forge.flow import depth_instruments
from persona_forge.questionnaire import (
    PRIVACY_BODY,
    PRIVACY_TITLE,
    progress_header,
    show_notice,
)
from persona_forge.session_ui import SessionPrompter
from persona_forge.terminal_ui import (
    MODULE_ICONS,
    MOMENT_ICONS,
    PERSONA_ICONS,
    SetupProgress,
    Summary,
    detect_theme,
    emoji_enabled,
    moment_line,
    notice_panel,
    parse_progress_header,
    plan_table,
    question_panel,
    render_text,
    rich_theme,
    section_rule,
    stepper,
    summary_panel,
)

LABELS = ("Questionnaire", "Review", "Personas", "Generate")


def test_theme_follows_override_then_terminal_background() -> None:
    """PERSONA_FORGE_THEME wins; COLORFGBG with a white background means light."""
    assert detect_theme({}) == "dark"
    assert detect_theme({"COLORFGBG": "0;15"}) == "light"
    assert detect_theme({"COLORFGBG": "15;0"}) == "dark"
    assert detect_theme({"PERSONA_FORGE_THEME": "light", "COLORFGBG": "15;0"}) == "light"
    assert detect_theme({"PERSONA_FORGE_THEME": "neon"}) == "dark"


def test_progress_header_is_parsed_back_into_its_parts() -> None:
    """The question panel reads the same header the questionnaire writes."""
    assert parse_progress_header(progress_header("Thinking style", 5, 12)) == (
        "Thinking style",
        5,
        12,
    )
    assert parse_progress_header("Work situations") is None


def test_question_panel_frames_title_progress_and_hint() -> None:
    """A rounded panel with the module title, the count and the hint, within 76 columns."""
    header = progress_header("Personality", 5, 12)
    text = render_text(question_panel(header, "How true is this for you?", 76))
    lines = text.rstrip("\n").splitlines()
    assert lines[0].startswith("╭─ Personality ") and lines[-1].startswith("╰")
    assert "5 of 12" in lines[1]
    assert "How true is this for you?" in text
    assert all(len(line.rstrip()) <= 76 for line in lines)


def test_scenario_panel_keeps_title_and_full_prompt() -> None:
    """Scenario text is shown in full inside the panel, never shortened."""
    header = progress_header("Work situations", 3, 16)
    prompt = "Your team finds a bug an hour before the release. What do you do?"
    text = render_text(question_panel(header, f"Release day\n\n{prompt}", 76))
    assert "Release day" in text and prompt in text


def test_notice_reflows_bullets_into_a_hanging_list() -> None:
    """Wrapped bullet lines are joined, shown with dots, and fit the panel."""
    text = render_text(notice_panel(PRIVACY_TITLE, PRIVACY_BODY, 76, accent=True))
    assert "╭─ Privacy and consent" in text
    assert text.count("• ") == 4
    assert "│ - " not in text
    assert "Nothing is sent anywhere." in text
    assert all(len(line.rstrip()) <= 76 for line in text.splitlines())


def test_stepper_marks_stages_and_shows_the_count() -> None:
    """Done stages get a tick, the current one a dot; the count is never cut off."""
    progress = SetupProgress(2, LABELS, "", 9, 22, "9/22 statements reviewed")
    wide = render_text(stepper(progress, 76))
    assert "✓ Questionnaire" in wide and "● Review" in wide and "○ Personas" in wide
    assert "9/22 statements reviewed" in wide
    narrow = render_text(stepper(progress, 50), width=50)
    assert "● Review 2/4" in narrow and "Personas" not in narrow
    assert "9/22 statements reviewed" in narrow


def test_plan_lists_modules_with_their_status() -> None:
    """Finished, started and untouched modules each get their own status."""
    instrument = depth_instruments("deep")[0]
    answers = Answers(depth="deep", role="software-engineer")
    answers.instruments[instrument.id] = {item.id: 3 for item in instrument.items}
    second = depth_instruments("deep")[1]
    answers.instruments[second.id] = {item.id: 2 for item in second.items[:4]}
    session = SessionPrompter(Recorder(), answers, lambda _: None)
    text = render_text(plan_table(session.module_plan(), 76))
    assert "✓ done" in text and f"● 4 of {len(second.items)}" in text and "○ to do" in text
    assert "Work situations" in text and "Working with your agent" in text
    assert "optional wellbeing adds 7 questions" in text
    assert "Time" not in render_text(plan_table(session.module_plan(), 50), width=50)


def test_section_rule_names_the_finished_section() -> None:
    """The rule says which section is done."""
    assert "✓ Personality" in render_text(section_rule("Personality"))


class Recorder:
    """A prompter with the display extras; records what it was asked to show."""

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def show(self, text: str) -> None:
        self.events.append(("show", text))

    def notice(self, title: str, body: str) -> None:
        self.events.append(("notice", title))

    def progress(self, state: SetupProgress) -> None:
        self.events.append(("progress", state))

    def plan(self, plan: object) -> None:
        self.events.append(("plan", plan))

    def section_done(self, title: str) -> None:
        self.events.append(("section_done", title))

    def moment(self, kind: str, text: str) -> None:
        self.events.append(("moment", (kind, text)))

    def screen(self, header: str, body: str) -> None:
        self.events.append(("screen", header))

    def pause(self, message: str) -> None:
        self.events.append(("pause", message))

    def select(self, message: str, choices: Sequence[tuple[str, str]]) -> str:
        return choices[0][0]

    def checkbox(self, message: str, choices: Sequence[tuple[str, str]]) -> list[str]:
        return []

    def text(self, message: str, limit: int) -> str:
        return ""

    def confirm(self, message: str, default: bool) -> bool:
        return default


def test_session_uses_display_extras_when_the_prompter_has_them() -> None:
    """Stepper data before prompts, the plan on the first screen only, a rule per section."""
    recorder = Recorder()
    answers = Answers(depth="quick", role="software-engineer")
    session = SessionPrompter(recorder, answers, lambda _: None)
    session.screen(progress_header("Personality", 1, 20), "hint")
    session.select("question", [("1", "one")])
    session.screen(progress_header("Personality", 2, 20), "hint")
    session.screen(progress_header("Work situations", 1, 8), "")
    kinds = [kind for kind, _ in recorder.events]
    assert kinds.count("plan") == 1 and kinds.index("plan") == kinds.index("screen") + 1
    progress = next(value for kind, value in recorder.events if kind == "progress")
    assert isinstance(progress, SetupProgress) and progress.stage == 1 and progress.total == 44
    assert ("section_done", "Personality") in recorder.events
    assert "show" not in kinds


def test_notice_falls_back_to_plain_text_for_simple_prompters() -> None:
    """Prompters without `notice` receive the title and body as one text."""

    class Plain:
        def __init__(self) -> None:
            self.shown: list[str] = []

        def show(self, text: str) -> None:
            self.shown.append(text)

    plain = Plain()
    show_notice(plain, "Review", "Choose for each statement.")
    assert plain.shown == ["Review\n\nChoose for each statement."]


def test_terminal_prompter_draws_the_stepper_above_the_question_panel() -> None:
    """A cleared screen waits, so the stepper prints first and the panel follows it."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from persona_forge.questionnaire import QuestionaryPrompter

    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        prompter = QuestionaryPrompter()
    buffer = io.StringIO()
    prompter._console = Console(file=buffer, width=80, theme=rich_theme("dark"), color_system=None)
    prompter.screen(progress_header("Personality", 1, 20), "How true is this for you?")
    assert buffer.getvalue() == ""
    prompter.progress(SetupProgress(1, LABELS, "Overall", 0, 44, "0/44 answered (0%)"))
    output = buffer.getvalue()
    assert output.index("● Questionnaire") < output.index("╭─") < output.index("Personality")


def test_every_icon_is_one_wide_emoji_so_borders_stay_aligned() -> None:
    """Variation selectors (as in ⚖️) are measured as one column but drawn as two."""
    from rich.cells import cell_len

    icons = [*MODULE_ICONS.values(), *PERSONA_ICONS.values(), *MOMENT_ICONS.values(), "✨"]
    for icon in icons:
        assert len(icon) == 1 and cell_len(icon) == 2, icon


def test_wellbeing_has_no_icon_and_every_preset_has_one() -> None:
    """Icons stay away from wellbeing; each shipped preset persona gets its own icon."""
    from persona_forge.egos import load_presets
    from persona_forge.flow import MODULE_TITLES

    assert not any("ellbeing" in title for title in MODULE_ICONS)
    assert set(MODULE_ICONS) <= {
        *MODULE_TITLES.values(),
        "Work situations",
        "Working with your agent",
    }
    assert set(load_presets()) <= set(PERSONA_ICONS)


def test_emoji_can_be_turned_off() -> None:
    """An environment switch, a dumb terminal or a non-UTF-8 terminal turns emoji off."""
    assert emoji_enabled({}, "utf-8")
    assert not emoji_enabled({"PERSONA_FORGE_EMOJI": "0"}, "utf-8")
    assert not emoji_enabled({"TERM": "dumb"}, "utf-8")
    assert not emoji_enabled({}, "ascii")


def test_icons_appear_in_titles_plan_and_rule_only_when_given() -> None:
    """The same layout works with and without icons."""
    header = progress_header("Personality", 2, 20)
    assert "╭─ 🧠 Personality" in render_text(question_panel(header, "hint", 76, MODULE_ICONS))
    assert "╭─ Personality" in render_text(question_panel(header, "hint", 76))
    assert "✓ 🧠 Personality" in render_text(section_rule("Personality", MODULE_ICONS))
    session = SessionPrompter(Recorder(), Answers(depth="quick", role="cto"), lambda _: None)
    assert "💼 Work situations" in render_text(plan_table(session.module_plan(), 76, MODULE_ICONS))


def test_summary_lists_personas_with_their_switch_names() -> None:
    """The finish screen names each persona with its icon and pf- name, then next steps."""
    summary = Summary(
        "Done, Alex",
        (("Depth", "Standard"), ("Files", "14 written to out")),
        "Your personas",
        (("mentor", "Mentor"), ("rubber-duck", "Rubber Duck")),
        (("make report", "open your private report"),),
    )
    text = render_text(summary_panel(summary, 76, "🔥"))
    assert "╭─ 🔥 Done, Alex" in text
    assert "🧭 Mentor" in text and "pf-mentor" in text
    assert "✨ Rubber Duck" in text and "pf-rubber-duck" in text
    assert "make report" in text
    plain = render_text(summary_panel(summary, 76, "", emoji=False))
    assert "🧭" not in plain and "Mentor" in plain


def test_moment_line_never_reads_markup() -> None:
    """A name with brackets is shown as typed, not as rich markup."""
    assert "[bold]Alex[/bold]" in render_text(moment_line("👋", "Welcome back, [bold]Alex[/bold]."))


def test_session_moments_welcome_resume_and_halfway() -> None:
    """New sessions get a welcome; saved ones say where they stopped; halfway shows once."""
    recorder = Recorder()
    SessionPrompter(recorder, Answers(), lambda _: None).welcome(resumed=False)
    assert recorder.events == [("moment", ("welcome", "Let's forge your work profile."))]

    instrument = depth_instruments("quick")[0]
    answers = Answers(consent=True, name="Alex", role="cto", seniority="senior", depth="quick")
    answers.instruments[instrument.id] = {item.id: 3 for item in instrument.items[:2]}
    recorder = Recorder()
    session = SessionPrompter(recorder, answers, lambda _: None)
    session.welcome(resumed=True)
    expected = "Welcome back, Alex. You stopped at Personality, question 3 of 20."
    assert recorder.events == [("moment", ("resume", expected))]

    recorder.events.clear()
    session.show_progress()
    answers.instruments[instrument.id] = {item.id: 3 for item in instrument.items}
    answers.sjt = {scenario.id: scenario.options[0].id for scenario in _scenarios("quick", "cto")}
    session.show_progress()
    session.show_progress()
    halfway = [event for event in recorder.events if event[0] == "moment"]
    assert len(halfway) == 1 and halfway[0][1][0] == "halfway"


def _scenarios(depth: str, role: str) -> tuple:
    """Scenarios for a depth and role."""
    from persona_forge.flow import depth_scenarios

    return depth_scenarios(depth, role)


def test_persona_picker_shows_icons_only_for_personas(monkeypatch) -> None:
    """Preset choices get their icon; other checkbox choices stay as written."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from persona_forge.questionnaire import QuestionaryPrompter

    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        prompter = QuestionaryPrompter()
    prompter._emoji = True
    seen: list[str] = []

    class Answered:
        def ask(self, **kwargs: object) -> list[str]:
            """Accept the terminal cancellation-message option."""
            return []

    def fake_checkbox(message, options, **kwargs):
        seen.extend(option.title for option in options)
        return Answered()

    monkeypatch.setattr(prompter._questionary, "checkbox", fake_checkbox)
    prompter.checkbox("Pick", [("mentor", "Mentor: patient"), ("other-1", "Plain option")])
    assert seen == ["🧭 Mentor: patient", "Plain option"]


def test_display_folder_is_relative_inside_the_working_directory(tmp_path, monkeypatch) -> None:
    """The finish screen shows out rather than a long absolute path."""
    from persona_forge.setup import display_folder

    monkeypatch.chdir(tmp_path)
    assert display_folder(tmp_path / "out") == "out"
    assert display_folder(tmp_path.parent) == str(tmp_path.parent.resolve())


@pytest.mark.parametrize(
    "terminal,term,clears", [(True, "xterm", True), (False, "xterm", False), (True, "dumb", False)]
)
def test_session_start_clears_terminal_history_only_for_interactive_output(
    monkeypatch: pytest.MonkeyPatch, terminal: bool, term: str, clears: bool
) -> None:
    """Scrollback is cleared before the UI, but redirected output gets no escape codes."""
    from persona_forge.questionnaire import QuestionaryPrompter

    monkeypatch.setenv("TERM", term)
    prompter = QuestionaryPrompter()
    buffer = io.StringIO()
    prompter._console = Console(file=buffer, force_terminal=terminal)
    prompter.start_session()
    assert buffer.getvalue() == ("\x1b[3J\x1b[2J\x1b[H" if clears else "")
