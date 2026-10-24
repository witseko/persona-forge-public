"""Run the questionnaire: ask only what is missing, saving after every answer.

All prompting goes through the small `Prompter` interface, so tests can script answers
and the interactive terminal UI (questionary) stays in one place.
"""

from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Protocol

from persona_forge.answers import KNOWN_RESULT_LIMITS, NAME_LIMIT, Answers, AnswersError, clean_text
from persona_forge.content import Preference, load_preferences
from persona_forge.flow import (
    DEPTHS,
    MODULE_TITLES,
    ROLES,
    SENIORITY,
    WELLBEING_INSTRUMENTS,
    depth_instruments,
    depth_scenarios,
    estimated_minutes,
    wellbeing_instruments,
)
from persona_forge.instruments import load_instrument_by_id
from persona_forge.languages import load_language
from persona_forge.model import Instrument, SJTScenario
from persona_forge.navigation import (
    BACK_ACTION,
    CONTROL_ACTIONS,
    NEXT_ACTION,
    PAUSE_ACTION,
    RESTART_ACTION,
    QuestionMoved,
    QuestionNavigation,
    configure_prompt,
    pending,
)
from persona_forge.permissions import instrument_installed
from persona_forge.translations import (
    LEGACY_UKRAINIAN_INSTRUMENTS,
    TRANSLATION_NOTICE,
    translate_instrument,
    validate_language,
)

PRIVACY_TITLE = "Privacy and consent"
PRIVACY_BODY = """\
- Your answers and everything generated from them stay in this project's out/ folder,
  which git ignores. Nothing is sent anywhere.
- The only exception is the optional prose polish at the end. It is off unless you
  choose it, and it shows exactly what would be sent first. Wellbeing data is never sent.
- This is a reflection tool. It does not diagnose anything, and its scores are not
  population norms, ability ratings or predictions of job performance.
- You can stop at any time with Ctrl-C. Progress is saved after every answer."""

KNOWN_RESULT_QUESTIONS = {
    "sixteen_personalities": "16Personalities type, if you know it (for example INTJ-A)",
    "cliftonstrengths_top5": "CliftonStrengths top 5, if you know them",
    "disc": "DISC style, if you know it",
    "enneagram": "Enneagram type, if you know it",
}

WELLBEING_TITLE = "Optional wellbeing check"
KNOWN_RESULTS_TITLE = "Optional: results you already know"
COMPLETE_TITLE = "Questionnaire complete"
COMPLETE_BODY = "All questions are answered. Press ← to go back and change an answer, or continue."
KNOWN_RESULTS_BODY = (
    "Leave blank to skip. These are kept as your own hints; this tool does not reproduce "
    "those tests."
)
WELLBEING_BODY = """\
One short, freely available questionnaire about energy and exhaustion at work
(Copenhagen Burnout Inventory, work scale, 7 questions). It is not a diagnosis.
Its results appear only in your private report. They never go into agent files, and
the screener name never appears there either."""


READING_WIDTH = 76

# Session controls shown as keys under a prompt instead of extra answer rows.
CONTROL_KEYS = {BACK_ACTION: "←", NEXT_ACTION: "→", PAUSE_ACTION: "P", RESTART_ACTION: "R"}
CONTROL_LABELS = {
    BACK_ACTION: "Back",
    NEXT_ACTION: "Next",
    PAUSE_ACTION: "Pause",
    RESTART_ACTION: "Start over",
}

# Short reminders shown above each item. They restate the source instructions, which
# are shown in full at the start of each questionnaire; item wording is never changed.
ITEM_HINTS = {
    "mini-ipip": "How accurately does this describe you, as you generally are now?",
    "ipip-neo-120": "How accurately does this describe you, as you generally are now?",
    "ipip-hexaco-hh": "How accurately does this describe you, as you generally are now?",
    "ipip-via": "How accurately does this describe you, as you generally are now?",
    "gse": "How true is this for you?",
    "ncs-6": "How characteristic is this of you?",
    "cbi-work": "Think about your work.",
}


# IPIP items are written without a subject ("Am the life of the party."). IPIP allows
# editing item wording, so these are shown in the first person for readability. The
# data files keep the exact source text; only the displayed question changes.
FIRST_PERSON_INSTRUMENTS = {"mini-ipip", "ipip-neo-120", "ipip-hexaco-hh", "ipip-via"}


