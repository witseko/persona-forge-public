"""Show saved questionnaire progress and expose pause controls during interactive setup."""

from collections.abc import Callable, Sequence

from persona_forge.answers import Answers
from persona_forge.content import load_preferences
from persona_forge.flow import (
    DEPTHS,
    MODULE_TITLES,
    SECONDS_PER_ITEM,
    SECONDS_PER_PREFERENCE,
    SECONDS_PER_SCENARIO,
    WELLBEING_INSTRUMENTS,
    depth_instruments,
    depth_scenarios,
    estimated_minutes,
)
from persona_forge.instruments import load_instrument_by_id
from persona_forge.languages import load_language
from persona_forge.navigation import (
    BACK_ACTION,
    NEXT_ACTION,
    PAUSE_ACTION,
    RESTART_ACTION,
    QuestionMoved,
    QuestionNavigation,
)
from persona_forge.questionnaire import (
    KNOWN_RESULT_QUESTIONS,
    Prompter,
    missing_questionnaire_parts,
    show_notice,
)
from persona_forge.terminal_ui import Plan, PlanRow, SetupProgress, Summary

MOMENT_TEXT = {
    "welcome": "Let's forge your work profile.",
    "resume": "Welcome back{person_suffix}.",
    "resume_at": "Welcome back{person_suffix}. You stopped at {where}.",
    "question": "{title}, question {number} of {total}",
    "halfway": "Halfway there. A good moment for a break - your progress is saved.",
    "forging": "Forging your profile and personas...",
    "done": "Done{person_suffix}",
    "depth": "Depth",
    "files": "Files",
    "files_value": "{count} written to {folder}",
    "personas": "Your personas",
    "report": "open your private report",
    "ego": "change your personas",
}


class SetupPaused(Exception):
    """Raised after saving when the user explicitly chooses to continue later."""


class SetupRestarted(Exception):
    """Raised when the user confirms archiving this session and starting again."""


