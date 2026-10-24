"""Separate people, preserve previous results and switch only project-owned links."""

from pathlib import Path

import pytest
from test_questionnaire import ScriptedPrompter

from persona_forge.cli import main
from persona_forge.profiles import create_profile, list_profiles, preserve_legacy, profile_directory

FIXTURE = Path(__file__).parent / "fixtures" / "answers_standard.json"


def command(root: Path, home: Path, action: str, *arguments: str) -> int:
    """Run the CLI with isolated storage and agent configuration."""
    return main([action, "--out", str(root), "--home", str(home), *arguments])


def test_profiles_keep_answers_separate_and_switch_all_personas(tmp_path: Path) -> None:
    """Guest setup never links; explicit switching removes obsolete personas."""
    root, home = tmp_path / "out", tmp_path / "home"
    for name in ("alex", "sam"):
        assert command(root, home, "setup", "--profile", name, "--answers", str(FIXTURE)) == 0
    assert not home.exists()
    original = (root / "profiles/alex/answers.json").read_bytes()
    assert command(root, home, "link", "--profile", "alex") == 0
    obsolete = root / "profiles/alex/codex/pf-extra.config.toml"
    obsolete.write_text("old persona")
    extra_link = home / ".codex/pf-extra.config.toml"
    extra_link.symlink_to(obsolete)
    config = home / ".codex/config.toml"
    config.write_text("user settings")
    foreign = home / ".codex/pf-foreign.config.toml"
    foreign.symlink_to(config)
    assert command(root, home, "link", "--profile", "sam") == 0
    assert not extra_link.is_symlink()
    assert (home / ".codex/pf-me.config.toml").resolve().is_relative_to(root / "profiles/sam")
    assert command(root, home, "unlink", "--profile", "alex") == 0
    assert (home / ".codex/pf-me.config.toml").is_symlink()
    assert command(root, home, "unlink") == 0
    assert not (home / ".codex/pf-me.config.toml").is_symlink()
    assert foreign.is_symlink() and config.read_text() == "user settings"
    assert (root / "profiles/alex/answers.json").read_bytes() == original


def test_preserve_original_keeps_both_copies_and_refuses_overwrite(tmp_path: Path) -> None:
    """Migration copies all results without replacing the original or another profile."""
    root, home = tmp_path / "out", tmp_path / "home"
    assert command(root, home, "setup", "--answers", str(FIXTURE), "--no-link") == 0
    before = (root / "answers.json").read_bytes()
    assert command(root, home, "preserve", "--profile", "alex") == 0
    assert list_profiles(root) == ["alex"]
    assert (root / "profiles/alex/answers.json").read_bytes() == before
    assert (root / "answers.json").read_bytes() == before
    assert command(root, home, "preserve", "--profile", "alex") == 1
    assert (root / "profiles/alex").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("name", ["../escape", "/outside/escape", "A", "a/b", "a--b", "x" * 65])
def test_invalid_profile_names_cannot_escape_storage(tmp_path: Path, name: str) -> None:
    """Names are bounded slugs, never arbitrary paths."""
    with pytest.raises(ValueError):
        profile_directory(tmp_path, name)


@pytest.mark.parametrize("component", ["root", "profiles", "person"])
def test_redirected_profile_directories_are_refused(tmp_path: Path, component: str) -> None:
    """Profile access refuses symlinks at every managed directory level."""
    root = tmp_path / "out"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = {"root": root, "profiles": root / "profiles", "person": root / "profiles/person"}[
        component
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(ValueError):
        profile_directory(root, "person")


def test_retake_archives_one_person_and_does_not_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retaking saves old results and leaves other people's answers untouched."""
    from persona_forge import cli

    root, home = tmp_path / "out", tmp_path / "home"
    for name in ("alex", "sam"):
        assert command(root, home, "setup", "--profile", name, "--answers", str(FIXTURE)) == 0
    other = (root / "profiles/alex/answers.json").read_bytes()
    old = (root / "profiles/sam/answers.json").read_bytes()
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: ScriptedPrompter(stop_after=1))
    assert command(root, home, "retake", "--profile", "sam", "--yes") == 0
    archives = list((root / "profiles/sam/backups").glob("*/answers.json"))
    assert len(archives) == 1 and archives[0].read_bytes() == old
    assert (root / "profiles/alex/answers.json").read_bytes() == other
    assert not home.exists()


def test_new_profile_refuses_existing_storage(tmp_path: Path) -> None:
    """Creating a person twice cannot overwrite saved results."""
    create_profile(tmp_path, "person")
    with pytest.raises(ValueError, match="already exists"):
        create_profile(tmp_path, "person")


def test_preserve_refuses_symlinked_answers(tmp_path: Path) -> None:
    """Migration cannot copy personal files from an unexpected symlink target."""
    source = tmp_path / "other.json"
    source.write_text("private")
    root = tmp_path / "out"
    root.mkdir()
    (root / "answers.json").symlink_to(source)
    with pytest.raises(ValueError, match="symlinks"):
        preserve_legacy(root, "person")
    assert not (root / "profiles/person").exists()


def test_default_setup_chooses_person_before_starting_questionnaire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordinary make setup creates a named guest session without global links."""
    from persona_forge import cli

    root, home = tmp_path / "out", tmp_path / "home"

    class NewPerson(ScriptedPrompter):
        """Create a person, choose English and pause before assessment choices."""

        def text(self, message: str, limit: int) -> str:
            if message.startswith("Profile name"):
                return "friend"
            return super().text(message, limit)

    monkeypatch.delenv("PROFILE", raising=False)
    monkeypatch.delenv("ANSWERS", raising=False)
    monkeypatch.delenv("QUESTIONNAIRE_LANGUAGE", raising=False)
    monkeypatch.setattr(cli, "DEFAULT_OUT", root)
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: NewPerson(stop_after=1))
    assert main(["setup", "--home", str(home)]) == 0
    assert list_profiles(root) == ["friend"]
    assert (root / "profiles/friend/answers.json").is_file()
    assert not (root / "answers.json").exists()
    assert not home.exists()
    assert (root / "profiles").stat().st_mode & 0o077 == 0


def test_declining_retake_preserves_active_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancellation changes neither answers nor the active links."""
    from persona_forge import cli

    root, home = tmp_path / "out", tmp_path / "home"
    assert command(root, home, "setup", "--profile", "person", "--answers", str(FIXTURE)) == 0
    assert command(root, home, "link", "--profile", "person") == 0
    before = (root / "profiles/person/answers.json").read_bytes()
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: ScriptedPrompter(confirm=False))
    assert command(root, home, "retake", "--profile", "person") == 0
    assert (root / "profiles/person/answers.json").read_bytes() == before
    assert not (root / "profiles/person/backups").exists()
    assert (home / ".codex/pf-me.config.toml").is_symlink()


def test_linking_empty_profile_keeps_the_active_one(tmp_path: Path) -> None:
    """A missing result cannot deactivate a working profile."""
    root, home = tmp_path / "out", tmp_path / "home"
    assert command(root, home, "setup", "--profile", "person", "--answers", str(FIXTURE)) == 0
    assert command(root, home, "link", "--profile", "person") == 0
    assert command(root, home, "link", "--profile", "empty") == 1
    assert (home / ".codex/pf-me.config.toml").resolve().is_relative_to(root / "profiles/person")
