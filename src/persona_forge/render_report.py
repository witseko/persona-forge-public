"""Render the private HTML report: self-contained, offline, light and dark.

Every value from answers or data files is HTML-escaped. The page loads nothing from
the network: CSS is inline and charts are inline SVG.
"""

from html import escape

from persona_forge.content import load_dimensions
from persona_forge.flow import DEPTHS
from persona_forge.instruments import load_instrument_by_id
from persona_forge.model import ScaleScore
from persona_forge.profile import Profile, Statement
from persona_forge.render_profile import KNOWN_RESULT_LABELS

SECTION_TITLES = {
    "communication": "How you communicate",
    "decisions": "How you decide",
    "strengths": "Strengths",
    "growth": "Growth points",
    "collaboration": "Collaboration",
}

DISCLAIMER = (
    '<div class="card note"><p>This report reflects your own answers. Scores describe where '
    "your answers sit within each response range; they are <strong>not population "
    "norms</strong>, ability ratings or predictions of performance, and nothing here is a "
    "diagnosis. Bands: low is below 40 percent of the range, high is above 60 percent.</p></div>"
)

STYLE = """
:root {
  color-scheme: light;
  --surface: #fcfcfb; --card: #ffffff; --border: #e4e3df;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #6f6e69;
  --series-1: #2a78d6; --track: #ecebe7; --mid-tick: #a9a8a2; --note: #f5f1e6;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface: #1a1a19; --card: #222220; --border: #3a3936;
    --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #9c9b93;
    --series-1: #3987e5; --track: #33322f; --mid-tick: #6f6e69; --note: #2c2a24;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --card: #222220; --border: #3a3936;
  --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #9c9b93;
  --series-1: #3987e5; --track: #33322f; --mid-tick: #6f6e69; --note: #2c2a24;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface); color: var(--text-primary);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 19px; margin: 32px 0 8px; }
h3 { font-size: 15px; margin: 18px 0 6px; color: var(--text-secondary); }
p, li { color: var(--text-secondary); }
.meta { color: var(--text-muted); margin: 0 0 16px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 16px; margin: 12px 0; }
.note { background: var(--note); }
.rows { display: grid; grid-template-columns: minmax(120px, 34%) 1fr auto; gap: 6px 12px;
  align-items: center; }
.rows .label { color: var(--text-primary); }
.rows .value { color: var(--text-secondary); font-variant-numeric: tabular-nums;
  white-space: nowrap; }
.poles { display: flex; justify-content: space-between; color: var(--text-muted);
  font-size: 12px; grid-column: 2; margin-top: -4px; }
svg.bar { width: 100%; height: 12px; display: block; }
.bar .track { fill: var(--track); }
.bar .fill, .bar .dot { fill: var(--series-1); }
.bar .dot { stroke: var(--card); stroke-width: 2; }
.bar .mid { stroke: var(--mid-tick); stroke-width: 1; }
table { border-collapse: collapse; width: 100%; }
td, th { text-align: left; padding: 4px 8px 4px 0; border-bottom: 1px solid var(--border);
  vertical-align: top; color: var(--text-secondary); }
th { color: var(--text-primary); font-weight: 600; }
.credits p { font-size: 13px; }
@media (max-width: 520px) { .rows { grid-template-columns: 1fr auto; grid-auto-flow: row dense; }
  .rows .label { grid-column: 1; } .rows .value { grid-column: 2; }
  .rows svg.bar { grid-column: 1 / -1; } .poles { grid-column: 1 / -1; }
  .spacer { display: none; } }
"""


def _e(value: object) -> str:
    """Escape any value for HTML text or attribute context."""
    return escape(str(value), quote=True)