class SessionPrompter:
    """Wrap terminal prompts with progress calculated from saved answer state."""

    def __init__(
        self, prompter: Prompter, answers: Answers, save: Callable[[Answers], None]
    ) -> None:
        self.prompter = prompter
        self.answers = answers
        self.pack = load_language(answers.questionnaire_language)
        self.save = save
        self.stage = "questionnaire"
        self.navigation: QuestionNavigation | None = None
        self.review_total = 0
        self._plan_key: tuple[str, str] | None = None
        self._item_ids: dict[str, set[str]] = {}
        self._scenario_ids: set[str] = set()
        self._preference_ids = {preference.id for preference in load_preferences()}
        self._has_wellbeing = bool(self.pack.instrument_ids & set(WELLBEING_INSTRUMENTS))
        self._section: str | None = None
        self._first_done: int | None = None
        self._halfway_shown = False

    def _question_counts(self) -> tuple[int, int]:
        """Count answered questions, including known-result prompts and wellbeing consent."""
        answers = self.answers
        if self._plan_key != (answers.depth, answers.role):
            self._item_ids = {
                instrument.id: {item.id for item in instrument.items}
                for instrument in depth_instruments(answers.depth, self.pack.code)
            }
            self._scenario_ids = {
                scenario.id for scenario in depth_scenarios(answers.depth, answers.role)
            }
            self._plan_key = (answers.depth, answers.role)
        item_ids = dict(self._item_ids)
        if answers.wellbeing_opt_in:
            for instrument_id in WELLBEING_INSTRUMENTS:
                instrument = load_instrument_by_id(instrument_id)
                item_ids[instrument_id] = {item.id for item in instrument.items}
        total = sum(len(ids) for ids in item_ids.values())
        done = sum(
            len(set(answers.instruments.get(instrument_id, {})) & ids)
            for instrument_id, ids in item_ids.items()
        )
        # Optional known-result prompts and one wellbeing opt-in decision.
        known_count = len(KNOWN_RESULT_QUESTIONS)
        total += (
            len(self._scenario_ids)
            + len(self._preference_ids)
            + known_count
            + int(self._has_wellbeing)
        )
        done += len(set(answers.sjt) & self._scenario_ids)
        done += len(set(answers.preferences) & self._preference_ids)
        done += known_count if answers.known_results_done else len(answers.known_results)
        done += int(self._has_wellbeing and answers.wellbeing_opt_in is not None)
        return done, total

    def setup_progress(self) -> SetupProgress:
        """Describe the current setup stage and, when counting, how much is answered."""
        translate = self.pack.text
        labels = tuple(
            translate(label) for label in ("Questionnaire", "Review", "Personas", "Generate")
        )
        if self.stage == "review":
            done = len(self.answers.review)
            return SetupProgress(
                2,
                labels,
                "",
                done,
                self.review_total,
                translate("{done}/{total} statements reviewed", done=done, total=self.review_total),
            )
        if self.stage == "personas":
            return SetupProgress(3, labels)
        if self.stage == "generate":
            return SetupProgress(4, labels)
        if self.answers.depth not in DEPTHS or not self.answers.role:
            return SetupProgress(1, labels)
        done, total = self._question_counts()
        percent = int(100 * done / total)
        counter = translate(
            "{done}/{total} answered ({percent}%)", done=done, total=total, percent=percent
        )
        note = ""
        if self._has_wellbeing and self.answers.wellbeing_opt_in is None:
            note = translate("Optional wellbeing may add 7 questions.")
        return SetupProgress(1, labels, translate("Overall"), done, total, counter, note)

    def progress_text(self) -> str:
        """Describe overall questionnaire progress and the remaining setup stages."""
        state = self.setup_progress()
        names = {
            2: "profile review",
            3: "personas",
            4: "generate files",
        }
        if state.stage == 1:
            choosing = not state.total
            name = "choose questionnaire" if choosing else "questionnaire"
        else:
            name = names[state.stage]
        text = self.pack.text("Setup {stage}/4: {name}", stage=state.stage, name=name)
        if state.counter_label:
            filled = int(10 * state.done / state.total)
            bar = f"[{'#' * filled}{'-' * (10 - filled)}]"
            text += f" | {state.counter_label} {bar} {state.counter_text}"
        elif state.counter_text:
            text += f" | {state.counter_text}"
        if state.note:
            text += f"\n{state.note}"
        return text

    def show_progress(self) -> None:
        """Display progress: the stepper when the prompter draws one, else a text line."""
        state = self.setup_progress()
        self._maybe_halfway(state)
        progress = getattr(self.prompter, "progress", None)
        if callable(progress):
            progress(state)
        else:
            self.prompter.show(self.progress_text())

    def _moment(self, kind: str, text: str) -> None:
        """Show a display-only moment when the prompter supports it."""
        moment = getattr(self.prompter, "moment", None)
        if callable(moment):
            moment(kind, text)

    def _maybe_halfway(self, state: SetupProgress) -> None:
        """Note the halfway point once, only when this run crosses it."""
        if self.stage != "questionnaire" or not state.total or self._halfway_shown:
            return
        if self._first_done is None:
            self._first_done = state.done
        if self._first_done < state.total / 2 <= state.done:
            self._halfway_shown = True
            self._moment("halfway", self.pack.text(MOMENT_TEXT["halfway"]))

    def _name_suffix(self) -> str:
        """ ", Alex" when a name is saved, else nothing."""
        return f", {self.answers.name}" if self.answers.name else ""

    def resume_point(self) -> str:
        """Where a saved session continues, in words, or an empty string if unclear."""
        text = MOMENT_TEXT
        if self.stage != "questionnaire":
            labels = tuple(
                self.pack.text(label)
                for label in ("Questionnaire", "Review", "Personas", "Generate")
            )
            return {"review": labels[1], "personas": labels[2], "generate": labels[3]}[self.stage]
        missing = missing_questionnaire_parts(self.answers)
        if not missing or missing[0] in {"consent", "name", "role", "seniority", "depth"}:
            return ""
        part = missing[0]
        if part == "sjt":
            return self.pack.text("Work situations")
        if part == "preferences":
            return self.pack.text("Working with your agent")
        if part not in MODULE_TITLES:
            return ""
        instrument = load_instrument_by_id(part)
        done = len(self.answers.instruments.get(part, {}))
        return self.pack.text(
            text["question"],
            title=self.pack.text(MODULE_TITLES[part]),
            number=done + 1,
            total=len(instrument.items),
        )

    def welcome(self, resumed: bool) -> None:
        """Greet a new session, or say where a saved one continues."""
        text = MOMENT_TEXT
        if not resumed:
            self._moment("welcome", self.pack.text(text["welcome"]))
            return
        where = self.resume_point()
        name = self._name_suffix()
        line = (
            self.pack.text(text["resume_at"], person_suffix=name, where=where)
            if where
            else self.pack.text(text["resume"], person_suffix=name)
        )
        self._moment("resume", line)

    def forging(self) -> None:
        """Say that files are being generated."""
        self._moment("forging", self.pack.text(MOMENT_TEXT["forging"]))

    def finished(
        self, persona_names: Sequence[tuple[str, str]], file_count: int, folder: str
    ) -> None:
        """Show the finish screen when the prompter supports it."""
        summary = getattr(self.prompter, "summary", None)
        if not callable(summary):
            return
        text = MOMENT_TEXT
        facts = [
            (
                self.pack.text(text["files"]),
                self.pack.text(text["files_value"], count=file_count, folder=folder),
            )
        ]
        if self.answers.depth in DEPTHS:
            facts.insert(0, (self.pack.text(text["depth"]), DEPTHS[self.answers.depth].title))
        summary(
            Summary(
                self.pack.text(text["done"], person_suffix=self._name_suffix()),
                tuple(facts),
                self.pack.text(text["personas"]),
                tuple(persona_names),
                (
                    ("make report", self.pack.text(text["report"])),
                    ("make ego", self.pack.text(text["ego"])),
                ),
            )
        )

    def module_plan(self) -> Plan:
        """The questionnaire plan: one row per module with its size, time and status."""
        translate = self.pack.text
        answers = self.answers
        modules: list[tuple[str, int, int, int]] = []
        instruments = list(depth_instruments(answers.depth, self.pack.code))
        if answers.wellbeing_opt_in:
            instruments += [load_instrument_by_id(item) for item in WELLBEING_INSTRUMENTS]
        for instrument in instruments:
            ids = {item.id for item in instrument.items}
            done = len(set(answers.instruments.get(instrument.id, {})) & ids)
            title = translate(MODULE_TITLES.get(instrument.id, instrument.name))
            modules.append((title, len(ids), done, len(ids) * SECONDS_PER_ITEM))
        scenarios = {scenario.id for scenario in depth_scenarios(answers.depth, answers.role)}
        modules.append(
            (
                translate("Work situations"),
                len(scenarios),
                len(set(answers.sjt) & scenarios),
                len(scenarios) * SECONDS_PER_SCENARIO,
            )
        )
        modules.append(
            (
                translate("Working with your agent"),
                len(self._preference_ids),
                len(set(answers.preferences) & self._preference_ids),
                len(self._preference_ids) * SECONDS_PER_PREFERENCE,
            )
        )
        rows = []
        for title, total, done, seconds in modules:
            if done >= total:
                state, status = "done", translate("done")
            elif done:
                state, status = "active", translate("{done} of {total}", done=done, total=total)
            else:
                state, status = "todo", translate("to do")
            minutes = f"{max(1, round(seconds / 60))} {translate('min')}"
            rows.append(PlanRow(title, total, minutes, status, state))
        caption = translate(
            "{depth} depth · about {minutes} min",
            depth=DEPTHS[answers.depth].title,
            minutes=estimated_minutes(answers.depth, len(self._preference_ids), self.pack.code),
        )
        if self._has_wellbeing and answers.wellbeing_opt_in is None:
            caption += translate(" · optional wellbeing adds 7 questions")
        return Plan(
            tuple(translate(label) for label in ("Module", "Questions", "Time", "Status")),
            tuple(rows),
            caption,
        )

    def _stop(self) -> None:
        """Save the current state before returning control to the shell."""
        self.save(self.answers)
        raise SetupPaused

    def show(self, text: str) -> None:
        """Display informational text unchanged."""
        self.prompter.show(self.pack.text(text))

    def show_raw(self, text: str) -> None:
        """Show an exact outgoing payload or diff, keeping its reviewed content intact."""
        self.prompter.show(text)

    def notice(self, title: str, body: str) -> None:
        """Display a titled notice, framed when the terminal prompter supports it."""
        show_notice(self.prompter, self.pack.text(title), self.pack.text(body))

    def screen(self, header: str, body: str) -> None:
        """Keep section progress; overall progress is shown below it before the question."""
        section = header.split("   [", 1)[0]
        if (
            self.stage == "questionnaire"
            and self._section is not None
            and section != self._section
            and not (self.navigation is not None and self.navigation.moving)
        ):
            self.section_break()
        first = self._section is None
        self._section = section
        self.prompter.screen(self.pack.text(header), self.pack.text(body))
        plan = getattr(self.prompter, "plan", None)
        if first and callable(plan) and self.stage == "questionnaire" and self._has_plan():
            plan(self.module_plan())

    def _has_plan(self) -> bool:
        """A plan exists once the depth and role are chosen."""
        return self.answers.depth in DEPTHS and bool(self.answers.role)

    def pause(self, message: str) -> None:
        """Wait at an instrument's instruction screen."""
        self.show_progress()
        self.prompter.pause(self.pack.text(message))

    def question_navigation(
        self, navigation: QuestionNavigation | None, default: str | list[str] | None
    ) -> None:
        """Enable question navigation only while an editable question is on screen."""
        self.navigation = navigation
        configure = getattr(self.prompter, "question_navigation", None)
        if callable(configure):
            configure(navigation, default)

    def _navigation_choices(self) -> list[tuple[str, str]]:
        """Keep first/last boundaries visible through only available actions."""
        if self.navigation is None:
            return []
        choices = []
        if self.navigation.position > 0:
            choices.append((BACK_ACTION, self.pack.text("Back to previous question")))
        if self.navigation.position < len(self.navigation.keys):
            choices.append((NEXT_ACTION, self.pack.text("Next question (keep saved answer)")))
        return choices

    def _move(self, result: str) -> None:
        """Consume navigation controls without storing them as answers."""
        if self.navigation is not None and result in (BACK_ACTION, NEXT_ACTION):
            raise QuestionMoved(-1 if result == BACK_ACTION else 1)

    def _choices(self, choices: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
        """Append a control action that is intercepted before any answer is stored."""
        return [
            *((value, self.pack.text(label)) for value, label in choices),
            *self._navigation_choices(),
            (PAUSE_ACTION, self.pack.text("Pause and continue later")),
            (RESTART_ACTION, self.pack.text("Start over")),
        ]

    def _restart(self) -> None:
        """Confirm before archiving personal answers and generated files."""
        if self.prompter.confirm(
            self.pack.text(
                "Start over? Your current session will be backed up and setup will restart."
            ),
            default=False,
        ):
            self.save(self.answers)
            raise SetupRestarted

    def select(self, message: str, choices: Sequence[tuple[str, str]]) -> str:
        """Intercept session controls before recording a single-choice answer."""
        self.show_progress()
        while True:
            result = self.prompter.select(self.pack.text(message), self._choices(choices))
            self._move(result)
            if result == PAUSE_ACTION:
                self._stop()
            if result != RESTART_ACTION:
                return result
            self._restart()

    def checkbox(self, message: str, choices: Sequence[tuple[str, str]]) -> list[str]:
        """Intercept session controls before committing a checkbox block."""
        self.show_progress()
        while True:
            result = self.prompter.checkbox(self.pack.text(message), self._choices(choices))
            for value in result:
                self._move(value)
            if PAUSE_ACTION in result:
                self._stop()
            if RESTART_ACTION not in result:
                return result
            self._restart()

    def text(self, message: str, limit: int) -> str:
        """Show progress before free text; Ctrl-C remains available at these prompts."""
        self.show_progress()
        return self.prompter.text(self.pack.text(message), limit)

    def confirm(self, message: str, default: bool) -> bool:
        """Show progress before yes/no questions; Ctrl-C remains available."""
        self.show_progress()
        return self.prompter.confirm(self.pack.text(message), default)

    def section_break(self) -> None:
        """Offer a break between sections, with continue selected by default."""
        section_done = getattr(self.prompter, "section_done", None)
        if callable(section_done):
            labels = tuple(
                self.pack.text(label)
                for label in ("Questionnaire", "Review", "Personas", "Generate")
            )
            stage_titles = {"review": labels[1], "personas": labels[2], "generate": labels[3]}
            title = stage_titles.get(self.stage, self._section or labels[0])
            section_done(self.pack.text(title))
        self.select(
            "Section complete. Continue?",
            [("continue", "Continue")],
        )
