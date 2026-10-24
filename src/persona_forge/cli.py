"""Command line entry point: setup, settings, ego, report, link, unlink and status."""

import argparse
import logging
import os
import webbrowser
from collections.abc import Sequence
from pathlib import Path

from persona_forge.answers import AnswersError
from persona_forge.clean import clean_session
from persona_forge.content import ContentError
from persona_forge.files import PROJECT_ROOT, DataFileError
from persona_forge.instruments import InstrumentValidationError
from persona_forge.languages import available_languages, load_language
from persona_forge.links import install, status, uninstall
from persona_forge.profiles import create_profile, list_profiles, preserve_legacy, profile_directory
from persona_forge.questionnaire import (
    QuestionaryPrompter,
    SetupInterrupted,
    missing_questionnaire_parts,
)
from persona_forge.session_ui import SetupPaused
from persona_forge.settings import Settings, load_settings, save_settings
from persona_forge.settings_menu import active_profile, run_settings_menu
from persona_forge.setup import (
    Paths,
    craft_egos,
    load_checked,
    regenerate,
    setup_interactive,
    setup_non_interactive,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_OUT = PROJECT_ROOT / "out"
EXPECTED_ERRORS = (AnswersError, ContentError, DataFileError, InstrumentValidationError, ValueError)


def build_parser() -> argparse.ArgumentParser:
    """Describe the commands. Paths are plain data; nothing is executed from them."""
    parser = argparse.ArgumentParser(
        prog="persona-forge",
        description="Local work profiles and coding-agent personas.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def add_common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--out", type=Path, default=None, help=argparse.SUPPRESS)
        # Scripts and tests only; people choose the active profile in `make settings`.
        command.add_argument("--profile", default=None, help=argparse.SUPPRESS)
        command.add_argument(
            "--home", type=Path, default=None, help="Override the home folder for testing"
        )

    setup = commands.add_parser(
        "setup", help="Run or resume the questionnaire, then generate and link"
    )
    setup.add_argument(
        "--answers",
        type=Path,
        default=Path(os.environ["ANSWERS"]) if os.environ.get("ANSWERS") else None,
        help="Use a complete answers file instead of asking (also read from $ANSWERS)",
    )
    setup.add_argument("--no-link", action="store_true", help="Generate files without linking them")
    # Scripts and tests only; people choose the language in `make settings`.
    setup.add_argument(
        "--questionnaire-language",
        "--language",
        choices=available_languages(),
        default=None,
        help=argparse.SUPPRESS,
    )
    add_common(setup)
    for name, description in (
        ("settings", "Choose the active profile and language, link, retake or copy sessions"),
        ("ego", "Craft or change alter egos, regenerate and relink"),
        ("report", "Regenerate outputs and open the HTML report"),
        ("link", "Install generated configuration links"),
        ("unlink", "Remove this project's configuration links"),
        ("status", "Show progress, generated output and link status"),
        ("clean", "Back up the session and remove managed links so setup can start fresh"),
        ("languages", "List and validate installed language plugins"),
        ("profiles", "List saved profiles"),
        ("retake", "Archive this profile's results and start its questionnaire again"),
        ("preserve", "Copy the original session into a named profile"),
    ):
        command = commands.add_parser(name, help=description)
        add_common(command)
        if name == "retake":
            command.add_argument("--yes", action="store_true", help="Confirm archiving old results")
        if name == "report":
            command.add_argument("--no-open", action="store_true", help="Do not open a browser")
    return parser


def _print_actions(actions: Sequence[str]) -> None:
    """Print the actions returned by link and reset operations."""
    for line in actions:
        LOGGER.info(line)


def _list_languages() -> None:
    """Validate each installed plugin and report its instrument coverage."""
    from persona_forge.instruments import load_instrument_by_id
    from persona_forge.translations import translate_instrument

    for code in available_languages():
        pack = load_language(code)
        for instrument_id in pack.instrument_ids:
            translate_instrument(load_instrument_by_id(instrument_id), code)
        LOGGER.info("%s: %s (%d)", code, pack.name, len(pack.instrument_ids))


def _run_setup(arguments: argparse.Namespace, paths: Paths) -> None:
    """Route interactive setup or generation from an already completed answers file.

    A new interactive session uses the language from settings, unless a flag chose one.
    """
    if arguments.answers is not None:
        if arguments.questionnaire_language is not None:
            raise ValueError("set questionnaire_language in the answers file instead")
        setup_non_interactive(
            arguments.answers, paths, link=not arguments.no_link and arguments.profile is None
        )
        return
    language = arguments.questionnaire_language
    if language is None and not paths.answers.exists():
        language = load_settings(arguments.settings_root).language
    setup_interactive(
        paths,
        QuestionaryPrompter(),
        link=not arguments.no_link and arguments.profile is None,
        questionnaire_language=language,
    )


def _run_report(arguments: argparse.Namespace, paths: Paths) -> None:
    """Regenerate the report and open it only when requested."""
    regenerate(paths)
    report = (paths.out_dir / "report.html").resolve()
    LOGGER.info("Report: %s", report)
    if not arguments.no_open:
        webbrowser.open(report.as_uri())


def _show_status(paths: Paths) -> None:
    """Describe saved questionnaire progress and configuration links."""
    if paths.answers.exists():
        missing = missing_questionnaire_parts(load_checked(paths.answers))
        LOGGER.info(
            "Questionnaire: %s", "complete" if not missing else "missing " + ", ".join(missing)
        )
    else:
        LOGGER.info("Questionnaire: not started")
    _print_actions(status(paths.out_dir, paths.home))


def _choose_profile(root: Path, allow_new: bool = True) -> str:
    """Choose a saved person or create a separate session before setup starts."""
    prompter = QuestionaryPrompter()
    choices = [(name, name) for name in list_profiles(root)]
    if allow_new:
        choices.append(("__new__", "New person / new profile"))
    if not choices:
        raise ValueError("no profiles yet; run `make setup` first")
    selected = prompter.select("Whose profile?", choices)
    if selected != "__new__":
        return selected
    name = prompter.text("Profile name (lowercase letters, digits and hyphens):", 64)
    create_profile(root, name)
    return name


def _resolve_paths(arguments: argparse.Namespace) -> Paths:
    """Use an explicit profile, else the active one from settings, else ask once and save it."""
    root = arguments.out or DEFAULT_OUT
    arguments.settings_root = root
    interactive_commands = {"setup", "ego", "report", "link", "clean", "retake"}
    if (
        arguments.command in interactive_commands
        and arguments.out is None
        and arguments.profile is None
        and not getattr(arguments, "answers", None)
    ):
        arguments.profile = active_profile(root)
        if arguments.profile is None:
            arguments.profile = _choose_profile(root, allow_new=arguments.command == "setup")
            settings = load_settings(root)
            save_settings(root, Settings(arguments.profile, settings.language))
    if arguments.profile is not None:
        directory = profile_directory(root, arguments.profile)
        if arguments.command == "setup" and not directory.exists():
            create_profile(root, arguments.profile)
    else:
        directory = root
    arguments.out = directory
    return Paths(directory, arguments.home or Path.home())


def _run_profile_command(arguments: argparse.Namespace, paths: Paths) -> None:
    """List profiles, preserve the original session or safely retake one profile."""
    root = arguments.settings_root
    if arguments.command == "profiles":
        names = list_profiles(root)
        active = active_profile(root)
        for name in names:
            directory = profile_directory(root, name)
            linked = any(line.startswith("linked ") for line in status(directory, paths.home))
            state = "linked" if linked else "unlinked"
            LOGGER.info("%s (%s%s)", name, state, ", active" if name == active else "")
        if not names:
            LOGGER.info("No named profiles yet; run `make setup`.")
        return
    if arguments.command == "preserve" and not arguments.profile:
        arguments.profile = QuestionaryPrompter().text("Name for the copied profile:", 64)
    if not arguments.profile:
        raise ValueError("choose an active profile in `make settings` first")
    if arguments.command == "preserve":
        preserve_legacy(root, arguments.profile)
        LOGGER.info(
            "Original session copied to profile %s; original files kept.", arguments.profile
        )
        return
    if not arguments.yes and not QuestionaryPrompter().confirm(
        "Archive this profile's previous results and take the questionnaire again?", default=False
    ):
        return
    _print_actions(clean_session(paths.out_dir, paths.home))
    language = load_settings(root).language
    setup_interactive(paths, QuestionaryPrompter(), link=False, questionnaire_language=language)


def _run_settings(arguments: argparse.Namespace, paths: Paths) -> None:
    """Open the settings menu; a retake from it restarts that profile's setup."""
    prompter = QuestionaryPrompter()

    def retake(directory: Path, language: str | None) -> None:
        arguments.setup_started = True
        setup_interactive(
            Paths(directory, paths.home), prompter, link=False, questionnaire_language=language
        )

    run_settings_menu(arguments.settings_root, paths.home, prompter, retake)


def run(arguments: argparse.Namespace) -> int:
    """Dispatch one command and return its exit status."""
    paths = _resolve_paths(arguments)
    command = arguments.command
    if command == "settings":
        _run_settings(arguments, paths)
    elif command in {"profiles", "preserve", "retake"}:
        _run_profile_command(arguments, paths)
    elif command == "languages":
        _list_languages()
    elif command == "setup":
        _run_setup(arguments, paths)
    elif command == "ego":
        craft_egos(paths, QuestionaryPrompter(), link=arguments.profile is None)
    elif command == "report":
        _run_report(arguments, paths)
    elif command == "link":
        _print_actions(install(paths.out_dir, paths.home))
    elif command == "unlink":
        _print_actions(uninstall(paths.out_dir, paths.home))
    elif command == "clean":
        _print_actions(clean_session(paths.out_dir, paths.home))
    elif command == "status":
        _show_status(paths)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run the command and turn expected errors into short messages."""
    arguments = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("persona_forge").setLevel(logging.INFO)
    try:
        return run(arguments)
    except (SetupPaused, SetupInterrupted, KeyboardInterrupt):
        if arguments.command == "settings" and not getattr(arguments, "setup_started", False):
            return 0
        language = arguments.questionnaire_language if arguments.command == "setup" else "en"
        out_dir = arguments.out or DEFAULT_OUT
        if language is None and (out_dir / "answers.json").is_file():
            language = load_checked(out_dir / "answers.json").questionnaire_language
        LOGGER.info(
            load_language(language or "en").text(
                "Paused. Your progress is saved; run `make setup` to continue."
            )
        )
        return 0
    except EXPECTED_ERRORS as error:
        LOGGER.error("Error: %s", error)
        return 1
