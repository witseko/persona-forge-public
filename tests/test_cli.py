"""End-to-end CLI behaviour with a temporary output folder and home folder."""

import json
import os
import tomllib
from pathlib import Path

import pytest
from helpers import make_answers

from persona_forge.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "answers_standard.json"


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Separate output and home folders inside the test's temporary directory."""
    out_dir, home = tmp_path / "out", tmp_path / "home"
    home.mkdir()
    return out_dir, home


def _run(command: str, out_dir: Path, home: Path, *extra: str) -> int:
    """Run one CLI command against temporary folders."""
    return main([command, "--out", str(out_dir), "--home", str(home), *extra])


def _snapshot(root: Path) -> dict[str, tuple[str, float | None]]:
    """Record every path under root with its link target or modification time."""
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            result[str(path.relative_to(root))] = (os.readlink(path), None)
        elif path.is_file():
            result[str(path.relative_to(root))] = (path.read_text(), path.stat().st_mtime)
    return result


def test_help_lists_commands(capsys: pytest.CaptureFixture[str]) -> None:
    """Users can discover every command."""
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    for command in ("setup", "ego", "report", "link", "unlink", "status"):
        assert command in help_text


@pytest.mark.parametrize("arguments", [[], ["unknown"], ["setup", "--unknown"]])
def test_invalid_arguments_are_rejected(arguments: list[str]) -> None:
    """Argparse rejects unknown operations before a workflow can run."""
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


def test_non_interactive_setup_creates_every_output_and_link(dirs: tuple[Path, Path]) -> None:
    """The documented fixture produces the full file table, linked into the home folder."""
    out_dir, home = dirs
    assert _run("setup", out_dir, home, "--answers", str(FIXTURE)) == 0
    expected_links = {
        home / ".claude" / "rules" / "persona-forge-profile.md",
        home / ".codex" / "pf-me.config.toml",
    }
    for ego in ("mentor", "strict-reviewer", "complement", "mirror", "rubber-duck"):
        expected_links.add(home / ".claude" / "output-styles" / f"pf-{ego}.md")
        expected_links.add(home / ".codex" / f"pf-{ego}.config.toml")
    for link in expected_links:
        assert link.is_symlink(), link
        assert out_dir.resolve() in Path(os.readlink(link)).parents
    for config in (out_dir / "codex").glob("*.toml"):
        assert tomllib.loads(config.read_text())["developer_instructions"].strip()
    assert (out_dir / "report.html").is_file()
    assert (out_dir / "answers.json").stat().st_mode & 0o077 == 0  # owner-only


def test_setup_twice_changes_nothing(dirs: tuple[Path, Path]) -> None:
    """A second identical run leaves files, timestamps and links untouched."""
    out_dir, home = dirs
    assert _run("setup", out_dir, home, "--answers", str(FIXTURE)) == 0
    before = (_snapshot(out_dir), _snapshot(home))
    assert _run("setup", out_dir, home, "--answers", str(FIXTURE)) == 0
    assert _snapshot(out_dir) == before[0]
    assert _snapshot(home) == before[1]
    assert not list(home.rglob("*.bak.*"))


def test_unlink_removes_only_own_links_and_keeps_backups(dirs: tuple[Path, Path]) -> None:
    """A pre-existing file is backed up on link, and unlink leaves it and foreign files alone."""
    out_dir, home = dirs
    rules = home / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "persona-forge-profile.md").write_text("my own rules")
    (rules / "other.md").write_text("unrelated")
    assert _run("setup", out_dir, home, "--answers", str(FIXTURE)) == 0
    backups = list(rules.glob("persona-forge-profile.md.bak.*"))
    assert len(backups) == 1 and backups[0].read_text() == "my own rules"
    assert _run("unlink", out_dir, home) == 0
    assert not (rules / "persona-forge-profile.md").exists()
    assert (rules / "other.md").read_text() == "unrelated"
    assert backups[0].exists()
    assert not [p for p in home.rglob("pf-*") if p.is_symlink()]


def test_incomplete_answers_file_fails_without_writing(dirs: tuple[Path, Path]) -> None:
    """A partial answers file is refused with a clear error and no output."""
    out_dir, home = dirs
    answers = make_answers()
    answers["sjt"].popitem()
    path = out_dir.parent / "partial.json"
    path.write_text(json.dumps(answers))
    assert _run("setup", out_dir, home, "--answers", str(path)) == 1
    assert not out_dir.exists()
    assert list(home.iterdir()) == []


@pytest.mark.parametrize(
    "mutation",
    ["unknown_field", "bad_item_value", "unknown_role", "unknown_scenario", "bad_ego"],
)
def test_malformed_answers_are_rejected(dirs: tuple[Path, Path], mutation: str) -> None:
    """Unknown fields, values and identifiers in an answers file are refused."""
    out_dir, home = dirs
    answers = make_answers()
    if mutation == "unknown_field":
        answers["admin"] = True
    elif mutation == "bad_item_value":
        instrument_answers = next(iter(answers["instruments"].values()))
        instrument_answers[next(iter(instrument_answers))] = 9
    elif mutation == "unknown_role":
        answers["role"] = "astronaut"
    elif mutation == "unknown_scenario":
        answers["sjt"]["made-up"] = "a"
    else:
        answers["egos"] = {"presets": ["../../etc"]}
    path = out_dir.parent / "bad.json"
    path.write_text(json.dumps(answers))
    assert _run("setup", out_dir, home, "--answers", str(path)) == 1
    assert list(home.iterdir()) == []


def test_answers_env_variable_is_used(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`make setup ANSWERS=path` exports ANSWERS, which the CLI reads as data."""
    out_dir, home = dirs
    monkeypatch.setenv("ANSWERS", str(FIXTURE))
    assert _run("setup", out_dir, home, "--no-link") == 0
    assert (out_dir / "report.html").is_file()
    assert list(home.iterdir()) == []


def test_report_and_status_after_setup(
    dirs: tuple[Path, Path], caplog: pytest.LogCaptureFixture
) -> None:
    """Report regenerates without asking; status shows completion and links."""
    out_dir, home = dirs
    assert _run("setup", out_dir, home, "--answers", str(FIXTURE)) == 0
    (out_dir / "report.html").unlink()
    assert _run("report", out_dir, home, "--no-open") == 0
    assert (out_dir / "report.html").is_file()
    caplog.clear()
    assert _run("status", out_dir, home) == 0
    assert "Questionnaire: complete" in caplog.text
    assert "linked" in caplog.text


def test_commands_without_answers_fail_cleanly(
    dirs: tuple[Path, Path], caplog: pytest.LogCaptureFixture
) -> None:
    """Report and ego need finished answers; status and unlink still work."""
    out_dir, home = dirs
    assert _run("report", out_dir, home, "--no-open") == 1
    assert "run `make setup`" in caplog.text
    assert _run("status", out_dir, home) == 0
    assert _run("unlink", out_dir, home) == 0
    assert list(home.iterdir()) == []