def display_text(instrument_id: str, text: str) -> str:
    """Return the question as shown: "Am the life..." becomes "I am the life..." for IPIP."""
    if instrument_id not in FIRST_PERSON_INSTRUMENTS:
        return text
    return f"I {text[0].lower()}{text[1:]}"


def progress_header(title: str, number: int, total: int) -> str:
    """One header line, for example "Personality   [####------]  4 of 20"."""
    filled = round(10 * (number - 1) / total)
    return f"{title}   [{'#' * filled}{'-' * (10 - filled)}]  {number} of {total}"


class SetupInterrupted(Exception):
    """Raised when the user cancels a prompt (Ctrl-C). Progress is already saved."""


def show_notice(prompter: object, title: str, body: str) -> None:
    """Show a titled notice: framed when the prompter supports it, else as plain text."""
    notice = getattr(prompter, "notice", None)
    if callable(notice):
        notice(title, body)
    else:
        prompter.show(f"{title}\n\n{body}")  # type: ignore[attr-defined]


class Prompter(Protocol):
    """The prompts the questionnaire needs. Each returns the chosen value(s).

    A prompter may also offer display-only extras: `notice(title, body)`,
    `progress(SetupProgress)`, `plan(Plan)`, `section_done(title)`, `moment(kind, text)`
    and `summary(Summary)`. Callers use them through `show_notice` and
    `SessionPrompter`; notice and progress fall back to `show`, the rest are skipped.
    """

    def show(self, text: str) -> None:
        """Display information."""

    def screen(self, header: str, body: str) -> None:
        """Start a fresh screen: a short header line, then wrapped body text."""

    def pause(self, message: str) -> None:
        """Wait until the user is ready to continue."""

    def select(self, message: str, choices: Sequence[tuple[str, str]]) -> str:
        """Pick one value from (value, label) pairs."""

    def checkbox(self, message: str, choices: Sequence[tuple[str, str]]) -> list[str]:
        """Pick any number of values from (value, label) pairs."""

    def text(self, message: str, limit: int) -> str:
        """Type a short free-text answer (may be empty)."""

    def confirm(self, message: str, default: bool) -> bool:
        """Answer yes or no."""


