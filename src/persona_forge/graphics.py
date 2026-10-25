"""Draw the README and docs graphics as theme-aware SVG files.

`make graphics` reads `data/evaluation-summary.json` and writes `docs/images/*.svg`.
Rules (from the Persona Forge CLI design system, Charts section): the title is the
answer, plain words only, at most five items per graphic, the persona-forge profile is
always the blue mark, bars start at zero, and pilot graphics carry their caveat. Every
label is measured against its box; text that would overflow stops the build.
"""

import html
import json
import sys
from collections.abc import Callable
from pathlib import Path

from persona_forge.files import PROJECT_ROOT

SUMMARY_FILE = PROJECT_ROOT / "data" / "evaluation-summary.json"
IMAGES_DIR = PROJECT_ROOT / "docs" / "images"
WIDTH = 720
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
PILOT_NOTE = "Test with 3 made-up people, not real users. Details: docs/evaluation-summary.md"
KIND_ORDER = ("none", "note", "settings", "profile")

TOKENS = {
    "light": {
        "surface": "#fcfcfb",
        "card": "#ffffff",
        "border": "#e4e3df",
        "frame": "#8e8d87",
        "text-primary": "#0b0b0b",
        "text-secondary": "#52514e",
        "text-muted": "#6f6e69",
        "series-1": "#2a78d6",
        "series-2": "#eb6834",
        "series-muted": "#a9a8a2",
        "accent": "#1f6fc7",
    },
    "dark": {
        "surface": "#1a1a19",
        "card": "#222220",
        "border": "#3a3936",
        "frame": "#6f6e69",
        "text-primary": "#f0efec",
        "text-secondary": "#c3c2b7",
        "text-muted": "#9c9b93",
        "series-1": "#3987e5",
        "series-2": "#d95926",
        "series-muted": "#6f6e69",
        "accent": "#5aa9f0",
    },
}

CLASSES = (
    ".bg{fill:var(--surface)} .card{fill:var(--card);stroke:var(--border);stroke-width:1}"
    ".t1{fill:var(--text-primary)} .t2{fill:var(--text-secondary)} .t3{fill:var(--text-muted)}"
    ".head{font-size:18px;font-weight:600} .sub{font-size:12.5px} .lab{font-size:12px}"
    ".small{font-size:11.5px} .big{font-size:24px;font-weight:600}"
    ".num{font-variant-numeric:tabular-nums} .grid{stroke:var(--border);stroke-width:1}"
    ".s1{fill:var(--series-1)} .s2{fill:var(--series-2)} .sm{fill:var(--series-muted)}"
    ".lm{stroke:var(--series-muted);stroke-width:2;stroke-linecap:round}"
    ".ring{stroke:var(--surface);stroke-width:2} .inbar{fill:#fff;font-weight:600}"
    ".box{fill:var(--card);stroke:var(--frame);stroke-width:1}"
    ".boxa{fill:var(--card);stroke:var(--accent);stroke-width:1.5}"
    ".ttl{fill:var(--accent);font-size:13px;font-weight:600}"
    ".arrow{stroke:var(--frame);stroke-width:1.5;fill:none} .tip{fill:var(--frame)}"
)


def text_width(content: str, size: float, bold: bool = False) -> float:
    """A generous width estimate for system sans text, so real text is never wider."""
    return len(content) * size * (0.62 if bold else 0.57)


def fits(content: str, size: float, room: float, bold: bool = False) -> str:
    """Return the text, or stop when it would run past its box."""
    if text_width(content, size, bold) > room:
        raise ValueError(f"text does not fit in {room:.0f}px: {content!r}")
    return content


def esc(content: str) -> str:
    """Escape text for SVG."""
    return html.escape(content, quote=True)


def text(x: float, y: float, content: str, cls: str, anchor: str = "start") -> str:
    """One text element."""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}">{esc(content)}</text>'
    )


def style() -> str:
    """Embedded light and dark token values, switched by the viewer's color scheme."""
    light = ";".join(f"--{name}:{value}" for name, value in TOKENS["light"].items())
    dark = ";".join(f"--{name}:{value}" for name, value in TOKENS["dark"].items())
    return (
        f"<style>svg.pf-chart{{{light}}}"
        f"@media (prefers-color-scheme: dark){{svg.pf-chart{{{dark}}}}}"
        f"text{{font-family:{FONT}}}{CLASSES}</style>"
    )


