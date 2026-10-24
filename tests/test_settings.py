"""Settings file and the `make settings` menu."""

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from test_questionnaire import ScriptedPrompter

from persona_forge.settings import Settings, load_settings, save_settings
from persona_forge.settings_menu import run_settings_menu

FIXTURE = Path(__file__).parent / "fixtures" / "answers_standard.json"


def test_settings_round_trip_privately(tmp_path: Path) -> None:
    """Settings hold only a profile name and a language, stored owner-only."""
    root = tmp_path / "out"
    assert load_settings(root) == Settings()
    save_settings(root, Settings("friend", "uk"))
    assert load_settings(root) == Settings("friend", "uk")
    stored = json.loads((root / "settings.json").read_text())
    assert stored == {"version": 1, "profile": "friend", "language": "uk"}
    assert (root / "settings.json").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    "content",
    [
        {"profile": "../escape"},
        {"profile": 5},
        {"language": "fr"},
        {"language": "../../etc"},
        {"answers": {}},
        [],
    ],
)
def test_bad_settings_are_rejected(tmp_path: Path, content: object) -> None:
    """A hand-edited file cannot escape the profiles folder or name a missing plugin."""
    root = tmp_path / "out"
    root.mkdir()
    (root / "settings.json").write_text(json.dumps(content))
    with pytest.raises(ValueError):
        load_settings(root)


def test_symlinked_settings_are_refused(tmp_path: Path) -> None:
    """Settings must be a regular file inside the output folder."""
    root = tmp_path / "out"
    root.mkdir()
    target = tmp_path / "elsewhere.json"
    target.write_text("{}")
    (root / "settings.json").symlink_to(target)
    with pytest.raises(ValueError):
        load_settings(root)


class Menu(ScriptedPrompter):
    """Pick menu actions in order; answer text prompts from a list."""

    def __init__(self, actions: list[str], texts: Sequence[str] = (), confirm: bool = True):
        super().__init__(confirm=confirm)
        self.actions = iter(actions)
        self.texts = iter(texts)
        self.notices: list[str] = []
        self.offered: list[list[str]] = []

    def notice(self, title: str, body: str) -> None:
        self.notices.append(body)

    def select(self, message: str, choices: Sequence[tuple[str, str]]) -> str:
        self.offered.append([value for value, _ in choices])
        return next(self.actions)

    def text(self, message: str, limit: int) -> str:
        return next(self.texts)


def test_menu_creates_a_profile_and_sets_language(tmp_path: Path) -> None:
    """New profile and language choices are saved for later commands."""
    root, home = tmp_path / "out", tmp_path / "home"
    menu = Menu(["profile", "__new__", "language", "uk", "done"], texts=["friend"])
    run_settings_menu(root, home, menu, lambda directory, language: None)
    assert load_settings(root) == Settings("friend", "uk")
    assert (root / "profiles/friend").is_dir()
    assert "Language for new questionnaires: Українська" in menu.notices[-1]


def test_menu_reports_bad_profile_names_without_changes(tmp_path: Path) -> None:
    """A rejected name leaves settings as they were and says why."""
    root, home = tmp_path / "out", tmp_path / "home"
    menu = Menu(["profile", "__new__", "done"], texts=["../bad"])
    run_settings_menu(root, home, menu, lambda directory, language: None)
    assert load_settings(root) == Settings()
    assert "Not changed:" in menu.notices[-1]


def test_menu_links_unlinks_and_retakes_the_active_profile(tmp_path: Path) -> None:
    """Link and unlink act on the active profile; retake archives, then restarts setup."""
    from persona_forge.cli import main

    root, home = tmp_path / "out", tmp_path / "home"
    common = ["--out", str(root), "--home", str(home)]
    assert main(["setup", *common, "--profile", "friend", "--answers", str(FIXTURE)]) == 0
    save_settings(root, Settings("friend", "uk"))
    menu = Menu(["link", "unlink", "done"])
    run_settings_menu(root, home, menu, lambda directory, language: None)
    assert "link" in menu.offered[0] and "unlink" in menu.offered[1]
    assert not (home / ".codex/pf-me.config.toml").is_symlink()

    retakes: list[tuple[Path, str | None]] = []
    menu = Menu(["retake"])
    run_settings_menu(
        root, home, menu, lambda directory, language: retakes.append((directory, language))
    )
    assert retakes == [(root / "profiles/friend", "uk")]
    assert not (root / "profiles/friend/answers.json").exists()
    assert (root / "profiles/friend/backups").is_dir()


def test_declined_retake_keeps_answers(tmp_path: Path) -> None:
    """Saying no to the confirmation changes nothing."""
    from persona_forge.cli import main

    root, home = tmp_path / "out", tmp_path / "home"
    common = ["--out", str(root), "--home", str(home)]
    assert main(["setup", *common, "--profile", "friend", "--answers", str(FIXTURE)]) == 0
    save_settings(root, Settings("friend", None))
    before = (root / "profiles/friend/answers.json").read_bytes()
    run_settings_menu(root, home, Menu(["retake", "done"], confirm=False), lambda d, lang: None)
    assert (root / "profiles/friend/answers.json").read_bytes() == before


def test_commands_use_the_active_profile_without_asking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once a profile is active, setup and other commands use it without a picker."""
    from persona_forge import cli

    root, home = tmp_path / "out", tmp_path / "home"
    assert (
        cli.main(
            [
                "setup",
                "--out",
                str(root),
                "--home",
                str(home),
                "--profile",
                "friend",
                "--answers",
                str(FIXTURE),
            ]
        )
        == 0
    )
    save_settings(root, Settings("friend", None))
    monkeypatch.setattr(cli, "DEFAULT_OUT", root)

    class NoPicker(ScriptedPrompter):
        def select(self, message: str, choices: Sequence[tuple[str, str]]) -> str:
            assert message != "Whose profile?"
            return super().select(message, choices)

    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: NoPicker())
    assert cli.main(["link", "--home", str(home)]) == 0
    assert (home / ".codex/pf-me.config.toml").resolve().is_relative_to(root / "profiles/friend")


def test_first_profile_choice_is_saved_as_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one-time picker saves its answer, so the next command does not ask again."""
    from persona_forge import cli

    root, home = tmp_path / "out", tmp_path / "home"

    class NewPerson(ScriptedPrompter):
        def select(self, message: str, choices: Sequence[tuple[str, str]]) -> str:
            if message == "Whose profile?":
                return "__new__"
            return super().select(message, choices)

        def text(self, message: str, limit: int) -> str:
            return "friend" if message.startswith("Profile name") else super().text(message, limit)

    monkeypatch.delenv("ANSWERS", raising=False)
    monkeypatch.setattr(cli, "DEFAULT_OUT", root)
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: NewPerson(stop_after=1))
    assert cli.main(["setup", "--home", str(home)]) == 0
    assert load_settings(root).profile == "friend"


def test_new_profile_offers_start_and_no_link(tmp_path: Path) -> None:
    """A profile without results can start its questionnaire but has nothing to link."""
    root, home = tmp_path / "out", tmp_path / "home"
    save_settings(root, Settings(None, None))
    (root / "profiles/friend").mkdir(parents=True)
    save_settings(root, Settings("friend", None))
    started: list[Path] = []
    menu = Menu(["retake"], confirm=False)
    run_settings_menu(root, home, menu, lambda directory, language: started.append(directory))
    assert "link" not in menu.offered[0]
    assert started == [root / "profiles/friend"]
