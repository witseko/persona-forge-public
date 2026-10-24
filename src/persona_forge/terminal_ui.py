"""Terminal look: colors, panels, progress bars and tables drawn with rich.

Only display lives here. Each function returns a rich renderable, so the layout can be
tested without a terminal. Colors follow the Persona Forge CLI design system: one accent
for "now", green for "done", amber for "fix this", and no red.

Emoji add a little personality around the questions, never inside them: one icon per
module title, one per persona, and one per moment (welcome, halfway, finish). Every
icon is a single wide emoji with no variation selector, so box borders stay aligned.
The wellbeing module has no icon on purpose.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

PALETTES = {
    "dark": {
        "frame": "#6f6e69",
        "accent": "#5aa9f0",
        "highlight": "#263a52",
        "success": "#5fbf7a",
        "warn": "#e0b050",
        "muted": "#9c9b93",
        "bar_back": "#3a3936",
        "answer": "#ff9d00",
        "surface": "#1a1a19",
    },
    "light": {
        "frame": "#8e8d87",
        "accent": "#1f6fc7",
        "highlight": "#dceafa",
        "success": "#1e7a3c",
        "warn": "#8a5a00",
        "muted": "#6f6e69",
        "bar_back": "#dcdbd6",
        "answer": "#9a5800",
        "surface": "#fcfcfb",
    },
}

# Width of standalone progress bars, in columns.
PROGRESS_CELLS = 30
# Below this width the setup stepper shows only the current stage.
NARROW_WIDTH = 60

# Keyed by the English module title shown in panels and the plan table.
MODULE_ICONS = {
    "Personality": "🧠",
    "Honesty and humility": "💎",
    "Drive: self-efficacy": "💪",
    "Thinking style": "🧩",
    "Character strengths": "🌱",
    "Career interests": "🔭",
    "Work situations": "💼",
    "Working with your agent": "🤝",
}

# Keyed by persona id. Custom personas share one icon.
PERSONA_ICONS = {
    "mentor": "🧭",
    "strict-reviewer": "🔍",
    "pair-programmer": "👥",
    "devils-advocate": "😈",
    "architect": "📐",
    "coach": "🏃",
    "executive-lens": "📊",
    "product-thinker": "💡",
    "complement": "🌗",
    "mirror": "💬",
}
CUSTOM_PERSONA_ICON = "✨"

MOMENT_ICONS = {"welcome": "🔥", "resume": "👋", "halfway": "☕", "forging": "🔨", "done": "🔥"}

OFF_VALUES = {"0", "false", "no", "off"}

HEADER_PATTERN = re.compile(r"^(?P<title>.+?)   \[[#-]{10}\]  (?P<number>\d+) \S+ (?P<total>\d+)$")


@dataclass(frozen=True)
class SetupProgress:
    """Where the user is in setup: stage 1 to 4, and an optional answer counter."""

    stage: int
    stage_labels: tuple[str, str, str, str]
    counter_label: str = ""
    done: int = 0
    total: int = 0
    counter_text: str = ""
    note: str = ""


@dataclass(frozen=True)
class Summary:
    """The finish screen: who, key facts, the personas made and what to do next."""

    title: str
    facts: tuple[tuple[str, str], ...]
    personas_heading: str
    personas: tuple[tuple[str, str], ...]
    hints: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PlanRow:
    """One module in the questionnaire plan. `state` is done, active or todo."""

    name: str
    questions: int
    minutes: str
    status: str
    state: str


@dataclass(frozen=True)
class Plan:
    """The questionnaire plan table: column headings, rows and a caption."""

    headers: tuple[str, str, str, str]
    rows: tuple[PlanRow, ...]
    caption: str


def detect_theme(environ: Mapping[str, str]) -> str:
    """Pick dark or light colors: PERSONA_FORGE_THEME wins, then COLORFGBG, then dark."""
    chosen = environ.get("PERSONA_FORGE_THEME", "").strip().lower()
    if chosen in PALETTES:
        return chosen
    background = environ.get("COLORFGBG", "").rsplit(";", 1)[-1]
    return "light" if background in {"7", "15"} else "dark"


def emoji_enabled(environ: Mapping[str, str], encoding: str) -> bool:
    """Show emoji unless PERSONA_FORGE_EMOJI turns them off or the terminal cannot."""
    if environ.get("PERSONA_FORGE_EMOJI", "").strip().lower() in OFF_VALUES:
        return False
    if environ.get("TERM") == "dumb":
        return False
    return encoding.lower().replace("-", "").startswith("utf")


def with_icon(icon: str, text: str) -> str:
    """Put an icon before text, or return the text alone when there is no icon."""
    return f"{icon} {text}" if icon else text


def persona_icon(persona_id: str) -> str:
    """The icon for a preset or built-in persona; custom personas get a sparkle."""
    return PERSONA_ICONS.get(persona_id, CUSTOM_PERSONA_ICON)


def rich_theme(name: str) -> Theme:
    """Named rich styles for one palette, including the progress bar styles."""
    colors = PALETTES[name]
    return Theme(
        {
            "pf.frame": colors["frame"],
            "pf.accent": colors["accent"],
            "pf.title": f"bold {colors['accent']}",
            "pf.success": colors["success"],
            "pf.done": f"bold {colors['success']}",
            "pf.muted": colors["muted"],
            "bar.back": colors["bar_back"],
            "bar.complete": colors["accent"],
            "bar.finished": colors["success"],
            "bar.pulse": colors["accent"],
        }
    )


def questionary_style_rules(name: str) -> list[tuple[str, str]]:
    """Style rules for questionary prompts in one palette."""
    colors = PALETTES[name]
    return [
        ("qmark", f"fg:{colors['accent']} bold"),
        ("question", "bold"),
        ("answer", f"fg:{colors['answer']} bold"),
        ("pointer", f"fg:{colors['accent']} bg:{colors['highlight']} bold"),
        ("highlighted", f"bg:{colors['highlight']} bold"),
        ("selected", f"fg:{colors['accent']}"),
        ("instruction", f"fg:{colors['muted']}"),
        ("separator", f"fg:{colors['frame']}"),
        ("disabled", f"fg:{colors['muted']} italic"),
        ("validation-toolbar", f"bg:{colors['warn']} fg:{colors['surface']} bold"),
        ("key", f"fg:{colors['accent']} bg:{colors['highlight']} bold"),
        ("key-label", f"fg:{colors['muted']}"),
        ("saved", f"fg:{colors['success']}"),
    ]


def control_bar_tokens(
    controls: list[tuple[str, str]], saved: str = "", saved_label: str = ""
) -> list[tuple[str, str]]:
    """The key bar under a prompt: an optional saved-answer line, then key chips.

    `controls` holds (key, label) pairs such as ("←", "Back"). The result is
    prompt_toolkit formatted text that uses the `key`, `key-label` and `saved` styles.
    """
    tokens: list[tuple[str, str]] = [("", "\n")]
    if saved:
        tokens += [("class:saved", f" ✓ {saved_label} "), ("class:saved bold", saved), ("", "\n")]
    for index, (key, label) in enumerate(controls):
        tokens += [("", " " if index == 0 else "   "), ("class:key", f" {key} ")]
        tokens.append(("class:key-label", f" {label}"))
    return tokens


def parse_progress_header(header: str) -> tuple[str, int, int] | None:
    """Split "Personality   [####------]  5 of 12" into title, number and total."""
    match = HEADER_PATTERN.match(header)
    if match is None:
        return None
    return match["title"], int(match["number"]), int(match["total"])


def _counter(done: int, total: int, text: str) -> Table:
    """A bar that fills the line, with its count on the right."""
    row = Table.grid(expand=True, padding=(0, 0, 0, 2))
    row.add_column(ratio=1)
    row.add_column(justify="right", no_wrap=True)
    row.add_row(ProgressBar(total=max(total, 1), completed=done), Text(text, style="pf.muted"))
    return row


def question_panel(
    header: str, body: str, width: int, icons: Mapping[str, str] | None = None
) -> Panel:
    """The question screen: module title, progress, then the hint or scenario text.

    A body with several paragraphs (a scenario) shows its first paragraph in bold.
    A single paragraph is a hint and is shown muted. Screens without a progress header
    (instructions) show the body as plain text.
    """
    parsed = parse_progress_header(header)
    parts: list[RenderableType] = []
    if parsed is None:
        title = header
        if body:
            parts.append(Text(body))
    else:
        title, number, total = parsed
        parts.append(_counter(number - 1, total, header.rsplit("  ", 1)[1]))
        paragraphs = [paragraph for paragraph in body.split("\n\n") if paragraph.strip()]
        if len(paragraphs) > 1:
            parts += [Text(""), Text(paragraphs[0], style="bold")]
            parts += [item for paragraph in paragraphs[1:] for item in (Text(""), Text(paragraph))]
        elif paragraphs:
            parts += [Text(""), Text(paragraphs[0], style="pf.muted")]
    icon = (icons or {}).get(title, "")
    return Panel(
        Group(*parts),
        title=Text(with_icon(icon, title), style="pf.title"),
        title_align="left",
        box=box.ROUNDED,
        border_style="pf.frame",
        padding=(0, 1),
        width=width,
    )


def _blocks(body: str) -> list[list[str]]:
    """Split notice text into paragraphs, joining wrapped lines; bullets start with "- "."""
    blocks: list[list[str]] = []
    for paragraph in body.strip("\n").split("\n\n"):
        entries: list[str] = []
        for line in paragraph.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") or not entries:
                entries.append(stripped)
            else:
                entries[-1] = f"{entries[-1]} {stripped}"
        if entries:
            blocks.append(entries)
    return blocks


def notice_panel(title: str, body: str, width: int, accent: bool = False) -> Panel:
    """A framed notice. Bullet lines become a hanging-indent list with accent dots."""
    parts: list[RenderableType] = []
    for entries in _blocks(body):
        parts.append(Text(""))
        if all(entry.startswith("- ") for entry in entries):
            bullets = Table.grid(padding=(0, 1, 0, 0))
            bullets.add_column(no_wrap=True)
            bullets.add_column()
            for entry in entries:
                bullets.add_row(Text("•", style="pf.accent"), Text(entry[2:]))
            parts.append(bullets)
        else:
            parts.extend(Text(entry) for entry in entries)
    parts.append(Text(""))
    return Panel(
        Group(*parts),
        title=Text(title, style="pf.title"),
        title_align="left",
        box=box.ROUNDED,
        border_style="pf.accent" if accent else "pf.frame",
        padding=(0, 1),
        width=width,
    )


def stepper(progress: SetupProgress, width: int) -> Group:
    """Setup stages on one line (done, current, upcoming), then the answer counter."""
    line = Text(" ")
    if width < NARROW_WIDTH:
        label = progress.stage_labels[progress.stage - 1]
        line.append("● ", style="pf.accent").append(label, style="pf.title")
        line.append(f" {progress.stage}/4", style="pf.muted")
    else:
        for index, label in enumerate(progress.stage_labels, start=1):
            if index < progress.stage:
                line.append(f"✓ {label}", style="pf.success")
            elif index == progress.stage:
                line.append("● ", style="pf.accent").append(label, style="pf.title")
            else:
                line.append(f"○ {label}", style="pf.muted")
            if index < len(progress.stage_labels):
                line.append(" ── ", style="pf.frame")
    parts: list[RenderableType] = [line]
    if progress.total:
        label = f" {progress.counter_label}"
        counter = f" {progress.counter_text}"
        cells = max(8, min(PROGRESS_CELLS, width - len(label) - len(counter) - 2))
        row = Table.grid(padding=(0, 0, 0, 1))
        row.add_column(no_wrap=True)
        row.add_column(width=cells)
        row.add_column(no_wrap=True)
        row.add_row(
            Text(label, style="pf.muted"),
            ProgressBar(total=progress.total, completed=progress.done, width=cells),
            Text(counter, style="pf.muted"),
        )
        parts.append(row)
    if progress.note:
        parts.append(Text(f" {progress.note}", style="pf.muted"))
    return Group(*parts)


STATE_GLYPHS = {
    "done": ("✓", "pf.success"),
    "active": ("●", "pf.accent"),
    "todo": ("○", "pf.muted"),
}


def plan_table(plan: Plan, width: int, icons: Mapping[str, str] | None = None) -> Table:
    """The module plan: name, question count, time and status, in a rounded table."""
    table = Table(
        box=box.ROUNDED,
        border_style="pf.frame",
        header_style="bold",
        caption=plan.caption,
        caption_style="pf.muted",
        caption_justify="left",
        width=width,
    )
    module, questions, time, status = plan.headers
    table.add_column(module, ratio=1)
    table.add_column(questions, justify="right", no_wrap=True)
    if width >= NARROW_WIDTH:
        table.add_column(time, justify="right", no_wrap=True, style="pf.muted")
    table.add_column(status, no_wrap=True)
    for row in plan.rows:
        glyph, style = STATE_GLYPHS[row.state]
        name = with_icon((icons or {}).get(row.name, ""), row.name)
        cells: list[RenderableType] = [Text(name), str(row.questions)]
        if width >= NARROW_WIDTH:
            cells.append(row.minutes)
        cells.append(Text(f"{glyph} {row.status}", style=style))
        table.add_row(*cells)
    return table


def section_rule(title: str, icons: Mapping[str, str] | None = None) -> Rule:
    """A centered rule marking a finished section."""
    label = with_icon((icons or {}).get(title, ""), title)
    return Rule(Text(f"✓ {label}", style="pf.done"), style="pf.frame")


def moment_line(icon: str, text: str) -> Text:
    """A one-line moment such as a welcome or a halfway note. Text is never markup."""
    line = Text(" ")
    if icon:
        line.append(f"{icon} ")
    return line.append(text, style="bold")


def summary_panel(summary: Summary, width: int, icon: str = "", emoji: bool = True) -> Panel:
    """The finish screen: facts, one line per persona with its switch name, next steps."""
    facts = Table.grid(padding=(0, 2, 0, 0))
    facts.add_column(style="pf.muted", no_wrap=True)
    facts.add_column()
    for label, value in summary.facts:
        facts.add_row(label, Text(value))
    personas = Table.grid(padding=(0, 2, 0, 0))
    personas.add_column(no_wrap=True)
    personas.add_column(style="pf.muted", no_wrap=True)
    for persona_id, name in summary.personas:
        label = with_icon(persona_icon(persona_id) if emoji else "", name)
        personas.add_row(Text(label), f"pf-{persona_id}")
    hints = Table.grid(padding=(0, 2, 0, 0))
    hints.add_column(style="pf.accent", no_wrap=True)
    hints.add_column(style="pf.muted")
    for command, description in summary.hints:
        hints.add_row(command, description)
    parts: list[RenderableType] = [Text(""), facts, Text("")]
    if summary.personas:
        parts += [Text(summary.personas_heading, style="bold"), personas, Text("")]
    parts += [hints, Text("")]
    return Panel(
        Group(*parts),
        title=Text(with_icon(icon, summary.title), style="pf.done"),
        title_align="left",
        box=box.ROUNDED,
        border_style="pf.success",
        padding=(0, 1),
        width=width,
    )


def render_text(renderable: RenderableType, width: int = 76) -> str:
    """Render to plain text without color. Used by tests and for debugging layouts."""
    from rich.console import Console

    console = Console(
        width=width, record=True, color_system=None, file=_NullFile(), theme=rich_theme("dark")
    )
    console.print(renderable)
    return console.export_text()


class _NullFile:
    """A write-only sink so render_text never prints."""

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        return None
