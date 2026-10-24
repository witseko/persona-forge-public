"""Optional polish (with the subprocess mocked) and alter ego construction."""

import subprocess
from pathlib import Path
from typing import Any

import pytest
from helpers import make_answers

from persona_forge import polish
from persona_forge.answers import AnswersError, parse_answers
from persona_forge.egos import build_egos, custom_ego, validate_ego_choices
from persona_forge.profile import accepted_statements, build_profile, statements_by_section
from persona_forge.render_profile import HEADINGS, render_profile_markdown


def _template() -> str:
    """The template profile for the synthetic answers."""
    profile = build_profile(parse_answers(make_answers()))
    accepted = statements_by_section(accepted_statements(profile, {}))
    return render_profile_markdown(profile, accepted)


def test_valid_polish_is_accepted() -> None:
    """A reworded profile with the same headings passes validation."""
    template = _template()
    reworded = template.replace("I tend to", "I usually")
    assert polish.validate_polished(reworded) == reworded


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: text.replace(HEADINGS[2], "## Decisions"),
        lambda text: text + "\n```sh\nrm -rf ~\n```\n",
        lambda text: text + "\n## Extra heading\n",
        lambda text: text * 10,
        lambda text: text.replace(HEADINGS[0], "TEMP")
        .replace(HEADINGS[1], HEADINGS[0])
        .replace("TEMP", HEADINGS[1]),
    ],
)
def test_invalid_polish_is_rejected(mutate: Any) -> None:
    """Lost or reordered headings, code blocks, extra headings and bloat are refused."""
    with pytest.raises(polish.PolishError):
        polish.validate_polished(mutate(_template()))


def test_polish_runs_with_argument_list_and_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI is called without a shell, with the payload on standard input."""
    calls: list[dict[str, Any]] = []
    template = _template()

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout=template, stderr="")

    monkeypatch.setattr(polish.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(polish.subprocess, "run", fake_run)
    assert polish.run_polish("claude", template) == template
    call = calls[0]
    assert isinstance(call["command"], list) and "shell" not in call
    assert call["input"] == template and call["timeout"] == polish.TIMEOUT_SECONDS
    assert call["command"][-2:] == ["--tools", ""]


def test_polish_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-zero exit becomes a PolishError so the template wording is kept."""
    monkeypatch.setattr(polish.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(
        polish.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "boom"),
    )
    with pytest.raises(polish.PolishError):
        polish.run_polish("codex", _template())


def test_saved_polish_applies_only_to_its_template(tmp_path: Path) -> None:
    """Changed answers (a different template) ignore the stale polished text."""
    template = _template()
    polished = template.replace("I tend to", "I usually")
    polish.save_polished_profile(tmp_path, template, polished)
    assert polish.load_polished_profile(tmp_path, template) == polished
    assert polish.load_polished_profile(tmp_path, template + "- changed\n") is None


def test_build_egos_in_stable_order() -> None:
    """Presets, then complement and mirror, then custom egos."""
    answers = parse_answers(make_answers())
    profile = build_profile(answers)
    accepted = statements_by_section(accepted_statements(profile, {}))
    ids = [ego.id for ego in build_egos(answers.egos, profile, accepted)]
    assert ids == ["mentor", "strict-reviewer", "complement", "mirror", "rubber-duck"]


@pytest.mark.parametrize(
    "entry",
    [
        {
            "name": "me",
            "purpose": "review",
            "bluntness": "blunt",
            "warmth": "cool",
            "detail": "brief",
            "risk": "bold",
            "humour": "none",
        },
        {
            "name": "!!!",
            "purpose": "review",
            "bluntness": "blunt",
            "warmth": "cool",
            "detail": "brief",
            "risk": "bold",
            "humour": "none",
        },
        {
            "name": "Ok",
            "purpose": "hack",
            "bluntness": "blunt",
            "warmth": "cool",
            "detail": "brief",
            "risk": "bold",
            "humour": "none",
        },
        {"name": "Ok", "purpose": "review"},
    ],
)
def test_invalid_custom_egos_are_refused(entry: dict[str, str]) -> None:
    """Reserved or empty names, unknown options and missing answers are refused."""
    with pytest.raises(AnswersError):
        custom_ego(entry)


def test_ego_choice_validation() -> None:
    """Unknown presets and too many custom egos are refused."""
    with pytest.raises(AnswersError):
        validate_ego_choices({"presets": ["hacker"]})
    custom = make_answers()["egos"]["custom"][0]
    with pytest.raises(AnswersError):
        validate_ego_choices({"custom": [custom] * 4})