def document(height: float, body: str, title: str, desc: str, pilot: bool = True) -> str:
    """Wrap a graphic with its title, description, background and optional caveat."""
    if pilot:
        body += text(24, height - 16, PILOT_NOTE, "t3 small")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" class="pf-chart" viewBox="0 0 {WIDTH} '
        f'{height:.0f}" width="{WIDTH}" height="{height:.0f}" role="img" '
        f'aria-labelledby="title desc"><title id="title">{esc(title)}</title>'
        f'<desc id="desc">{esc(desc)}</desc>{style()}'
        f'<rect class="bg" width="{WIDTH}" height="{height:.0f}" rx="10"/>{body}</svg>\n'
    )


def header(title: str, subtitle: str) -> str:
    """The answer as a title, then one plain line of context."""
    room = WIDTH - 48
    return text(24, 36, fits(title, 18, room, True), "t1 head") + text(
        24, 58, fits(subtitle, 12.5, room), "t3 sub"
    )


def legend(items: list[tuple[str, str]], y: float) -> str:
    """Colored dots with text labels; text never wears the series color."""
    parts, x = [], 24.0
    for cls, label in items:
        parts.append(f'<circle class="{cls}" cx="{x + 5:.1f}" cy="{y - 4:.1f}" r="5"/>')
        parts.append(text(x + 15, y, label, "t2 lab"))
        x += 34 + text_width(label, 12)
    return "".join(parts)


def bar(x0: float, x1: float, y: float, height: float, cls: str, tip: str) -> str:
    """A horizontal bar: square at the zero line, 4px rounded end."""
    r = min(4.0, (x1 - x0) / 2)
    path = (
        f"M{x0:.1f},{y:.1f} H{x1 - r:.1f} A{r},{r} 0 0 1 {x1:.1f},{y + r:.1f} "
        f"V{y + height - r:.1f} A{r},{r} 0 0 1 {x1 - r:.1f},{y + height:.1f} H{x0:.1f} Z"
    )
    return f'<path class="{cls}" d="{path}"><title>{esc(tip)}</title></path>'


def box(
    x: float, y: float, w: float, h: float, title: str, lines: list[str], accent: bool = False
) -> str:
    """A rounded diagram box with a title and short lines."""
    room = w - 24
    parts = [
        f'<rect class="{"boxa" if accent else "box"}" x="{x:.1f}" y="{y:.1f}" '
        f'width="{w:.1f}" height="{h:.1f}" rx="6"/>',
        text(x + 12, y + 24, fits(title, 13, room, True), "ttl"),
    ]
    for index, line in enumerate(lines):
        parts.append(text(x + 12, y + 44 + index * 17, fits(line, 11.5, room), "t2 small"))
    return "".join(parts)


def arrow(x1: float, y1: float, x2: float, y2: float) -> str:
    """A thin connector with a small arrowhead."""
    return (
        f'<path class="arrow" d="M{x1:.1f},{y1:.1f} L{x2 - 6:.1f},{y2:.1f}"/>'
        f'<path class="tip" d="M{x2:.1f},{y2:.1f} l-7,-4 v8 z"/>'
    )


def bar_rows(
    rows: list[tuple[str, float, str]], top: float, maximum: float, ticks: list[float], unit: str
) -> tuple[str, float]:
    """Labelled horizontal bars from zero, with gridlines and tick labels."""
    left, right = 200.0, WIDTH - 90.0

    def scale(value: float) -> float:
        return left + value / maximum * (right - left)

    parts = [
        f'<line class="grid" x1="{scale(t):.1f}" x2="{scale(t):.1f}" y1="{top}" '
        f'y2="{top + len(rows) * 30}"/>'
        for t in ticks
    ]
    for index, (label, value, cls) in enumerate(rows):
        y = top + 7 + index * 30
        shown = f"{value:g}{unit}" if unit else f"{value:.1f}"
        parts.append(text(190, y + 12, fits(label, 12, 176), "t2 lab", "end"))
        parts.append(bar(scale(0), scale(value), y, 16, cls, f"{label}: {shown}"))
        parts.append(text(scale(value) + 8, y + 12, shown, "t1 lab num"))
    bottom = top + len(rows) * 30 + 16
    for tick in ticks:
        parts.append(text(scale(tick), bottom, f"{tick:g}", "t3 small num", "middle"))
    return "".join(parts), bottom