def bar_svg(position: float, tooltip: str) -> str:
    """A magnitude bar: square at the baseline, 4px rounded data end."""
    width = max(0.0, min(1.0, position)) * 200
    fill = ""
    if width > 0:
        radius = min(4.0, width / 2)
        # Path: square left edge (baseline), rounded right end.
        fill = (
            f'<path class="fill" d="M0 0 H{width - radius:.2f} '
            f"A{radius:.2f} {radius:.2f} 0 0 1 {width:.2f} {radius:.2f} V{12 - radius:.2f} "
            f'A{radius:.2f} {radius:.2f} 0 0 1 {width - radius:.2f} 12 H0 Z"/>'
        )
    return (
        '<svg class="bar" viewBox="0 0 200 12" preserveAspectRatio="none" role="img" '
        f'aria-label="{_e(tooltip)}"><title>{_e(tooltip)}</title>'
        f'<rect class="track" width="200" height="12" rx="4"/>{fill}</svg>'
    )


def bipolar_svg(position: float, tooltip: str) -> str:
    """A position marker between two poles, with a neutral midpoint tick."""
    x = 6 + max(0.0, min(1.0, position)) * 188
    return (
        '<svg class="bar" viewBox="0 0 200 12" preserveAspectRatio="none" role="img" '
        f'aria-label="{_e(tooltip)}"><title>{_e(tooltip)}</title>'
        '<rect class="track" y="4" width="200" height="4" rx="2"/>'
        '<line class="mid" x1="100" x2="100" y1="0" y2="12"/>'
        f'<circle class="dot" cx="{x:.2f}" cy="6" r="5"/></svg>'
    )


def score_value(score: ScaleScore, aggregation: str, scale_max: int) -> str:
    """Readable score text: sums show "x of max", means show one decimal."""
    if aggregation == "sum":
        return f"{score.score:g} of {scale_max}"
    return f"{score.score:.1f}"


def score_rows(scores: tuple[ScaleScore, ...], instrument_id: str) -> str:
    """Rows of label, bar and value for a set of scales."""
    instrument = load_instrument_by_id(instrument_id)
    maximum = instrument.response_sets[0].maximum
    rows = []
    for score in scores:
        scale_max = maximum * score.item_count
        value = score_value(score, instrument.aggregation, scale_max)
        tooltip = f"{score.name}: {value}, {score.band} (not normed)"
        rows.append(
            f'<div class="label">{_e(score.name)}</div>{bar_svg(score.position, tooltip)}'
            f'<div class="value">{_e(value)} &middot; {_e(score.band)}</div>'
        )
    return '<div class="rows">' + "".join(rows) + "</div>"


def instrument_section(profile: Profile, instrument_id: str, title: str, intro: str) -> str:
    """One instrument's domains and scales, or an empty string if it was not taken."""
    for result in profile.instrument_scores:
        if result.instrument_id != instrument_id:
            continue
        parts = [f"<h2>{_e(title)}</h2>", f"<p>{_e(intro)}</p>", '<div class="card">']
        if not result.domains:
            parts += [score_rows(result.scales, instrument_id), "</div>"]
            return "".join(parts)
        parts += ["<h3>Domains</h3>", score_rows(result.domains, instrument_id)]
        # Facets are listed under their own domain so the hierarchy stays visible.
        scale_by_id = {score.id: score for score in result.scales}
        instrument = load_instrument_by_id(instrument_id)
        for domain in instrument.domains:
            facets = tuple(scale_by_id[scale_id] for scale_id in domain.scale_ids)
            parts += [f"<h3>{_e(domain.name)} facets</h3>", score_rows(facets, instrument_id)]
        parts.append("</div>")
        return "".join(parts)
    return ""