class QuestionaryPrompter:
    """Interactive prompts in the terminal using questionary and rich.

    A screen is drawn lazily: `screen`, `notice` and `section_done` start a fresh screen
    and queue their content, so the setup stepper (from `progress`) is printed above it,
    once per screen. Any other output or prompt prints the queue first. A fresh screen
    keeps lines printed since the last answer (a welcome or a saved value), so they are
    not wiped before they are read.
    """

    def __init__(self) -> None:
        # Imported here so tests and non-interactive runs never need a terminal.
        import os

        import questionary
        from rich.console import Console

        from persona_forge.terminal_ui import (
            MODULE_ICONS,
            detect_theme,
            emoji_enabled,
            questionary_style_rules,
            rich_theme,
        )

        theme = detect_theme(os.environ)
        self._questionary = questionary
        self._console = Console(theme=rich_theme(theme))
        self._style = questionary.Style(questionary_style_rules(theme))
        self._pending: list[object] = []
        self._new_screen = True
        self._since_prompt = False
        self._emoji = emoji_enabled(os.environ, self._console.encoding)
        self._icons = MODULE_ICONS if self._emoji else {}
        self._language = load_language("en")
        self._navigation: QuestionNavigation | None = None
        self._answer_default: str | list[str] | None = None

    def question_navigation(
        self, navigation: QuestionNavigation | None, default: str | list[str] | None
    ) -> None:
        """Remember the saved answer and enable horizontal question navigation."""
        self._navigation = navigation
        self._answer_default = default

    def _bind_navigation(self, question: object) -> None:
        """Left/right leave the current answer untouched; Enter alone submits edits."""
        if self._navigation is None:
            return
        from prompt_toolkit.keys import Keys

        bindings = question.application.key_bindings

        @bindings.add(Keys.Left, eager=True)
        def previous(event: object) -> None:
            """Move back unless this is the first question."""
            if self._navigation.position > 0:
                event.app.exit(exception=QuestionMoved(-1))

        @bindings.add(Keys.Right, eager=True)
        def following(event: object) -> None:
            """Move forward without submitting the highlighted answer."""
            if self._navigation.position < len(self._navigation.keys):
                event.app.exit(exception=QuestionMoved(1))

    def _split_controls(
        self, choices: Sequence[tuple[str, str]]
    ) -> tuple[list[tuple[str, str]], list[str]]:
        """Separate answers from session controls, which become keys instead of rows."""
        answers = [(value, label) for value, label in choices if value not in CONTROL_ACTIONS]
        controls = [value for value in CONTROL_ACTIONS if value in {v for v, _ in choices}]
        return answers, controls

    def _add_control_bar(
        self, question: object, controls: list[str], saved: str, as_list: bool
    ) -> None:
        """Bind P and R and draw the key bar (and any saved answer) under the choices.

        Left and Right are bound by `_bind_navigation`; P and R end the prompt with the
        control value, so the session handles them exactly like the old menu rows.
        """
        if not controls and not saved:
            return
        from prompt_toolkit.filters import IsDone, to_filter
        from prompt_toolkit.layout.containers import ConditionalContainer, Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        from persona_forge.terminal_ui import control_bar_tokens

        application = question.application  # type: ignore[attr-defined]
        for value, key in ((PAUSE_ACTION, "p"), (RESTART_ACTION, "r")):
            if value in controls:
                result = [value] if as_list else value
                for character in (key, key.upper()):
                    application.key_bindings.add(character, eager=True)(
                        lambda event, result=result: event.app.exit(result=result)
                    )
        chips = [
            (CONTROL_KEYS[value], self._language.text(CONTROL_LABELS[value])) for value in controls
        ]
        tokens = control_bar_tokens(chips, saved, self._language.text("Saved answer:"))
        bar = Window(FormattedTextControl(tokens), dont_extend_height=True)
        children = application.layout.container.children
        # The answer list fills spare rows by default, which pushes the bar to the bottom
        # of the terminal. Keep it at its own height so the bar sits under the answers.
        choices = getattr(children[1], "content", None)
        if isinstance(choices, Window):
            choices.dont_extend_height = to_filter(True)
        children.insert(2, ConditionalContainer(bar, filter=~IsDone()))

    def set_language(self, language: str) -> None:
        """Use the selected plugin for terminal-owned instructions and validation text."""
        self._language = load_language(language)
        from persona_forge.terminal_ui import MODULE_ICONS

        self._icons = (
            {self._language.text(title): icon for title, icon in MODULE_ICONS.items()}
            if self._emoji
            else {}
        )

    def start_session(self) -> None:
        """Clear the terminal display and scrollback once before setup's first prompt."""
        self._pending = []
        if self._console.is_terminal and not self._console.is_dumb_terminal:
            # Rich's normal clear keeps scrollback. CSI 3 J also erases saved lines;
            # CSI 2 J clears the screen and CSI H returns the cursor to the top.
            # Emit fixed control sequences only to a capable interactive terminal.
            self._console.file.write("\x1b[3J\x1b[2J\x1b[H")
            self._console.file.flush()
        self._new_screen = True
        self._since_prompt = False

    def _begin_screen(self) -> None:
        """Start a fresh screen, keeping anything printed since the last answer."""
        if not self._since_prompt:
            self._pending = []
            self._console.clear()
        self._new_screen = True

    def _ask(self, question: object) -> object:
        """Run a question; questionary returns None when the user presses Ctrl-C."""
        self._flush()
        result = question.ask(kbi_msg="")  # type: ignore[attr-defined]
        self._since_prompt = False
        if result is None:
            raise SetupInterrupted
        return result

    def _flush(self) -> None:
        """Print queued screen parts."""
        pending, self._pending = self._pending, []
        for renderable in pending:
            self._console.print(renderable)

    def show(self, text: str) -> None:
        """Print text with rich formatting disabled (content is plain)."""
        self._flush()
        self._console.print(text, markup=False, highlight=False, width=self._width())
        self._since_prompt = True

    def notice(self, title: str, body: str) -> None:
        """A framed notice. Privacy and consent gets the accent border, once."""
        from persona_forge.terminal_ui import notice_panel

        self._begin_screen()
        accent = title == self._language.text(PRIVACY_TITLE)
        self._pending.append(notice_panel(title, body, self._width(), accent=accent))

    def progress(self, state: object) -> None:
        """Print the setup stepper once per screen, then the queued screen below it."""
        from persona_forge.terminal_ui import stepper

        if self._new_screen:
            self._console.print(stepper(state, self._width()))  # type: ignore[arg-type]
            self._new_screen = False
        self._flush()

    def plan(self, plan: object) -> None:
        """Queue the module plan table above the current screen's panel."""
        from persona_forge.terminal_ui import plan_table

        table = plan_table(plan, self._width(), self._icons)  # type: ignore[arg-type]
        self._pending.insert(0, table)

    def section_done(self, title: str) -> None:
        """Start a screen with a rule marking the finished section."""
        from persona_forge.terminal_ui import section_rule

        self._begin_screen()
        self._pending.append(section_rule(title, self._icons))

    def moment(self, kind: str, text: str) -> None:
        """Print a one-line moment (welcome, halfway, forging) with its icon."""
        from persona_forge.terminal_ui import MOMENT_ICONS, moment_line

        icon = MOMENT_ICONS.get(kind, "") if self._emoji else ""
        self._console.print(moment_line(icon, text), width=self._width())
        self._since_prompt = True

    def summary(self, summary: object) -> None:
        """Print the finish screen."""
        from persona_forge.terminal_ui import MOMENT_ICONS, summary_panel

        self._flush()
        icon = MOMENT_ICONS["done"] if self._emoji else ""
        self._console.print()
        self._console.print(
            summary_panel(summary, self._width(), icon, self._emoji)  # type: ignore[arg-type]
        )

    def _width(self) -> int:
        """Keep lines short enough to read comfortably."""
        return min(self._console.width, READING_WIDTH)

    def screen(self, header: str, body: str) -> None:
        """Clear the terminal so only the current question is visible."""
        from persona_forge.terminal_ui import question_panel

        self._pending = []
        self._console.clear()
        self._new_screen = True
        self._pending.append(question_panel(header, body, self._width(), self._icons))

    def pause(self, message: str) -> None:
        """Wait for any key. This prompt returns None on success, so Ctrl-C is caught instead."""
        self._flush()
        try:
            self._questionary.press_any_key_to_continue(message, style=self._style).unsafe_ask()
        except KeyboardInterrupt as error:
            raise SetupInterrupted from error
        self._since_prompt = False

    def select(self, message: str, choices: Sequence[tuple[str, str]]) -> str:
        """Arrow-key or number-key selection, with session controls as a key bar."""
        answers, controls = self._split_controls(choices)
        options = [self._questionary.Choice(title=label, value=value) for value, label in answers]
        default = self._answer_default if isinstance(self._answer_default, str) else None
        saved = next((label for value, label in answers if value == default), "")
        question = self._questionary.select(
            message,
            options,
            default=default if saved else None,
            use_shortcuts=len(options) <= 9,
            instruction=self._language.text("(Up/Down: answer, Enter: save)")
            if self._navigation is not None
            else self._language.text("(press Enter)")
            if len(options) == 1
            else self._language.text("(keys 1-{count} or arrows, then Enter)", count=len(options))
            if len(options) <= 9
            else self._language.text("(arrows, then Enter)"),
            style=self._style,
        )
        self._bind_navigation(question)
        self._add_control_bar(question, controls, saved, as_list=False)
        return str(self._ask(question))

    def checkbox(self, message: str, choices: Sequence[tuple[str, str]]) -> list[str]:
        """Space to toggle, Enter to confirm. Persona choices get their icon."""
        from persona_forge.terminal_ui import PERSONA_ICONS, with_icon

        answers, controls = self._split_controls(choices)
        options = [
            self._questionary.Choice(
                title=with_icon(PERSONA_ICONS.get(value, "") if self._emoji else "", label),
                value=value,
            )
            for value, label in answers
        ]
        if isinstance(self._answer_default, list):
            for option in options:
                option.checked = option.value in self._answer_default
        question = self._questionary.checkbox(
            message,
            options,
            instruction=self._language.text("(Space: tick, Enter: save)")
            if self._navigation is not None
            else self._language.text("(Space to tick, Enter when done)"),
            style=self._style,
        )
        self._bind_navigation(question)
        self._add_control_bar(question, controls, "", as_list=True)
        return list(self._ask(question))  # type: ignore[call-overload]

    def text(self, message: str, limit: int) -> str:
        """Free text, validated for length before it is accepted."""

        def within_limit(value: str) -> bool | str:
            return len(value) <= limit or self._language.text(
                "! At most {limit} characters, please.", limit=limit
            )

        return str(
            self._ask(self._questionary.text(message, validate=within_limit, style=self._style))
        )

    def confirm(self, message: str, default: bool) -> bool:
        """Yes or no."""
        if self._language.code != "en":
            # questionary.confirm hardcodes English Yes/No in the submitted answer.
            # A boolean-valued select keeps both the interface and result localized.
            choices = [
                self._questionary.Choice(self._language.text("Yes"), value=True),
                self._questionary.Choice(self._language.text("No"), value=False),
            ]
            return bool(
                self._ask(
                    self._questionary.select(
                        message,
                        choices,
                        default=default,
                        style=self._style,
                        instruction=self._language.text("(arrows, then Enter)"),
                    )
                )
            )
        return bool(
            self._ask(
                self._questionary.confirm(
                    message,
                    default=default,
                    style=self._style,
                    instruction=self._language.text("(Yes/No: y/n)"),
                )
            )
        )