def how_it_works(summary: dict) -> str:
    """The product in three steps, then the two assistants."""
    w, h, y, side = 160.0, 96.0, 80.0, 130.0
    gap = (WIDTH - 48 - 3 * w - side) / 3
    xs = [24 + index * (w + gap) for index in range(3)]
    parts = [
        header("How persona-forge works", "Everything stays in a private folder on your computer.")
    ]
    steps = [
        ("1. Questionnaire", ["questions about you", "+ work situations", "+ your preferences"]),
        ("2. You review", ["keep or drop", "each statement", "about you"]),
        ("3. Your profile", ["how you like to work", "+ assistant personas", "+ private report"]),
    ]
    for index, (title, lines) in enumerate(steps):
        parts.append(box(xs[index], y, w, h, title, lines, accent=index == 2))
        if index < 2:
            parts.append(arrow(xs[index] + w, y + h / 2, xs[index + 1], y + h / 2))
    side_x = WIDTH - 24 - side
    parts.append(box(side_x, y - 10, side, 56, "Claude Code", ["rules + styles"]))
    parts.append(box(side_x, y + 50, side, 56, "Codex", ["codex -p"]))
    parts.append(arrow(xs[2] + w, y + h / 2 - 8, side_x, y + 18))
    parts.append(arrow(xs[2] + w, y + h / 2 + 8, side_x, y + 78))
    return document(
        210,
        "".join(parts),
        "How persona-forge works",
        "Answer a questionnaire, keep or drop each statement about you, and get a "
        "profile with assistant personas that Claude Code and Codex use.",
        pilot=False,
    )


def short_answer(summary: dict) -> str:
    """Three cards that answer 'does it help?' first."""
    cards = [
        ("Correct answers", "Same", "with or without a profile"),
        ("Compared with nothing", "A bit better", "too small to be sure"),
        ("Compared with a short note", "Worse", "a 5-line note did better"),
    ]
    gap = 12.0
    card_w = (WIDTH - 48 - 2 * gap) / 3
    parts = [
        header("The short answer", "Does a persona-forge profile help AI assistants work with you?")
    ]
    for index, (label, value, note) in enumerate(cards):
        x = 24 + index * (card_w + gap)
        room = card_w - 32
        parts.append(
            f'<rect class="card" x="{x:.1f}" y="78" width="{card_w:.1f}" height="104" rx="10"/>'
        )
        parts.append(text(x + 16, 104, fits(label, 12, room), "t3 lab"))
        parts.append(text(x + 16, 142, fits(value, 24, room, True), "t1 big"))
        parts.append(text(x + 16, 166, fits(note, 12, room), "t2 lab"))
    return document(
        226,
        "".join(parts),
        "The short answer",
        "Correct answers stayed the same with a profile. It was a bit better than "
        "no instructions, too small to be sure, and worse than a short 5-line note.",
    )


def what_we_tested(summary: dict) -> str:
    """The pilot in four boxes."""
    steps = [
        ("3 made-up people", ["tired senior dev", "keen junior dev", "demanding manager"]),
        ("4 kinds of notes", ["none", "short note", "settings / profile"]),
        ("2 AI assistants", ["Claude Code", "Codex", "same 4 work tasks"]),
        ("An AI judge", [f"scored {summary['trials']} replies", "not told which", "note was used"]),
    ]
    w, h, y = 153.0, 104.0, 80.0
    gap = (WIDTH - 48 - 4 * w) / 3
    parts = [
        header(
            "What we tested",
            "Each made-up person gave the assistants a different kind of note about themselves.",
        )
    ]
    for index, (title, lines) in enumerate(steps):
        x = 24 + index * (w + gap)
        parts.append(box(x, y, w, h, title, lines, accent=index == 3))
        if index < 3:
            parts.append(arrow(x + w, y + h / 2, x + w + gap, y + h / 2))
    return document(
        228,
        "".join(parts),
        "What we tested",
        "Three made-up people, four kinds of notes, two AI assistants and an AI "
        f"judge that scored {summary['trials']} replies without being told which "
        "note was used.",
    )


def fit_average(summary: dict) -> dict[str, float]:
    """Average fit of both assistants for each kind of note."""
    agents = summary["fit_out_of_8"].values()
    return {kind: sum(agent[kind] for agent in agents) / len(agents) for kind in KIND_ORDER}


