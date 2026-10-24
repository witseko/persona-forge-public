"""Turn answers into a profile: scores, reviewable statements and explicit preferences.

The profile is the single input for every renderer. Wellbeing results are kept in a
separate field that only the HTML report reads; agent files never see them.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

from persona_forge.answers import Answers
from persona_forge.content import load_dimensions, load_preferences
from persona_forge.flow import ROLES, SENIORITY, WELLBEING_INSTRUMENTS, depth_scenarios
from persona_forge.insights import SECTIONS, load_rules, load_strength_texts, load_wellbeing_text
from persona_forge.instruments import load_instrument_by_id
from persona_forge.languages import load_language
from persona_forge.model import InstrumentScore, ScaleScore
from persona_forge.scoring import band_for_position, score_instrument, score_sjt

# Scores from different instruments that describe the same Big Five domain share a key,
# so the same interpretation rules work for the Quick (Mini-IPIP) and longer depths.
BIG_FIVE_KEYS = {
    ("mini-ipip", "extraversion"): "big5:extraversion",
    ("mini-ipip", "agreeableness"): "big5:agreeableness",
    ("mini-ipip", "conscientiousness"): "big5:conscientiousness",
    ("mini-ipip", "neuroticism"): "big5:neuroticism",
    ("mini-ipip", "intellect-imagination"): "big5:openness",
    ("ipip-neo-120", "e"): "big5:extraversion",
    ("ipip-neo-120", "a"): "big5:agreeableness",
    ("ipip-neo-120", "c"): "big5:conscientiousness",
    ("ipip-neo-120", "n"): "big5:neuroticism",
    ("ipip-neo-120", "o"): "big5:openness",
}
TRAIT_PREFIXES = {
    "ipip-neo-120": "neo",
    "ipip-hexaco-hh": "hh",
    "gse": "gse",
    "ncs-6": "ncs",
    "ipip-via": "via",
    "onet-ip-sf": "onet",
}
# Keep the work profile short (about 60 lines): at most this many statements per section.
SECTION_LIMITS = {
    "communication": 4,
    "decisions": 4,
    "strengths": 5,
    "growth": 4,
    "collaboration": 3,
}
SIGNATURE_STRENGTHS = 5


@dataclass(frozen=True)
class Trait:
    """One interpretable score, keyed like "big5:openness" or "sjt:pace"."""

    key: str
    name: str
    position: float
    band: str


@dataclass(frozen=True)
class Statement:
    """A generated statement the user reviews (yes, partly or no)."""

    id: str
    section: str
    text: str
    softened: str
    agent_tip: str
    source: str


@dataclass
class Profile:
    """Everything renderers need. `wellbeing` is report-only by design."""

    name: str
    role: str
    role_title: str
    seniority: str
    depth: str
    traits: dict[str, Trait]
    instrument_scores: list[InstrumentScore]
    instrument_names: dict[str, str]
    statements: list[Statement]
    preference_instructions: dict[str, str]
    signature_strengths: list[dict[str, Any]]
    interests: list[dict[str, Any]]
    derived_label: str | None
    known_results: dict[str, str]
    note: str
    wellbeing: dict[str, Any] | None = None
    wellbeing_tips: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready dictionary (written to out/profile.json, never to agent files)."""
        return asdict(self)


def collect_traits(scores: list[InstrumentScore], sjt_means: dict[str, float]) -> dict[str, Trait]:
    """Map instrument and scenario scores to shared trait keys."""
    traits: dict[str, Trait] = {}
    for instrument_score in scores:
        prefix = TRAIT_PREFIXES.get(instrument_score.instrument_id)
        for score in instrument_score.scales + instrument_score.domains:
            big_five = BIG_FIVE_KEYS.get((instrument_score.instrument_id, score.id))
            if big_five:
                traits[big_five] = Trait(big_five, score.name, score.position, score.band)
            if prefix:
                key = f"{prefix}:{score.id}"
                traits[key] = Trait(key, score.name, score.position, score.band)
    dimension_names = {dimension.id: dimension.name for dimension in load_dimensions()}
    for dimension_id, mean in sjt_means.items():
        key = f"sjt:{dimension_id}"
        traits[key] = Trait(key, dimension_names[dimension_id], mean, band_for_position(mean))
    return traits


def derive_label(traits: dict[str, Trait]) -> str | None:
    """Approximate four-letter label from Big Five positions, for familiarity only.

    E/I from Extraversion, N/S from Openness, F/T from Agreeableness and J/P from
    Conscientiousness. An exact midpoint shows "X". This is not an MBTI result.
    """
    pairs = [
        ("big5:extraversion", "E", "I"),
        ("big5:openness", "N", "S"),
        ("big5:agreeableness", "F", "T"),
        ("big5:conscientiousness", "J", "P"),
    ]
    if not all(key in traits for key, _, _ in pairs):
        return None
    letters = []
    for key, high, low in pairs:
        position = round(traits[key].position, 9)
        letters.append(high if position > 0.5 else low if position < 0.5 else "X")
    return "".join(letters)