def render_report(
    profile: Profile,
    accepted: dict[str, list[tuple[Statement, str]]],
    generated_on: str,
    questionnaire_language: str = "en",
    instrument_languages: dict[str, str] | None = None,
) -> str:
    """Return the full HTML report."""
    body = [
        f"<h1>Work profile: {_e(profile.name)}</h1>",
        f'<p class="meta">{_e(profile.role_title)} &middot; {_e(profile.seniority)} &middot; '
        f"{_e(DEPTHS[profile.depth].title)} depth &middot; generated {_e(generated_on)}</p>",
        DISCLAIMER,
    ]
    if questionnaire_language == "uk":
        body.append(
            "<p>Questionnaire language: Ukrainian (Persona Forge project translation, "
            "revision 1, not psychometrically validated in Ukrainian). GSE "
            "and O*NET are not offered by the Ukrainian language pack. "
            "Previously completed English responses are retained.</p>"
        )
        if (instrument_languages or {}).get("cbi-work") == "en":
            body.append("<p>The wellbeing questionnaire was administered in English.</p>")
    body.append(
        instrument_section(
            profile,
            "mini-ipip",
            "Personality (Big Five)",
            "Mini-IPIP, a 20-item short form. Short forms are less precise.",
        )
    )
    body.append(
        instrument_section(
            profile,
            "ipip-neo-120",
            "Personality (Big Five)",
            "IPIP-NEO-120: five domains, each built from six facets.",
        )
    )
    body.append(
        instrument_section(
            profile,
            "ipip-hexaco-hh",
            "Honesty and humility",
            "Preliminary IPIP proxies for the HEXACO Honesty-Humility facets.",
        )
    )
    body.append(
        instrument_section(
            profile,
            "gse",
            "Self-efficacy",
            "General Self-Efficacy Scale: confidence in handling difficult situations.",
        )
    )
    body.append(
        instrument_section(
            profile,
            "ncs-6",
            "Thinking style",
            "Need for Cognition (6 items): enjoyment of effortful thinking.",
        )
    )
    body.append(
        instrument_section(
            profile, "ipip-via", "Character strengths", "Revised IPIP-VIA scales, self-rated."
        )
    )
    if profile.signature_strengths:
        names = ", ".join(strength["label"] for strength in profile.signature_strengths)
        body.append(f"<p>Highest-rated strengths: {_e(names)}.</p>")
    if profile.interests:
        body.append(interest_section(profile))
    body.append(sjt_section(profile))
    body.append(statement_section(accepted))
    body.append(preference_section(profile))
    body.append(extras_section(profile))
    if profile.wellbeing:
        body.append(wellbeing_section(profile))
    body.append(credits_section(profile))
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Work profile: {_e(profile.name)}</title><style>{STYLE}</style></head>"
        f"<body><main>{''.join(body)}</main></body></html>\n"
    )


def interest_section(profile: Profile) -> str:
    """RIASEC counts as bars and the three-letter interest code."""
    code = "".join(interest["label"][0] for interest in profile.interests[:3])
    rows = []
    for interest in profile.interests:
        tooltip = f"{interest['label']}: {interest['count']} of 10 activities"
        bar = bar_svg(interest["count"] / 10, tooltip)
        rows.append(
            f'<div class="label">{_e(interest["label"])}</div>{bar}'
            f'<div class="value">{interest["count"]} of 10</div>'
        )
    descriptions = "".join(
        f"<li><strong>{_e(i['label'])}</strong>: {_e(i['description'])}</li>"
        for i in profile.interests[:3]
    )
    return (
        "<h2>Career interests</h2><p>O*NET Interest Profiler Short Form: activities you would like "
        f"to do, counted per interest area. Your top three: <strong>{_e(code)}</strong>.</p>"
        f'<div class="card"><div class="rows">{"".join(rows)}</div><ul>{descriptions}</ul></div>'
    )


def sjt_section(profile: Profile) -> str:
    """Scenario dimensions as positions between two poles."""
    rows = []
    for dimension in load_dimensions():
        trait = profile.traits.get(f"sjt:{dimension.id}")
        if trait is None:
            continue
        poles = f"{dimension.low_label} to {dimension.high_label}"
        tooltip = f"{dimension.name}: {trait.position:.2f} ({poles})"
        rows.append(
            f'<div class="label">{_e(dimension.name)}</div>{bipolar_svg(trait.position, tooltip)}'
            f'<div class="value">{trait.position:.2f}</div>'
            f'<div class="poles"><span>{_e(dimension.low_label)}</span>'
            f'<span>{_e(dimension.high_label)}</span></div><div class="spacer"></div>'
        )
    return (
        "<h2>Work situations</h2><p>Your choices in project-authored IT scenarios. These are "
        "reflective prompts, not a validated test; the middle means a balanced or situational "
        f'approach.</p><div class="card"><div class="rows">{"".join(rows)}</div></div>'
    )


