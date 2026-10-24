"""`make settings`: choose the active profile and language, link, retake or copy sessions.

The menu replaces the old PROFILE and QUESTIONNAIRE_LANGUAGE variables. Every choice is
saved in the private settings file, and other commands read it from there.
"""

from collections.abc import Callable
from pathlib import Path

from persona_forge.answers import load_answers
from persona_forge.clean import clean_session
from persona_forge.languages import available_languages, load_language
from persona_forge.links import install, status, uninstall
from persona_forge.profiles import create_profile, list_profiles, preserve_legacy, profile_directory
from persona_forge.questionnaire import Prompter, show_notice
from persona_forge.settings import Settings, load_settings, save_settings

ASK_LANGUAGE = "__ask__"
BACK = "__back__"
NEW_PROFILE = "__new__"


def active_profile(root: Path) -> str | None:
    """The saved active profile, if it still exists."""
    profile = load_settings(root).profile
    return profile if profile in list_profiles(root) else None


def is_linked(directory: Path, home: Path) -> bool:
    """Whether this profile's files are the ones linked into the agents."""
    return any(line.startswith("linked ") for line in status(directory, home))


def _language_name(code: str | None) -> str:
    """A language's display name, or how setup behaves when none is chosen."""
    return load_language(code).name if code else "Ask when a questionnaire starts"


def _saved_language(directory: Path) -> str | None:
    """The language a profile's saved answers use, if it has any."""
    answers = directory / "answers.json"
    return load_answers(answers).questionnaire_language if answers.is_file() else None


def _summary(root: Path, home: Path, settings: Settings, message: str) -> str:
    """The bullet list shown at the top of the settings screen."""
    profile = active_profile(root)
    lines = [f"- Profile: {profile or 'not chosen yet'}"]
    if profile:
        directory = profile_directory(root, profile)
        if is_linked(directory, home):
            lines[0] += " (linked to your agents)"
        saved = _saved_language(directory)
        if saved and saved != settings.language:
            lines.append(
                f"- This profile's answers are in {_language_name(saved)}. "
                "Retake its questionnaire to switch language."
            )
    lines.append(f"- Language for new questionnaires: {_language_name(settings.language)}")
    text = "\n".join(lines)
    return f"{text}\n\n{message}" if message else text


def _choose_profile(root: Path, prompter: Prompter, settings: Settings) -> str:
    """Pick a saved profile or create one, and make it active."""
    choices = [(name, name) for name in list_profiles(root)]
    choices += [(NEW_PROFILE, "New profile"), (BACK, "Back")]
    selected = prompter.select("Which profile should be active?", choices)
    if selected == BACK:
        return ""
    if selected == NEW_PROFILE:
        selected = prompter.text("Profile name (lowercase letters, digits and hyphens):", 64)
        create_profile(root, selected)
    save_settings(root, Settings(selected, settings.language))
    return f"Active profile: {selected}."


def _choose_language(root: Path, prompter: Prompter, settings: Settings) -> str:
    """Pick the language used by new questionnaires and retakes."""
    choices = [(code, load_language(code).name) for code in available_languages()]
    choices += [(ASK_LANGUAGE, "Ask when a questionnaire starts"), (BACK, "Back")]
    selected = prompter.select("Language for new questionnaires:", choices)
    if selected == BACK:
        return ""
    language = None if selected == ASK_LANGUAGE else selected
    save_settings(root, Settings(settings.profile, language))
    return f"Language for new questionnaires: {_language_name(language)}."


def _preserve(root: Path, prompter: Prompter) -> str:
    """Copy the original single-person session into a new named profile."""
    name = prompter.text("Name for the copied profile:", 64)
    preserve_legacy(root, name)
    return f"Original session copied to profile {name}; the original files are kept."


def run_settings_menu(
    root: Path,
    home: Path,
    prompter: Prompter,
    retake: Callable[[Path, str | None], None],
) -> None:
    """Show settings until the person chooses Done. `retake` restarts one profile's setup."""
    message = ""
    while True:
        settings = load_settings(root)
        profile = active_profile(root)
        show_notice(prompter, "Settings", _summary(root, home, settings, message))
        message = ""
        choices = [
            ("profile", f"Profile: {profile or 'choose one'}"),
            ("language", f"Language: {_language_name(settings.language)}"),
        ]
        directory = profile_directory(root, profile) if profile else None
        started = directory is not None and (directory / "answers.json").is_file()
        if directory is not None:
            if is_linked(directory, home):
                choices.append(("unlink", "Unlink this profile from your agents"))
            elif (directory / "profile.json").is_file():
                choices.append(("link", "Link this profile to your agents"))
            choices.append(
                ("retake", "Retake this profile's questionnaire")
                if started
                else ("retake", "Start this profile's questionnaire")
            )
        if (root / "answers.json").is_file():
            choices.append(("preserve", "Copy the original session into a new profile"))
        choices.append(("done", "Done"))
        action = prompter.select("What would you like to change?", choices)
        try:
            if action == "done":
                return
            if action == "profile":
                message = _choose_profile(root, prompter, settings)
            elif action == "language":
                message = _choose_language(root, prompter, settings)
            elif action == "preserve":
                message = _preserve(root, prompter)
            elif action == "link" and directory is not None:
                install(directory, home)
                message = f"Linked {profile} to your agents."
            elif action == "unlink" and directory is not None:
                uninstall(directory, home)
                message = f"Unlinked {profile} from your agents."
            elif action == "retake" and directory is not None:
                if not started or prompter.confirm(
                    "Archive this profile's previous results and take the questionnaire again?",
                    default=False,
                ):
                    clean_session(directory, home)
                    retake(directory, settings.language)
                    return
        except ValueError as error:
            message = f"Not changed: {error}"