def select_statements(traits: dict[str, Trait], role: str) -> list[Statement]:
    """Fire matching rules, strongest tendencies first, within per-section limits."""
    candidates = []
    for rule in load_rules():
        trait = traits.get(rule.trait)
        if trait is None or trait.band != rule.band or (rule.roles and role not in rule.roles):
            continue
        strength = abs(trait.position - 0.5)
        statement = Statement(
            rule.id, rule.section, rule.statement, rule.softened, rule.agent_tip, rule.trait
        )
        candidates.append((strength, statement))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    selected: list[Statement] = []
    for _, statement in candidates:
        same_section = [s for s in selected if s.section == statement.section]
        if len(same_section) < SECTION_LIMITS[statement.section]:
            selected.append(statement)
    return selected


def signature_strengths(traits: dict[str, Trait]) -> list[dict[str, Any]]:
    """Top character strengths: the highest high-band IPIP-VIA scales."""
    via_texts, _ = load_strength_texts()
    high = [
        trait for key, trait in traits.items() if key.startswith("via:") and trait.band == "high"
    ]
    high.sort(key=lambda trait: trait.position, reverse=True)
    result = []
    for trait in high[:SIGNATURE_STRENGTHS]:
        scale_id = trait.key.removeprefix("via:")
        text = via_texts[scale_id]
        result.append(
            {"id": scale_id, "label": text.label, "position": trait.position, "tip": text.text}
        )
    return result


def strength_statements(strengths: list[dict[str, Any]]) -> list[Statement]:
    """Reviewable statements for signature strengths."""
    return [
        Statement(
            f"via-{strength['id']}",
            "strengths",
            f"{strength['label']} is among my highest-rated character strengths.",
            f"{strength['label']} may be one of my character strengths.",
            strength["tip"],
            f"via:{strength['id']}",
        )
        for strength in strengths
    ]


def interest_profile(scores: list[InstrumentScore]) -> list[dict[str, Any]]:
    """Rank RIASEC areas by checked activities (report only)."""
    _, riasec = load_strength_texts()
    for instrument_score in scores:
        if instrument_score.instrument_id == "onet-ip-sf":
            ranked = sorted(instrument_score.scales, key=lambda score: score.score, reverse=True)
            return [
                {
                    "id": score.id,
                    "label": riasec[score.id].label,
                    "count": int(score.score),
                    "description": riasec[score.id].text,
                }
                for score in ranked
            ]
    return []


def wellbeing_summary(score: ScaleScore) -> dict[str, Any]:
    """Report-only wellbeing summary with calm, non-diagnostic wording."""
    texts = load_wellbeing_text()
    note = texts.report_note_high if score.band == "high" else texts.report_note_other
    return {
        "name": score.name,
        "score": score.score,
        "position": score.position,
        "band": score.band,
        "note": note,
    }


def build_profile(answers: Answers) -> Profile:
    """Score every answered instrument and scenario and assemble the profile."""
    scores = []
    wellbeing = None
    for instrument_id, responses in answers.instruments.items():
        instrument = load_instrument_by_id(instrument_id)
        if instrument_id not in load_language(
            answers.questionnaire_language
        ).instrument_ids and len(responses) != len(instrument.items):
            # Preserve historical answers, but do not score an unfinished English-only
            # module excluded by the selected language pack.
            continue
        result = score_instrument(instrument, responses)
        if instrument_id in WELLBEING_INSTRUMENTS:
            wellbeing = wellbeing_summary(result.scales[0])
        else:
            scores.append(result)
    scenarios = depth_scenarios(answers.depth, answers.role)
    sjt_means = score_sjt(scenarios, answers.sjt).means
    traits = collect_traits(scores, sjt_means)
    strengths = signature_strengths(traits)
    statements = select_statements(traits, answers.role) + strength_statements(strengths)
    preferences = {preference.id: preference for preference in load_preferences()}
    preference_instructions = {
        preference_id: preferences[preference_id].option(option_id).instruction
        for preference_id, option_id in answers.preferences.items()
    }
    tips = list(load_wellbeing_text().practical_tips) if answers.wellbeing_tips else []
    return Profile(
        name=answers.name,
        role=answers.role,
        role_title=ROLES[answers.role],
        seniority=SENIORITY[answers.seniority],
        depth=answers.depth,
        traits=traits,
        instrument_scores=scores,
        instrument_names={
            s.instrument_id: load_instrument_by_id(s.instrument_id).name for s in scores
        },
        statements=statements,
        preference_instructions=preference_instructions,
        signature_strengths=strengths,
        interests=interest_profile(scores),
        derived_label=derive_label(traits),
        known_results={key: value for key, value in answers.known_results.items() if value},
        note=answers.note,
        wellbeing=wellbeing,
        wellbeing_tips=tips,
    )


def accepted_statements(profile: Profile, review: dict[str, str]) -> list[tuple[Statement, str]]:
    """Apply the review: "yes" keeps the text, "partly" softens it, "no" drops it.

    Statements without a review entry are kept as written; the interactive flow always
    reviews every statement, so this only applies to hand-written answers files.
    """
    accepted = []
    for statement in profile.statements:
        verdict = review.get(statement.id, "yes")
        if verdict == "yes":
            accepted.append((statement, statement.text))
        elif verdict == "partly":
            accepted.append((statement, statement.softened))
    return accepted


def statements_by_section(
    accepted: list[tuple[Statement, str]],
) -> dict[str, list[tuple[Statement, str]]]:
    """Group accepted statements by profile section, in section order."""
    grouped: dict[str, list[tuple[Statement, str]]] = {section: [] for section in SECTIONS}
    for statement, text in accepted:
        grouped[statement.section].append((statement, text))
    return grouped