def statement_section(accepted: dict[str, list[tuple[Statement, str]]]) -> str:
    """Statements the user accepted in review, grouped by section."""
    parts = ["<h2>Statements you accepted</h2>", '<div class="card">']
    any_statement = False
    for section, title in SECTION_TITLES.items():
        entries = accepted.get(section, [])
        if not entries:
            continue
        any_statement = True
        items = "".join(f"<li>{_e(text)}</li>" for _, text in entries)
        parts.append(f"<h3>{_e(title)}</h3><ul>{items}</ul>")
    if not any_statement:
        parts.append("<p>No statements were accepted.</p>")
    parts.append("</div>")
    return "".join(parts)


def preference_section(profile: Profile) -> str:
    """The explicit collaboration preferences as instructions."""
    items = "".join(f"<li>{_e(text)}</li>" for text in profile.preference_instructions.values())
    return f'<h2>How you asked your agent to work</h2><div class="card"><ul>{items}</ul></div>'


def extras_section(profile: Profile) -> str:
    """Derived label and self-reported results from other tests."""
    parts = []
    if profile.derived_label:
        parts.append(
            f"<p>Approximate four-letter label: <strong>{_e(profile.derived_label)}</strong>. "
            "Derived from your Big Five scores for familiarity only; it is not an MBTI result "
            "and has no validated equivalence to one. X means exactly in the middle.</p>"
        )
    known = [
        f"<li>{_e(KNOWN_RESULT_LABELS[key])}: {_e(value)}</li>"
        for key, value in profile.known_results.items()
        if value
    ]
    if known:
        parts.append(f"<p>Results you reported from other tests:</p><ul>{''.join(known)}</ul>")
    if profile.note:
        parts.append(f"<p>Your note to the agent: {_e(profile.note)}</p>")
    if not parts:
        return ""
    return f'<h2>Other notes</h2><div class="card">{"".join(parts)}</div>'


def wellbeing_section(profile: Profile) -> str:
    """Opt-in wellbeing result with calm, non-diagnostic wording (report only)."""
    wellbeing = profile.wellbeing or {}
    tooltip = f"{wellbeing['name']}: {wellbeing['score']:.0f} of 100"
    return (
        "<h2>Wellbeing (private)</h2>"
        '<div class="card note"><div class="rows">'
        f'<div class="label">{_e(wellbeing["name"])}</div>{bar_svg(wellbeing["position"], tooltip)}'
        f'<div class="value">{wellbeing["score"]:.0f} of 100</div></div>'
        f"<p>{_e(wellbeing['note'])}</p><p>This section appears only in this private report. "
        "It is never written to agent files.</p></div>"
    )


def credits_section(profile: Profile) -> str:
    """Citation, licence and credit line for every instrument used."""
    instrument_ids = [result.instrument_id for result in profile.instrument_scores]
    if profile.wellbeing:
        instrument_ids.append("cbi-work")
    parts = ['<h2>About the questionnaires</h2><div class="card credits">']
    for instrument_id in instrument_ids:
        instrument = load_instrument_by_id(instrument_id)
        parts.append(
            f"<p><strong>{_e(instrument.name)}</strong>. {_e(instrument.citation)} "
            f"Licence: {_e(instrument.licence)} {_e(instrument.attribution)}</p>"
        )
    parts.append(
        "<p>Work situations, collaboration preferences, interpretation statements and agent tips "
        "are authored by persona-forge and are not validated instruments.</p></div>"
    )
    return "".join(parts)