def check_known_identifiers(answers: Answers) -> None:
    """Refuse answers that name roles, items or options the shipped content does not have."""
    if answers.role and answers.role not in ROLES:
        raise AnswersError(f"unknown role {answers.role}")
    if answers.seniority and answers.seniority not in SENIORITY:
        raise AnswersError(f"unknown seniority {answers.seniority}")
    if answers.depth and answers.depth not in DEPTHS:
        raise AnswersError(f"unknown depth {answers.depth}")
    allowed_instruments = set(WELLBEING_INSTRUMENTS)
    if answers.depth:
        allowed_instruments |= set(DEPTHS[answers.depth].instrument_ids)
    for instrument_id, responses in answers.instruments.items():
        if instrument_id not in allowed_instruments:
            raise AnswersError(f"instrument {instrument_id} is not part of this depth")
        if not instrument_installed(instrument_id):
            raise AnswersError(f"instrument {instrument_id} is not included in this edition")
        instrument = load_instrument_by_id(instrument_id)
        items = {item.id: item for item in instrument.items}
        for item_id, value in responses.items():
            if item_id not in items:
                raise AnswersError(f"unknown item {item_id} in {instrument_id}")
            if value not in instrument.response_set(items[item_id].response_set).values:
                raise AnswersError(f"answer for {item_id} is not an allowed value")
    if answers.sjt:
        if not (answers.depth and answers.role):
            raise AnswersError("scenario answers need a depth and a role")
        scenarios = {
            scenario.id: scenario for scenario in depth_scenarios(answers.depth, answers.role)
        }
        for scenario_id, option_id in answers.sjt.items():
            if scenario_id not in scenarios:
                raise AnswersError(f"scenario {scenario_id} is not part of this depth and role")
            if option_id not in {option.id for option in scenarios[scenario_id].options}:
                raise AnswersError(f"unknown option {option_id} for {scenario_id}")
    preferences = {preference.id: preference for preference in load_preferences()}
    for preference_id, option_id in answers.preferences.items():
        if preference_id not in preferences:
            raise AnswersError(f"unknown preference {preference_id}")
        if option_id not in {option.id for option in preferences[preference_id].options}:
            raise AnswersError(f"unknown option {option_id} for {preference_id}")


