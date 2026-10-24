"""Orchestrate `make setup`, `make ego` and `make report`.

Interactive runs resume from out/answers.json and save after every answer. A run with
`--answers PATH` is fully non-interactive: the file must already be complete.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from persona_forge.answers import Answers, AnswersError, clean_text, load_answers, save_answers
from persona_forge.clean import clean_session
from persona_forge.egos import (
    CUSTOM_DIMENSIONS,
    CUSTOM_NAME_LIMIT,
    MAX_CUSTOM,
    load_presets,
    validate_ego_choices,
)
from persona_forge.files import DATA_DIR
from persona_forge.generate import Outputs, generate
from persona_forge.instruments import load_instrument_by_id
from persona_forge.languages import available_languages, load_language
from persona_forge.links import install
from persona_forge.polish import (
    PolishError,
    available_tools,
    diff,
    payload_for,
    run_polish,
    save_polished_profile,
)
from persona_forge.profile import Profile, accepted_statements, build_profile, statements_by_section
from persona_forge.questionnaire import (
    Prompter,
    SetupInterrupted,
    check_known_identifiers,
    missing_questionnaire_parts,
    run_questionnaire,
    show_notice,
)
from persona_forge.render_profile import render_profile_markdown
from persona_forge.session_ui import SessionPrompter, SetupPaused, SetupRestarted
from persona_forge.translations import validate_language

LOGGER = logging.getLogger(__name__)
ANSWERS_FILE = "answers.json"
ALIAS_HINT = (
    "Optional shell alias (add it yourself; persona-forge never edits shell files):\n"
    "  alias codex='codex -p pf-me'"
)
REVIEW_LABELS = [("yes", "Yes, that's me"), ("partly", "Partly"), ("no", "No, drop it")]


@dataclass(frozen=True)
class Paths:
    """Where answers and generated files live, and which home folder receives links."""

    out_dir: Path
    home: Path

    @property
    def answers(self) -> Path:
        """The resumable answers file."""
        return self.out_dir / ANSWERS_FILE


def ensure_out_dir(out_dir: Path) -> None:
    """Create out/ privately; refuse to use the shipped data folder by mistake."""
    if out_dir.resolve() == DATA_DIR.resolve() or DATA_DIR.resolve() in out_dir.resolve().parents:
        raise ValueError("the output folder cannot be inside data/")
    if not out_dir.exists():
        # Only a folder we create gets owner-only permissions; an existing folder is left as is.
        out_dir.mkdir(parents=True, mode=0o700)


def load_checked(path: Path) -> Answers:
    """Load answers and check every identifier against the shipped content."""
    answers = load_answers(path)
    check_known_identifiers(answers)
    if answers.egos is not None:
        validate_ego_choices(answers.egos)
    return answers


def run_review(
    answers: Answers, profile: Profile, prompter: Prompter, save: Callable[[Answers], None]
) -> None:
    """Ask yes / partly / no for each unreviewed statement, then the optional note."""
    if answers.review_done:
        return
    show_notice(
        prompter,
        "Review",
        "For each statement, choose whether it describes you. 'No' drops it; "
        "'Partly' keeps a softer version. Only what you accept reaches your agents.",
    )
    for statement in profile.statements:
        if statement.id in answers.review:
            continue
        answers.review[statement.id] = prompter.select(statement.text, REVIEW_LABELS)
        save(answers)
    if answers.wellbeing_opt_in and profile.wellbeing is not None:
        answers.wellbeing_tips = prompter.confirm(
            "Add a few practical working tips to your agent files? Only the tip text is added, "
            "never scores or questionnaire names.",
            default=False,
        )
    answers.note = clean_text(
        prompter.text("Anything your agent must know? (optional, one line)", 500), 500
    )
    answers.review_done = True
    save(answers)


def run_ego_step(
    answers: Answers, profile: Profile, prompter: Prompter, save: Callable[[Answers], None]
) -> None:
    """Choose preset egos, the complement and mirror egos, and craft custom ones."""
    if answers.egos and answers.egos.get("done"):
        return
    presets = load_presets()
    show_notice(
        prompter,
        "Alter egos",
        "Personas your agent can switch to: /output-style pf-<name> in Claude Code, "
        "codex -p pf-<name> in Codex.",
    )
    if answers.egos is None:
        answers.egos = {"custom": [], "done": False}
    choices = answers.egos
    if "presets" not in choices:
        choices["presets"] = prompter.checkbox(
            "Pick presets (space to toggle):",
            [(ego.id, f"{ego.name}: {ego.description}") for ego in presets.values()],
        )
        save(answers)
    accepted = statements_by_section(accepted_statements(profile, answers.review))
    if "complement" not in choices:
        choices["complement"] = bool(accepted["growth"]) and prompter.confirm(
            "Add a complement ego that gently counterbalances your growth points?", default=True
        )
        save(answers)
    if "mirror" not in choices:
        choices["mirror"] = prompter.confirm(
            "Add a mirror ego that drafts text in your voice?", default=True
        )
        save(answers)
    custom = choices.setdefault("custom", [])
    while len(custom) < MAX_CUSTOM:
        if "custom_draft" not in choices:
            if not prompter.confirm("Craft a custom ego?", default=False):
                break
            name = clean_text(
                prompter.text("Name for the custom ego:", CUSTOM_NAME_LIMIT), CUSTOM_NAME_LIMIT
            )
            choices["custom_draft"] = {"name": name}
            try:
                validate_ego_choices(choices)
            except AnswersError as error:
                prompter.show(f"That ego was not added: {error}")
                choices.pop("custom_draft")
                continue
            save(answers)
        entry = choices["custom_draft"]
        for dimension, spec in CUSTOM_DIMENSIONS.items():
            if dimension in entry:
                continue
            entry[dimension] = prompter.select(
                spec["question"], [(key, label) for key, (label, _) in spec["options"].items()]
            )
            save(answers)
        custom.append(entry)
        choices.pop("custom_draft")
        save(answers)
    choices["done"] = True
    validate_ego_choices(answers.egos)
    save(answers)


def _show_exact_text(prompter: Prompter, text: str) -> None:
    """Keep outgoing payload diffs verbatim, independently of the interface language."""
    show_raw = getattr(prompter, "show_raw", prompter.show)
    show_raw(text)


def offer_polish(answers: Answers, paths: Paths, prompter: Prompter) -> None:
    """Optionally polish the profile wording with a local AI CLI, after full disclosure."""
    tools = available_tools()
    if not tools:
        return
    if not prompter.confirm(
        "Polish the profile wording with an AI CLI? (optional, sends text)", default=False
    ):
        return
    tool = tools[0] if len(tools) == 1 else prompter.select("Which tool?", [(t, t) for t in tools])
    profile = build_profile(answers)
    template = render_profile_markdown(
        profile, statements_by_section(accepted_statements(profile, answers.review))
    )
    prompter.show(
        f"\nThis exact text would be sent to {tool} (no scores, no wellbeing data):\n\n"
        f"{payload_for(tool, template)}"
    )
    if not prompter.confirm("Send it?", default=False):
        return
    try:
        polished = run_polish(tool, template)
    except PolishError as error:
        prompter.show(f"Polish skipped: {error}. The template wording is kept.")
        return
    changes = diff(template, polished)
    if changes:
        _show_exact_text(prompter, changes)
    else:
        prompter.show("No changes suggested.")
    if prompter.confirm("Use the polished wording?", default=False):
        save_polished_profile(paths.out_dir, template, polished)


def display_folder(folder: Path) -> str:
    """Show a folder relative to the current directory when it is inside it."""
    resolved = folder.resolve()
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def finish(answers: Answers, paths: Paths, link: bool, today: date | None) -> Outputs:
    """Generate outputs, install links and print a summary."""
    outputs = generate(answers, paths.out_dir, today)
    pack = load_language(answers.questionnaire_language)
    LOGGER.info(
        pack.text("Generated {count} files in {path}", count=len(outputs.files), path=paths.out_dir)
    )
    for path in outputs.files:
        LOGGER.info("  %s", path.relative_to(paths.out_dir))
    if outputs.unreviewed:
        LOGGER.warning(
            pack.text(
                "{count} statements had no review entry and were kept as written.",
                count=outputs.unreviewed,
            )
        )
    if link:
        for line in install(paths.out_dir, paths.home):
            LOGGER.info(pack.text(line))
        LOGGER.info(pack.text(ALIAS_HINT))
    return outputs


def setup_non_interactive(
    answers_path: Path, paths: Paths, link: bool = True, today: date | None = None
) -> Outputs:
    """Generate everything from a complete answers file."""
    answers = load_checked(answers_path)
    missing = missing_questionnaire_parts(answers)
    if missing:
        raise AnswersError(f"the answers file is incomplete: {', '.join(missing)}")
    ensure_out_dir(paths.out_dir)
    if answers_path.resolve() != paths.answers.resolve():
        save_answers(paths.answers, answers)
    return finish(answers, paths, link, today)


def _load_session_answers(paths: Paths, questionnaire_language: str | None) -> Answers:
    """Load resumable answers and reject a language change before any UI is cleared."""
    if questionnaire_language is not None:
        validate_language(questionnaire_language)
    ensure_out_dir(paths.out_dir)
    answers = load_checked(paths.answers) if paths.answers.exists() else Answers()
    if questionnaire_language is not None:
        if paths.answers.exists() and questionnaire_language != answers.questionnaire_language:
            raise AnswersError(
                "cannot change the questionnaire language of a saved session; "
                "run `make clean` to back it up and start fresh"
            )
        answers.questionnaire_language = questionnaire_language

    return answers


def _check_saved_instrument_languages(answers: Answers) -> None:
    """Refuse to mix languages within an already-started instrument."""
    pack = load_language(answers.questionnaire_language)
    for instrument_id, language in answers.instrument_languages.items():
        count = len(answers.instruments.get(instrument_id, {}))
        total = len(load_instrument_by_id(instrument_id).items)
        if instrument_id in pack.instrument_ids and 0 < count < total and language != pack.code:
            raise AnswersError(
                pack.text(
                    "This instrument was started in another language. "
                    "Start a new session to change its wording."
                )
            )


def _start_terminal(prompter: Prompter, language: str) -> None:
    """Configure optional terminal hooks before displaying the first setup prompt."""
    set_language = getattr(prompter, "set_language", None)
    if callable(set_language):
        set_language(language)
    start_session = getattr(prompter, "start_session", None)
    if callable(start_session):
        start_session()


def _restore_setup_stage(session: SessionPrompter) -> None:
    """Select the progress stage for an already-complete questionnaire."""
    answers = session.answers
    if not answers.review_done:
        session.stage = "review"
        session.review_total = len(build_profile(answers).statements)
    elif not (answers.egos and answers.egos.get("done")):
        session.stage = "personas"
    else:
        session.stage = "generate"


def setup_interactive(
    paths: Paths,
    prompter: Prompter,
    link: bool = True,
    today: date | None = None,
    questionnaire_language: str | None = None,
) -> Outputs:
    """Run setup again after an explicitly confirmed session restart."""
    while True:
        try:
            return _setup_attempt(paths, prompter, link, today, questionnaire_language)
        except SetupRestarted:
            clean_session(paths.out_dir, paths.home)


def _setup_attempt(
    paths: Paths,
    prompter: Prompter,
    link: bool = True,
    today: date | None = None,
    questionnaire_language: str | None = None,
) -> Outputs:
    """Ask what is missing, review, craft egos, optionally polish, generate and link."""
    answers = _load_session_answers(paths, questionnaire_language)

    def save(current: Answers) -> None:
        save_answers(paths.answers, current)

    _check_saved_instrument_languages(answers)
    _start_terminal(prompter, answers.questionnaire_language)
    if not paths.answers.exists() and questionnaire_language is None:
        choices = [(code, load_language(code).name) for code in available_languages()]
        language = prompter.select("Choose your language:", choices)
        validate_language(language)
        answers.questionnaire_language = language
        set_language = getattr(prompter, "set_language", None)
        if callable(set_language):
            set_language(language)
    pack = load_language(answers.questionnaire_language)
    session = SessionPrompter(prompter, answers, save)
    pending = bool(missing_questionnaire_parts(answers))
    if not pending:
        _restore_setup_stage(session)
    try:
        session.welcome(resumed=paths.answers.exists())
        excluded = set(load_language("en").instrument_ids) - set(pack.instrument_ids)
        if excluded:
            session.show(
                "Language pack excludes English-only instruments: "
                + ", ".join(sorted(excluded))
                + "."
            )
        if paths.answers.exists():
            session.select(
                "Saved session found. Continue where you stopped?", [("continue", "Continue")]
            )
        session.stage = "questionnaire"
        run_questionnaire(answers, session, save)
        if pending:
            session.section_break()
        profile = build_profile(answers)
        session.stage = "review"
        session.review_total = len(profile.statements)
        pending = not answers.review_done
        run_review(answers, profile, session, save)
        if pending:
            session.section_break()
        session.stage = "personas"
        run_ego_step(answers, profile, session, save)
        session.stage = "generate"
        offer_polish(answers, paths, session)
        session.show_progress()
    except (SetupPaused, SetupInterrupted, KeyboardInterrupt):
        save(answers)
        raise
    session.forging()
    outputs = finish(answers, paths, link, today)
    personas = [(ego.id, ego.name) for ego in outputs.egos]
    session.finished(personas, len(outputs.files), display_folder(paths.out_dir))
    return outputs


def craft_egos(
    paths: Paths, prompter: Prompter, today: date | None = None, link: bool = True
) -> Outputs:
    """`make ego`: choose egos again, regenerate and relink."""
    if not paths.answers.exists():
        raise AnswersError("no answers yet; run `make setup` first")
    answers = load_checked(paths.answers)
    if missing_questionnaire_parts(answers) or not answers.review_done:
        raise AnswersError("setup is not finished; run `make setup` to complete it first")
    answers.egos = None
    run_ego_step(
        answers,
        build_profile(answers),
        prompter,
        lambda current: save_answers(paths.answers, current),
    )
    return finish(answers, paths, link, today)


def regenerate(paths: Paths, today: date | None = None) -> Outputs:
    """`make report`: regenerate outputs from saved answers without asking anything."""
    if not paths.answers.exists():
        raise AnswersError("no answers yet; run `make setup` first")
    answers = load_checked(paths.answers)
    missing = missing_questionnaire_parts(answers)
    if missing:
        raise AnswersError(f"setup is not finished ({', '.join(missing)}); run `make setup`")
    return generate(answers, paths.out_dir, today)
