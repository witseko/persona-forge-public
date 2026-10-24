"""Write every generated file into out/ from the answers.

Generation is deterministic for a given day, and files are only rewritten when their
content changes, so running setup twice changes nothing.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from persona_forge.answers import Answers
from persona_forge.egos import Ego, build_egos
from persona_forge.files import write_private_text_if_changed
from persona_forge.polish import load_polished_profile
from persona_forge.profile import Profile, accepted_statements, build_profile, statements_by_section
from persona_forge.render_claude import RULES_FILE_NAME, output_style_name, render_output_style
from persona_forge.render_codex import codex_profile_name, render_codex_config
from persona_forge.render_profile import append_practical_tips, render_profile_markdown
from persona_forge.render_report import render_report

LOGGER = logging.getLogger(__name__)
# Only files matching these names are ever deleted from out/ as stale.
OWNED_STYLE = re.compile(r"^pf-[a-z0-9-]+\.md$")
OWNED_CODEX = re.compile(r"^pf-[a-z0-9-]+\.config\.toml$")


@dataclass
class Outputs:
    """Paths written (or confirmed unchanged) by one generation run."""

    profile: Profile
    egos: list[Ego]
    files: list[Path]
    unreviewed: int


def _write_if_changed(path: Path, text: str, written: list[Path]) -> None:
    """Write `text` only when the file content differs, and record the path."""
    write_private_text_if_changed(path, text)
    written.append(path)


def _remove_stale(directory: Path, pattern: re.Pattern[str], keep: set[str]) -> None:
    """Delete generated files of ours that are no longer produced (for example a dropped ego)."""
    if not directory.is_dir():
        return
    for path in directory.iterdir():
        if (
            pattern.match(path.name)
            and path.name not in keep
            and path.is_file()
            and not path.is_symlink()
        ):
            path.unlink()
            LOGGER.info("removed stale %s", path)


def profile_markdown_for(profile: Profile, accepted: dict, out_dir: Path) -> str:
    """Return the work profile text, using accepted polished wording when it is current."""
    template = render_profile_markdown(profile, accepted)
    polished = load_polished_profile(out_dir, template)
    return append_practical_tips(polished or template, profile.wellbeing_tips)


def generate(answers: Answers, out_dir: Path, today: date | None = None) -> Outputs:
    """Build the profile and egos and write all outputs under `out_dir`."""
    profile = build_profile(answers)
    accepted_list = accepted_statements(profile, answers.review)
    accepted = statements_by_section(accepted_list)
    reviewed = set(answers.review)
    unreviewed = sum(1 for statement in profile.statements if statement.id not in reviewed)
    egos = build_egos(answers.egos, profile, accepted)
    written: list[Path] = []

    profile_json = json.dumps(profile.to_dict(), indent=2, ensure_ascii=False) + "\n"
    _write_if_changed(out_dir / "profile.json", profile_json, written)

    markdown = profile_markdown_for(profile, accepted, out_dir)
    _write_if_changed(out_dir / "claude" / "rules" / RULES_FILE_NAME, markdown, written)

    style_dir = out_dir / "claude" / "output-styles"
    codex_dir = out_dir / "codex"
    style_names = {f"{output_style_name(ego)}.md" for ego in egos}
    codex_names = {f"{codex_profile_name(None)}.config.toml"} | {
        f"{codex_profile_name(ego)}.config.toml" for ego in egos
    }
    _remove_stale(style_dir, OWNED_STYLE, style_names)
    _remove_stale(codex_dir, OWNED_CODEX, codex_names)
    for ego in egos:
        _write_if_changed(
            style_dir / f"{output_style_name(ego)}.md", render_output_style(ego), written
        )
        _write_if_changed(
            codex_dir / f"{codex_profile_name(ego)}.config.toml",
            render_codex_config(markdown, ego),
            written,
        )
    _write_if_changed(codex_dir / "pf-me.config.toml", render_codex_config(markdown), written)

    generated_on = (today or date.today()).isoformat()
    _write_if_changed(
        out_dir / "report.html",
        render_report(
            profile,
            accepted,
            generated_on,
            answers.questionnaire_language,
            answers.instrument_languages,
        ),
        written,
    )
    return Outputs(profile, egos, written, unreviewed)