def _incomplete_instruments(answers: Answers, instruments: Sequence[Instrument]) -> list[str]:
    """List instruments whose saved response count does not cover their complete item set."""
    return [
        instrument.id
        for instrument in instruments
        if len(answers.instruments.get(instrument.id, {})) != len(instrument.items)
    ]


def missing_questionnaire_parts(answers: Answers) -> list[str]:
    """List what is still unanswered, in questionnaire order (empty when complete)."""
    missing = [
        key
        for key in ("consent", "name", "role", "seniority", "depth")
        if not getattr(answers, key)
    ]
    if missing:
        return missing
    missing.extend(
        _incomplete_instruments(
            answers, depth_instruments(answers.depth, answers.questionnaire_language)
        )
    )
    if len(answers.sjt) != len(depth_scenarios(answers.depth, answers.role)):
        missing.append("sjt")
    if len(answers.preferences) != len(load_preferences()):
        missing.append("preferences")
    if not answers.known_results_done:
        missing.append("known_results")
    optional = wellbeing_instruments(answers.questionnaire_language)
    has_wellbeing = bool(optional)
    if answers.wellbeing_opt_in is None and has_wellbeing:
        missing.append("wellbeing_opt_in")
    elif answers.wellbeing_opt_in and has_wellbeing:
        missing.extend(_incomplete_instruments(answers, optional))
    return missing