def fit_score(summary: dict) -> str:
    """Zero-based bars of average fit out of 8."""
    kinds = summary["kinds"]
    average = fit_average(summary)
    best = max(average, key=average.get)
    title = (
        "All four did well. The short note fit best."
        if best == "note"
        else (f"All four did well. {kinds[best]} fit best.")
    )
    rows = [(kinds[k], round(average[k], 1), "s1" if k == "profile" else "sm") for k in KIND_ORDER]
    parts = [
        header(
            title,
            "How well replies matched what each person asked for. Score out of 8, both assistants.",
        ),
        legend([("s1", kinds["profile"]), ("sm", "Other notes")], 88),
    ]
    body, bottom = bar_rows(rows, 106, 8, [0, 2, 4, 6, 8], "")
    parts.append(body)
    desc = "Average fit out of 8: " + ", ".join(f"{label} {value:.1f}" for label, value, _ in rows)
    return document(bottom + 40, "".join(parts), title, desc + ".")


def judge_counts(summary: dict) -> list[tuple[str, list[int]]]:
    """Judge outcomes summed over both assistants, profile against each other kind."""
    agents = [value for key, value in summary["judge"].items() if key != "comment"]
    out = []
    for kind in ("none", "note", "settings"):
        counts = [sum(agent[kind][index] for agent in agents) for index in range(4)]
        out.append((f"vs {summary['kinds'][kind].split(' (')[0].lower()}", counts))
    return out


def judge_preference(summary: dict) -> str:
    """Side-by-side preferences: profile better, same, other better; unsure apart."""
    rows = judge_counts(summary)
    total = sum(rows[0][1])
    left, right = 170.0, WIDTH - 150.0
    unit = (right - left) / total
    title = "The judge preferred the profile to nothing, not to a note"
    parts = [
        header(title, f"{total} side-by-side comparisons each. Which reply did the judge prefer?"),
        legend([("s1", "Profile better"), ("sm", "Same"), ("s2", "Other note better")], 88),
        text(WIDTH - 24, 110, "unsure", "t3 small", "end"),
    ]
    for index, (label, (better, same, worse, unsure)) in enumerate(rows):
        y = 118 + index * 34
        parts.append(text(160, y + 13, fits(label, 12, 136), "t2 lab", "end"))
        x = left
        for count, cls, word in (
            (better, "s1", "profile better"),
            (same, "sm", "same"),
            (worse, "s2", "other note better"),
        ):
            if not count:
                continue
            seg = count * unit
            parts.append(
                f'<rect class="{cls}" x="{x:.1f}" y="{y}" width="{seg - 2:.1f}" '
                f'height="18" rx="3"><title>{esc(f"{label}: {count} {word}")}'
                "</title></rect>"
            )
            if text_width(str(count), 11.5) + 8 < seg:
                parts.append(text(x + seg / 2 - 1, y + 13, str(count), "small num inbar", "middle"))
            x += seg
        parts.append(text(WIDTH - 24, y + 13, f"{unsure} of {total}", "t2 small num", "end"))
    bottom = 118 + len(rows) * 34 + 14
    parts.append(
        text(
            24,
            bottom,
            "Unsure: the judge picked a different reply when the order was swapped.",
            "t3 small",
        )
    )
    desc = "; ".join(
        f"{label}: profile better {b}, same {s}, other better {w}, unsure {u}"
        for label, (b, s, w, u) in rows
    )
    return document(bottom + 38, "".join(parts), title, desc + ".")


def reply_length(summary: dict) -> str:
    """Words per reply for the person who asked for short answers."""
    kinds = summary["kinds"]
    claude = summary["short_answer_words"]["Claude Code"]
    codex = summary["short_answer_words"]["Codex"]
    title = "Asked for short answers, the profile kept replies long"
    rows = [(kinds[k], claude[k], "s1" if k == "profile" else "sm") for k in KIND_ORDER]
    parts = [
        header(title, "Average words per reply for the tired senior developer, with Claude Code."),
        legend([("s1", kinds["profile"]), ("sm", "Other notes")], 88),
    ]
    body, bottom = bar_rows(rows, 106, 1000, [0, 250, 500, 750, 1000], " words")
    parts.append(body)
    parts.append(
        text(
            24,
            bottom + 22,
            fits(
                f"With Codex, every kind of note made replies shorter (profile: {codex['profile']} "
                f"words, no instructions: {codex['none']}).",
                11.5,
                WIDTH - 48,
            ),
            "t3 small",
        )
    )
    desc = "Claude Code words per reply: " + ", ".join(
        f"{label} {value}" for label, value, _ in rows
    )
    return document(bottom + 58, "".join(parts), title, desc + ".")


