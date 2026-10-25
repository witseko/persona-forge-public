"""Optional prose polish of the work profile through `claude -p` or `codex exec`.

Only the template work profile is sent. It never contains scores, screener names or
wellbeing data (practical tips are appended after polishing). The reply is treated as
untrusted text: it must keep every heading, stay under a size limit and contain no
code blocks. The user sees the exact payload before sending and a diff before saving.
The polished text is stored with a hash of the template it came from, so it is used
only while the underlying answers are unchanged.
"""

import difflib
import hashlib
import json
import shutil
import subprocess  # noqa: S404 - fixed argument lists, no shell
from pathlib import Path

from persona_forge.files import read_json_file, write_private_json
from persona_forge.render_profile import HEADINGS

POLISH_FILE = "polished-profile.json"
MAX_POLISHED_CHARS = 8000
TIMEOUT_SECONDS = 180
INSTRUCTION = (
    "Improve the wording of the following Markdown work profile. Keep it in the first "
    "person, keep every heading exactly as written and in the same order, keep the meaning "
    "of every bullet, do not add new facts, and keep it under 60 lines. Reply with the "
    "Markdown only, without code fences."
)


class PolishError(ValueError):
    """Raised when polishing fails or the reply does not pass validation."""


def _digest(text: str) -> str:
    """Hash of the template text the polish was based on."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def available_tools() -> list[str]:
    """Return the polishing CLIs found on PATH, in preference order."""
    return [tool for tool in ("claude", "codex") if shutil.which(tool)]


def command_for(tool: str) -> list[str]:
    """Return the argument list for a tool; the payload goes to standard input."""
    if tool == "claude":
        # The prompt comes before --tools, which takes a variable number of values; an
        # empty tool list keeps the call to plain text generation.
        return ["claude", "-p", INSTRUCTION, "--tools", ""]
    if tool == "codex":
        # "-" makes codex exec read the prompt from standard input.
        return ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-"]
    raise PolishError(f"unknown tool {tool}")


def payload_for(tool: str, template: str) -> str:
    """Return exactly what is sent on standard input."""
    if tool == "codex":
        return f"{INSTRUCTION}\n\n{template}"
    return template


def run_polish(tool: str, template: str) -> str:
    """Call the tool and return its validated reply."""
    executable = shutil.which(tool)
    if executable is None:
        raise PolishError(f"{tool} is not installed")
    command = [executable, *command_for(tool)[1:]]
    try:
        completed = subprocess.run(  # noqa: S603 - argument list built from constants
            command,
            input=payload_for(tool, template),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PolishError(f"{tool} did not finish: {error}") from error
    if completed.returncode != 0:
        raise PolishError(f"{tool} exited with status {completed.returncode}")
    return validate_polished(completed.stdout)


def validate_polished(text: str) -> str:
    """Accept a reply only if it keeps the structure and contains no code blocks."""
    text = text.strip() + "\n"
    if len(text) > MAX_POLISHED_CHARS:
        raise PolishError("the polished profile is too long")
    if "```" in text or "~~~" in text:
        raise PolishError("the polished profile must not contain code blocks")
    if not text.startswith("# "):
        raise PolishError("the polished profile must start with the title heading")
    positions = []
    lines = text.splitlines()
    for heading in HEADINGS:
        if heading not in lines:
            raise PolishError(f"the polished profile lost the heading: {heading}")
        positions.append(lines.index(heading))
    if positions != sorted(positions):
        raise PolishError("the polished profile reordered its headings")
    if any(line.startswith("#") and line not in HEADINGS for line in lines[1:]):
        raise PolishError("the polished profile added headings")
    return text


def diff(template: str, polished: str) -> str:
    """Unified diff for the user to review."""
    return "".join(
        difflib.unified_diff(
            template.splitlines(keepends=True),
            polished.splitlines(keepends=True),
            "template",
            "polished",
        )
    )


def save_polished_profile(out_dir: Path, template: str, polished: str) -> None:
    """Store accepted wording alongside the hash of its template."""
    write_private_json(
        out_dir / POLISH_FILE, {"template_sha256": _digest(template), "text": polished}
    )


def load_polished_profile(out_dir: Path, template: str) -> str | None:
    """Return accepted wording if it was made from this exact template, else None."""
    path = out_dir / POLISH_FILE
    if not path.is_file():
        return None
    try:
        raw = read_json_file(path, max_bytes=100_000)
        if raw.get("template_sha256") != _digest(template):
            return None
        return validate_polished(raw["text"])
    except (ValueError, KeyError, AttributeError, TypeError, json.JSONDecodeError):
        return None