def ask_setup_details(
    answers: Answers, prompter: Prompter, save: Callable[[Answers], None], preference_count: int
) -> None:
    """Ask consent and basic profile details before selecting language-aware depth."""
    if not answers.consent:
        show_notice(prompter, PRIVACY_TITLE, PRIVACY_BODY)
        if not prompter.confirm("I understand and want to continue.", default=True):
            raise SetupInterrupted
        answers.consent = True
        save(answers)
    if not answers.name:
        name = ""
        while not name:
            name = clean_text(prompter.text("Your name or nickname:", NAME_LIMIT), NAME_LIMIT)
        answers.name = name
        save(answers)
    if not answers.role:
        answers.role = prompter.select("Your role:", list(ROLES.items()))
        save(answers)
    if not answers.seniority:
        answers.seniority = prompter.select("Your seniority:", list(SENIORITY.items()))
        save(answers)
    if not answers.depth:
        choices = [
            (
                depth.id,
                f"{depth.title} (about "
                f"{estimated_minutes(depth.id, preference_count, answers.questionnaire_language)} "
                "minutes)",
            )
            for depth in DEPTHS.values()
            if depth_instruments(depth.id, answers.questionnaire_language)
        ]
        answers.depth = prompter.select("How deep should the questionnaire go?", choices)
        save(answers)


def run_questionnaire(
    answers: Answers, prompter: Prompter, save: Callable[[Answers], None]
) -> None:
    """Ask every missing question in order, calling `save` after each answer."""
    validate_language(answers.questionnaire_language)
    preferences = load_preferences()
    ask_setup_details(answers, prompter, save, len(preferences))
    run_navigable_questions(answers, prompter, save)


def _navigation_questions(answers: Answers) -> list[tuple[str, bool]]:
    """List editable questions in presentation order, including saved optional items."""
    questions = []
    instruments = list(depth_instruments(answers.depth, answers.questionnaire_language))
    for instrument in instruments:
        responses = answers.instruments.get(instrument.id, {})
        checklist = instrument.aggregation == "sum" and instrument.response_sets[0].values == {0, 1}
        size = 10 if checklist else 1
        for start in range(0, len(instrument.items), size):
            block = instrument.items[start : start + size]
            questions.append(
                (f"{instrument.id}:{block[0].id}", all(i.id in responses for i in block))
            )
    questions.extend(
        (f"sjt:{scenario.id}", scenario.id in answers.sjt)
        for scenario in depth_scenarios(answers.depth, answers.role)
    )
    questions.extend(
        (f"preference:{preference.id}", preference.id in answers.preferences)
        for preference in load_preferences()
    )
    questions.extend(
        (f"known:{key}", answers.known_results_done or key in answers.known_results)
        for key in KNOWN_RESULT_QUESTIONS
    )
    if answers.wellbeing_opt_in:
        for instrument in wellbeing_instruments(answers.questionnaire_language):
            responses = answers.instruments.get(instrument.id, {})
            questions.extend(
                (f"{instrument.id}:{item.id}", item.id in responses) for item in instrument.items
            )
    return questions


def run_navigable_questions(
    answers: Answers, prompter: Prompter, save: Callable[[Answers], None]
) -> None:
    """Visit saved or new questions without changing answers merely by moving."""
    previous = deepcopy(
        (answers.instruments, answers.sjt, answers.preferences, answers.known_results)
    )

    def save_answer(current: Answers) -> None:
        """Re-review inferred statements after an answer changes, retaining persona choices."""
        nonlocal previous
        content = (current.instruments, current.sjt, current.preferences, current.known_results)
        if content != previous:
            current.review.clear()
            current.review_done = False
            previous = deepcopy(content)
        save(current)

    navigation = QuestionNavigation(_navigation_questions(answers))
    while True:
        try:
            configure_prompt(prompter, navigation, None)
            for instrument in depth_instruments(answers.depth, answers.questionnaire_language):
                ask_instrument(instrument, answers, prompter, save_answer, navigation)
            ask_scenarios(
                depth_scenarios(answers.depth, answers.role),
                answers,
                prompter,
                save_answer,
                navigation,
            )
            ask_preferences(load_preferences(), answers, prompter, save_answer, navigation)
            ask_known_results(answers, prompter, save_answer, navigation)
            _ask_optional_questions(answers, prompter, save_answer, navigation)
            show_notice(prompter, COMPLETE_TITLE, COMPLETE_BODY)
            configure_prompt(prompter, navigation, None)
            prompter.select("Review answers or continue:", [("continue", "Continue")])
            missing = QuestionNavigation(_navigation_questions(answers))
            if missing.position == len(missing.keys):
                return
            navigation.position = missing.position
        except QuestionMoved as move:
            navigation.move(move.direction)
        finally:
            configure_prompt(prompter, None, None)