def requested_formats(summary: dict) -> str:
    """Before and after: replies out of 8 using the format the manager asked for."""
    left, right = 310.0, WIDTH - 110.0

    def scale(value: float) -> float:
        return left + value / 8 * (right - left)

    title = "The manager got the formats they asked for"
    parts = [
        header(title, "Out of 8 replies, without any note and with a note or profile."),
        legend([("sm", "No note"), ("s1", "With a note or profile")], 88),
    ]
    rows = summary["formats_out_of_8"]
    top = 106
    for tick in range(0, 9, 2):
        parts.append(
            f'<line class="grid" x1="{scale(tick):.1f}" x2="{scale(tick):.1f}" '
            f'y1="{top}" y2="{top + len(rows) * 36}"/>'
        )
    for index, row in enumerate(rows):
        y = top + 18 + index * 36
        low, high, base = row["with_low"], row["with_high"], row["without"]
        parts.append(text(296, y + 4, fits(row["label"], 12, 272), "t2 lab", "end"))
        parts.append(
            f'<line class="lm" x1="{scale(base):.1f}" x2="{scale(low):.1f}" y1="{y}" y2="{y}"/>'
        )
        parts.append(
            f'<circle class="sm ring" cx="{scale(base):.1f}" cy="{y}" r="5">'
            f"<title>{esc(row['label'])}: {base} of 8 without a note</title></circle>"
        )
        if high > low:
            parts.append(
                f'<rect class="s1" x="{scale(low) - 5:.1f}" y="{y - 5}" '
                f'width="{scale(high) - scale(low) + 10:.1f}" height="10" rx="5">'
                f"<title>{esc(row['label'])}: {low}-{high} of 8 with a note</title>"
                "</rect>"
            )
            shown = f"{low}-{high} of 8"
        else:
            parts.append(
                f'<circle class="s1 ring" cx="{scale(high):.1f}" cy="{y}" r="5">'
                f"<title>{esc(row['label'])}: {high} of 8 with a note</title></circle>"
            )
            shown = f"{high} of 8"
        parts.append(text(scale(high) + 14, y + 4, shown, "t1 lab num"))
        parts.append(text(scale(base), y - 11, f"{base} of 8", "t3 small num", "middle"))
    bottom = top + len(rows) * 36 + 16
    for tick in range(0, 9, 2):
        parts.append(text(scale(tick), bottom, str(tick), "t3 small num", "middle"))
    desc = "; ".join(
        f"{r['label']}: {r['without']} of 8 without a note, "
        f"{r['with_low']}-{r['with_high']} of 8 with one"
        for r in rows
    )
    return document(bottom + 40, "".join(parts), title, desc + ".")


GRAPHICS: dict[str, Callable[[dict], str]] = {
    "how-it-works": how_it_works,
    "short-answer": short_answer,
    "what-we-tested": what_we_tested,
    "fit-score": fit_score,
    "judge-preference": judge_preference,
    "reply-length": reply_length,
    "requested-formats": requested_formats,
}


def load_summary(path: Path = SUMMARY_FILE) -> dict:
    """Read the aggregated, public-safe evaluation numbers."""
    return json.loads(path.read_text(encoding="utf-8"))


def render_all(summary: dict) -> dict[str, str]:
    """Every graphic as SVG text, keyed by file name."""
    return {f"{name}.svg": make(summary) for name, make in GRAPHICS.items()}


def write_all(directory: Path = IMAGES_DIR) -> list[Path]:
    """Write every graphic into `directory` and return the paths."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in render_all(load_summary()).items():
        path = directory / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for written_path in write_all(Path(sys.argv[1]) if len(sys.argv) > 1 else IMAGES_DIR):
        print(
            written_path.relative_to(PROJECT_ROOT)
            if written_path.is_relative_to(PROJECT_ROOT)
            else written_path
        )
