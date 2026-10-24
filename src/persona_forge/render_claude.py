"""Claude Code outputs: an always-on rules file and one output style per alter ego."""

import json

from persona_forge.egos import Ego
from persona_forge.render_profile import render_ego_markdown

RULES_FILE_NAME = "persona-forge-profile.md"


def output_style_name(ego: Ego) -> str:
    """Return the style name used with /output-style, for example pf-mentor."""
    return f"pf-{ego.id}"


def render_output_style(ego: Ego) -> str:
    """Return an output style file that keeps Claude Code's coding instructions.

    Frontmatter values are written as JSON strings, which YAML reads as double-quoted
    scalars, so a custom ego name cannot break the frontmatter.
    """
    frontmatter = [
        "---",
        f"name: {json.dumps(output_style_name(ego))}",
        f"description: {json.dumps(f'persona-forge: {ego.name}. {ego.description}')}",
        "keep-coding-instructions: true",
        "---",
        "",
    ]
    return "\n".join(frontmatter) + render_ego_markdown(ego)