def _ask_optional_questions(
    answers: Answers,
    prompter: Prompter,
    save: Callable[[Answers], None],
    navigation: QuestionNavigation,
) -> None:
    """Append optional items after consent, retaining the same navigation cursor."""
    optional = wellbeing_instruments(answers.questionnaire_language)
    if not optional:
        answers.wellbeing_opt_in = False
    elif answers.wellbeing_opt_in is None:
        show_notice(prompter, WELLBEING_TITLE, WELLBEING_BODY)
        answers.wellbeing_opt_in = prompter.confirm(
            "Take the optional wellbeing check?", default=False
        )
        save(answers)
    navigation.keys = [key for key, _ in _navigation_questions(answers)]
    if answers.wellbeing_opt_in:
        for instrument in optional:
            ask_instrument(instrument, answers, prompter, save, navigation)


def _administration_language(instrument_id: str, answers: Answers, has_responses: bool) -> str:
    """Keep the language of saved answers, including legacy English CBI administrations."""
    if instrument_id in answers.instrument_languages:
        return answers.instrument_languages[instrument_id]
    if has_responses and instrument_id not in LEGACY_UKRAINIAN_INSTRUMENTS:
        return "en"
    return answers.questionnaire_language


def _instrument_instructions(instrument: Instrument, answers: Answers, language: str) -> str:
    """Add a translated provenance notice without changing administration wording."""
    if language != "en":
        notice = load_language(language).text(TRANSLATION_NOTICE)
        return f"{notice}\n\n{instrument.instructions}"
    if answers.questionnaire_language != "en":
        notice = load_language(answers.questionnaire_language).text(
            "This instrument continues in its previously administered language."
        )
        return f"{notice}\n\n{instrument.instructions}"
    return instrument.instructions


def ask_instrument(
    instrument: Instrument,
    answers: Answers,
    prompter: Prompter,
    save: Callable[[Answers], None],
    navigation: QuestionNavigation | None = None,
) -> None:
    """Ask the unanswered items of one instrument."""
    responses = answers.instruments.setdefault(instrument.id, {})
    remaining = [
        item
        for item in instrument.items
        if pending(navigation, f"{instrument.id}:{item.id}", item.id in responses)
    ]
    if not remaining:
        return
    language = _administration_language(instrument.id, answers, bool(responses))
    translated = language != "en"
    answers.instrument_languages[instrument.id] = language
    instrument = translate_instrument(instrument, language)
    pack = load_language(language)
    title = pack.text(MODULE_TITLES.get(instrument.id, instrument.name))
    instructions = _instrument_instructions(instrument, answers, language)
    if navigation is None or instrument.id not in navigation.shown_sections:
        prompter.screen(title, instructions)
        prompter.pause(pack.text("Press any key to start."))
        if navigation is not None:
            navigation.shown_sections.add(instrument.id)
    if instrument.aggregation == "sum" and instrument.response_sets[0].values == frozenset({0, 1}):
        ask_checklist(instrument, responses, answers, prompter, save, navigation)
        return
    total = len(instrument.items)
    for number, item in enumerate(instrument.items, 1):
        if not pending(navigation, f"{instrument.id}:{item.id}", item.id in responses):
            continue
        response_set = instrument.response_set(item.response_set)
        choices = [(str(option.value), option.label) for option in response_set.options]
        hint = pack.text(ITEM_HINTS.get(instrument.id, ""))
        prompter.screen(progress_header(title, number, total), hint)
        text = item.text if translated else display_text(instrument.id, item.text)
        default = str(responses[item.id]) if item.id in responses else None
        configure_prompt(prompter, navigation, default)
        responses[item.id] = int(prompter.select(text, choices))
        configure_prompt(prompter, None, None)
        save(answers)
        if navigation is not None:
            navigation.advance()


def ask_checklist(
    instrument: Instrument,
    responses: dict[str, int],
    answers: Answers,
    prompter: Prompter,
    save: Callable[[Answers], None],
    navigation: QuestionNavigation | None = None,
) -> None:
    """Ask a check-the-boxes instrument in blocks of ten, saving after each block."""
    for start in range(0, len(instrument.items), 10):
        block = instrument.items[start : start + 10]
        key = f"{instrument.id}:{block[0].id}"
        if not pending(navigation, key, all(item.id in responses for item in block)):
            continue
        title = MODULE_TITLES.get(instrument.id, instrument.name)
        prompter.screen(progress_header(title, start + 1, len(instrument.items)), "")
        message = "Tick the activities you would like to do:"
        configure_prompt(
            prompter, navigation, [item.id for item in block if responses.get(item.id)]
        )
        checked = set(prompter.checkbox(message, [(item.id, item.text) for item in block]))
        configure_prompt(prompter, None, None)
        for item in block:
            responses[item.id] = 1 if item.id in checked else 0
        save(answers)
        if navigation is not None:
            navigation.advance()


