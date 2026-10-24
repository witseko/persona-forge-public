"""Session reset preserves answers, unrelated files and user-owned configuration."""

from pathlib import Path

import pytest
from test_questionnaire import ScriptedPrompter

from persona_forge.answers import load_answers
from persona_forge.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "answers_standard.json"


def test_clean_archives_outputs_and_allows_a_new_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed English session can be backed up and followed by Ukrainian setup."""
    from persona_forge import cli

    out_dir = tmp_path / "out"
    home = tmp_path / "home"
    common = ["--out", str(out_dir), "--home", str(home)]
    assert main(["setup", *common, "--answers", str(FIXTURE)]) == 0
    (out_dir / "polished-profile.json").write_text("old wording")
    original = {
        path.relative_to(out_dir): path.read_bytes()
        for path in out_dir.rglob("*")
        if path.is_file()
    }
    (out_dir / "notes.txt").write_text("keep this unrelated file")
    config = home / ".codex" / "config.toml"
    config.write_text("user config")
    foreign = home / ".codex" / "pf-foreign.config.toml"
    foreign.symlink_to(config)
    assert main(["clean", *common]) == 0
    backups = list((out_dir / "backups").iterdir())
    assert len(backups) == 1
    backup = backups[0]
    assert backup.stat().st_mode & 0o077 == 0
    for relative, content in original.items():
        assert (backup / relative).read_bytes() == content
        assert not (out_dir / relative).exists()
    assert (out_dir / "notes.txt").read_text() == "keep this unrelated file"
    assert config.read_text() == "user config"
    assert foreign.is_symlink()
    assert not (home / ".codex" / "pf-me.config.toml").is_symlink()
    assert not (home / ".claude" / "rules" / "persona-forge-profile.md").is_symlink()

    # Repeating clean does not recursively archive the old backup or touch its contents.
    assert main(["clean", *common]) == 0
    assert list((out_dir / "backups").iterdir()) == backups
    monkeypatch.delenv("ANSWERS", raising=False)
    monkeypatch.setattr(cli, "QuestionaryPrompter", lambda: ScriptedPrompter(confirm=False))
    assert main(["setup", *common, "--questionnaire-language", "uk", "--no-link"]) == 0
    assert load_answers(out_dir / "answers.json").questionnaire_language == "uk"
    assert load_answers(backup / "answers.json").questionnaire_language == "en"
    assert not (out_dir / "polished-profile.json").exists()


def test_clean_without_a_session_creates_no_files(tmp_path: Path) -> None:
    """Cleaning before the first setup is harmless."""
    out_dir = tmp_path / "out"
    home = tmp_path / "home"
    assert main(["clean", "--out", str(out_dir), "--home", str(home)]) == 0
    assert not out_dir.exists()
    assert not home.exists()


@pytest.mark.parametrize("conflict", ["out_symlink", "backups_symlink", "backups_file"])
def test_clean_rejects_unsafe_backup_destinations(tmp_path: Path, conflict: str) -> None:
    """Symlinked output and backup directories cannot redirect the reset elsewhere."""
    from persona_forge.clean import clean_session

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    out_dir = tmp_path / "out"
    if conflict == "out_symlink":
        out_dir.symlink_to(elsewhere, target_is_directory=True)
    else:
        out_dir.mkdir()
        if conflict == "backups_symlink":
            (out_dir / "backups").symlink_to(elsewhere, target_is_directory=True)
        else:
            (out_dir / "backups").write_text("keep")
    answers = out_dir / "answers.json"
    answers.write_text("personal answers")
    with pytest.raises(ValueError, match="regular"):
        clean_session(out_dir, tmp_path / "home")
    assert answers.read_text() == "personal answers"


def test_clean_preserves_multiple_backups(tmp_path: Path) -> None:
    """New sessions get distinct backup directories without overwriting old answers."""
    from persona_forge.clean import clean_session

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    for text in ("first", "second"):
        (out_dir / "answers.json").write_text(text)
        clean_session(out_dir, tmp_path / "home")
    backups = list((out_dir / "backups").iterdir())
    assert len(backups) == 2
    assert {(path / "answers.json").read_text() for path in backups} == {"first", "second"}
