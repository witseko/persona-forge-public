# Persona Forge: work profiles and agent personas

## Abstract

Persona Forge is a proposed local tool that translates self-reported work tendencies
and explicit preferences into instructions for AI coding assistants. It combines a
questionnaire, a user review of the resulting statements, switchable agent personas,
and a private HTML report. The user remains the authority on how they want to work.

Mission: make AI assistants work the way you do, not the other way round. A synthetic
pilot ([plain summary](evaluation-summary.md)) found that explicit, written preferences
drive the benefit, while questionnaire-derived statements added no measurable value. The
questionnaire is therefore positioned as guided reflection that helps people find and
word their preferences, not as a measurement of who they are.

## Problem and audience

Generic assistant behavior does not account for differences in feedback preferences,
decision making or focus. Personality assessments can support reflection, but their
results rarely translate into concrete collaboration practices. Proprietary tests can
also restrict access and reuse.

The intended audience includes software engineers, engineering managers, product
managers, product owners, CTOs and heads of engineering. Role-specific situations
provide work context without treating role titles as personality categories.

## Goals and boundaries

The standard experience takes about 25 minutes, with mostly multiple-choice input.
Estimates from item counts are about 11 minutes for Quick, 26 for Standard and 62 for
Deep. Deep is longer than first planned because it uses complete sourced scale sets
rather than invented short forms. These are estimates, not measured completion times.
Outputs should be understandable, editable, private and useful during real work.

The tool does not diagnose conditions, evaluate employees, select candidates or send
results to third parties by default. Scores must not be presented as objective ability
ratings, population percentiles or predictions of job performance.

## Method

The catalogue combines Big Five personality measures (Mini-IPIP, IPIP-NEO-120),
IPIP Honesty-Humility facets, revised IPIP-VIA character-strength scales, general
self-efficacy, need for cognition and O*NET vocational interests. Every included
instrument was copied from its primary source, including response anchors, reverse
keys and scale membership, and its reuse terms were checked. Grit, need for closure and
chronotype measures were dropped because permission for this use could not be
verified; see `docs/instruments.md`.

Project-authored IT situations and collaboration questions cover conflict, risk,
ownership, feedback, communication and autonomy. They are reflective prompts, not
validated psychological tests. No unvalidated short forms are used: the character-strength scales are the full
published IPIP-VIA set. Raw score bands are not population norms.

Every generated personal statement is reviewed as yes, partly or no. Rejected
statements disappear; partial agreement softens the wording. This review helps address
overgeneralized interpretations, but does not itself validate the assessment.

## Setup experience

The user chooses or creates a local profile, then selects a questionnaire language.
Privacy and consent information follows, then the user chooses depth, role and
seniority and enters a name or nickname. Modules cover personality, strengths and
drive, thinking and rhythm, role situations, and explicit agent preferences. Answers
are saved after each item so interrupted sessions can resume.

The psychological questionnaires support an optional Ukrainian language setting.
The four IPIP instruments, NCS-6 and CBI use project-authored translations of the sourced
English text, explicitly labelled as not psychometrically validated in Ukrainian.
GSE and O*NET are excluded from Ukrainian sessions until translation permission is
verified. The language is saved with the answers. The complete interactive setup,
including menus, consent and authored scenarios, uses that language. Reports and
agent instructions remain English. JSON language plugins declare complete UI coverage
and their permitted instrument subset; contributors can add packs without Python changes.
Published Ukrainian adaptations remain a future replacement goal.

Existing proprietary test results can be entered as optional hints without reproducing
their questions. The wellbeing module (a short work-energy scale) requires a separate opt-in. After reviewing the
profile, the user may add a length-limited note and choose or craft personas through
multiple-choice questions. Generation ends with a file summary. Named profiles remain
unlinked until explicitly activated. Each person has separate saved answers and
outputs, and retakes archive previous results. Linking a profile replaces the previous
profile's project-managed links. Profiles share the local OS account's access rights;
they are not an authentication boundary.

## Outputs and integration

The work profile covers communication, decisions, strengths, growth nudges and
collaboration preferences in about 60 lines. Explicit preferences should take priority
over inferred traits. Presets include mentor, reviewer, devil's advocate, pair programmer,
architect, product thinker, executive lens and coach. A complement persona supports
growth areas; a mirror persona reflects the user's accepted preferences.

The Claude integration uses a user-level rules file and output styles that retain coding
instructions. The Codex integration uses named configuration files containing developer
instructions, selected explicitly with `codex -p`. Both were checked against Claude Code
2.1.309 documentation and Codex 0.163.0 on 2026-10-23.
Existing global instructions and shell configuration must remain intact. Link conflicts
are backed up and uninstall removes only links owned by this project.

The offline report provides explanations and charts with light and dark presentation.
An optional approximate four-letter label may be derived for familiarity only. It is
not an MBTI assessment or a validated equivalence to one.

## Ethics, privacy and licensing

Answers and generated artifacts stay in ignored `out/`. Generated agent files contain
only accepted work guidance. Wellbeing scores and screener names are excluded; even
practical tips require explicit consent. Screener feedback is non-diagnostic and may
suggest discussing concerns with a qualified professional.

Optional prose polishing requires a separate disclosure of the outgoing payload,
excludes wellbeing data and requires accepting the resulting diff before saving.
Proprietary instruments such as MBTI, CliftonStrengths, DISC, RHETI, Belbin and TKI are
not reproduced. Free access or research permission alone does not establish permission
to redistribute items in this project.

## Limitations and roadmap

Self-report reflects context, interpretation and response bias. Short forms lose detail,
and questionnaire findings should be treated as tentative tendencies rather than fixed
identities. Neither authored scenarios nor raw bands establish clinical or occupational
validity. User review and editability remain central safeguards.

Future work may include an observer form, persona-specific Claude subagents, and
trend tracking across retakes. These are outside the initial implementation milestones.