def ask_scenarios(
    scenarios: tuple[SJTScenario, ...],
    answers: Answers,
    prompter: Prompter,
    save: Callable[[Answers], None],
    navigation: QuestionNavigation | None = None,
) -> None:
    """Ask the unanswered work scenarios."""
    remaining = [
        scenario
        for scenario in scenarios
        if pending(navigation, f"sjt:{scenario.id}", scenario.id in answers.sjt)
    ]
    if not remaining:
        return
    if navigation is None or "sjt" not in navigation.shown_sections:
        prompter.screen(
            "Work situations",
            "Short work scenarios. Pick what you would most likely do. There are no right "
            "answers; these are reflective prompts, not a validated test.",
        )
        prompter.pause("Press any key to start.")
        if navigation is not None:
            navigation.shown_sections.add("sjt")
    for number, scenario in enumerate(scenarios, 1):
        if not pending(navigation, f"sjt:{scenario.id}", scenario.id in answers.sjt):
            continue
        header = progress_header("Work situations", number, len(scenarios))
        prompter.screen(header, f"{scenario.title}\n\n{scenario.prompt}")
        configure_prompt(prompter, navigation, answers.sjt.get(scenario.id))
        answers.sjt[scenario.id] = prompter.select(
            "What would you most likely do?",
            [(option.id, option.text) for option in scenario.options],
        )
        configure_prompt(prompter, None, None)
        save(answers)
        if navigation is not None:
            navigation.advance()


def ask_preferences(
    preferences: tuple[Preference, ...],
    answers: Answers,
    prompter: Prompter,
    save: Callable[[Answers], None],
    navigation: QuestionNavigation | None = None,
) -> None:
    """Ask the unanswered collaboration preferences."""
    remaining = [
        preference
        for preference in preferences
        if pending(navigation, f"preference:{preference.id}", preference.id in answers.preferences)
    ]
    if not remaining:
        return
    for number, preference in enumerate(preferences, 1):
        if not pending(
            navigation, f"preference:{preference.id}", preference.id in answers.preferences
        ):
            continue
        prompter.screen(
            progress_header("Working with your agent", number, len(preferences)),
            "Your explicit choices. They override anything inferred from scores.",
        )
        configure_prompt(prompter, navigation, answers.preferences.get(preference.id))
        answers.preferences[preference.id] = prompter.select(
            preference.question, [(option.id, option.label) for option in preference.options]
        )
        configure_prompt(prompter, None, None)
        save(answers)
        if navigation is not None:
            navigation.advance()


def ask_known_results(
    answers: Answers,
    prompter: Prompter,
    save: Callable[[Answers], None],
    navigation: QuestionNavigation | None = None,
) -> None:
    """Optionally record results the user already has from proprietary tests.

    Each question gets its own screen, like the questionnaire items, so earlier prompts
    never pile up above the current one.
    """
    total = len(KNOWN_RESULT_QUESTIONS)
    for number, (key, question) in enumerate(KNOWN_RESULT_QUESTIONS.items(), start=1):
        if not pending(
            navigation, f"known:{key}", answers.known_results_done or key in answers.known_results
        ):
            continue
        prompter.screen(progress_header(KNOWN_RESULTS_TITLE, number, total), KNOWN_RESULTS_BODY)
        if navigation is not None:
            configure_prompt(prompter, navigation, None)
            choices = [("edit", "Enter or change answer")]
            if answers.known_results_done or key in answers.known_results:
                choices.insert(0, ("keep", "Keep saved answer"))
                saved = answers.known_results.get(key, "")
                if saved:
                    # The person's own text: shown exactly, never looked up for translation.
                    getattr(prompter, "show_raw", prompter.show)(saved)
            action = prompter.select(question + ":", choices)
            configure_prompt(prompter, None, None)
            if action == "keep":
                navigation.advance()
                continue
        value = clean_text(
            prompter.text(question + ":", KNOWN_RESULT_LIMITS[key]), KNOWN_RESULT_LIMITS[key]
        )
        # Empty values also record that this optional question was deliberately skipped.
        answers.known_results[key] = value
        save(answers)
        if navigation is not None:
            navigation.advance()
    answers.known_results_done = answers.known_results_done or all(
        key in answers.known_results for key in KNOWN_RESULT_QUESTIONS
    )
    save(answers)
