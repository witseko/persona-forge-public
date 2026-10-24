# Plan: persona-forge (psychometric work profile and alter egos for Claude Code and Codex)

## Private repository and limited public edition (2026-10-24)

Owner decision: this repository stays private and keeps every instrument. The public
release is a separate, limited copy built by `make public-export DEST=<new folder>`
(`public_export.py`). It leaves out content whose redistribution, commercial-use or
translation permission is unclear, per `data/permissions.json` (`permissions.py`):
GSE, NCS-6, the O*NET Interest Profiler and the Ukrainian NCS-6 and CBI overlays.
The catalogue records item provenance, redistribution, commercial use, translation
and validation separately. Evidence is in the permission research artifact
(`ai-artifacts/persona-forge/prepare-public-release/00-questionnaire-permissions.md`).

`make public-sync` (`public_sync.py`, added 2026-10-24) updates the public repository
(`../persona-forge-public`, or `PUBLIC=<path>`): it refuses a dirty or non-git target
and this repository itself, exports to a temporary folder, mirrors the edition into the
target (removing tracked files that are gone, never touching `.git`), runs the target's
`make test lint` and commits "update public edition". Pushing stays manual.

The export copies only files tracked by git (commit new files first; never `out/` or `.git`),
leaves out `PLAN.md` (internal bootstrap notes), removes withheld ids from language
manifests and sample answer files, then scans the
copy for withheld item text and deletes it if any is found. The app skips instruments
whose data file is absent, and answer files naming one are refused with a clear error.
Tests that check withheld content carry `private_edition_only` and skip in the public
copy. `NOTICE` lists third-party terms for both editions.

Validation: private `make test lint audit` passes (313 tests); in a fresh export,
`make test lint` passes (290 passed, 21 skipped) and non-interactive setup with the
sample answers completes. Code licence: MIT (`LICENSE`, owner-approved 2026-10-24); questionnaire content
keeps its own terms in `NOTICE`. Open: the public repository should be created from the export with new history;
rights-holder questions in the research artifact remain unasked. Security: the export
is a local maintainer command; the destination comes from `DEST` through the
environment, must be new and outside the repository, and git runs with fixed
arguments without a shell. No new dependency or network access.

## Settings menu replaces profile and language variables (2026-10-24)

Owner request: no PROFILE or QUESTIONNAIRE_LANGUAGE variables; use a settings CLI.
`make settings` (`settings_menu.py`) shows the active profile, link state and the
language for new questionnaires, and offers: choose or create a profile, choose a
language (or ask at setup), link or unlink the active profile, start or retake its
questionnaire (archiving first, with confirmation), and copy the original pre-profile
session into a new profile. Choices are stored in `out/settings.json`
(`settings.py`): only a profile slug and a language code, validated on every read
(slug rules, no symlinked file, installed plugins only, no extra keys), written
atomically with owner-only permissions. Other commands use the active profile; when
none is saved, the existing picker asks once and saves the choice. New sessions and
retakes use the saved language; saved sessions keep their own language. The Makefile
no longer exports PROFILE or QUESTIONNAIRE_LANGUAGE, and the CLI ignores them;
`--profile` and `--language` remain as hidden flags for scripts and tests. Security:
no new network, subprocess or dependency; the settings file is local user input with
strict validation, and profile paths still go through `profile_directory`.
Validation: `make test lint audit` passes (304 tests); the menu was checked on an
emulated 80x50 terminal.

## Local profile management (2026-10-24)

Named sessions live in ignored `out/profiles/<slug>/`. Ordinary `make setup` offers
saved people or a new person; `PROFILE=name` selects directly. Profiles have separate
answers, language, review, personas and reports. Setup and persona editing for named
profiles do not install links. `make profiles` lists link status; `make link
PROFILE=name` switches all project-owned active personas to one profile. `make unlink`
removes all project links; a profile argument limits removal to that profile.
`make retake PROFILE=name` confirms, archives that profile's session through the
existing private backup flow and starts a fresh, unlinked questionnaire. `make
preserve PROFILE=name` copies the original single-user results without removing or
overwriting them. Explicit `--out` scripts retain their previous workflow.

The owner's existing six Claude/Codex links were removed as requested. The original
session was copied to a named profile; the copy is complete and unlinked,
and original files were kept. No personal answers were included in tracked files.

Entry points are local CLI arguments, environment variables, terminal menus and
stored profile directories, used by the local OS user. No remote authentication is
needed. Slugs are bounded, path traversal and symlinked profile directories are
rejected, new profile directories are private, existing profiles cannot be overwritten,
and migration refuses symlinked files. Profiles are storage separation, not separate
OS accounts: people sharing the account can read each other's files.

Validation: `make test lint audit` passes with 288 tests, Ruff lint and formatting
clean, and no known dependency vulnerabilities (the unpublished local package is
skipped). Behavior coverage includes profile isolation, switching and stale personas,
scoped and global unlink, retake confirmation and backups, default profile selection,
empty-profile link refusal, migration preservation, invalid slugs and symlinks.
The nine copied real-session files match their originals byte for byte; no active
project links remain. Code-quality checklist completed: reviewed complexity, nesting,
parameters, duplication, unused code and empty blocks. Ruff's cyclomatic limit of
10 passes the profile, CLI and links modules; cognitive complexity was reviewed
manually, and no SonarQube analysis is configured. Security checklist completed:
local entry points and validation reviewed, negative path tests and existing privacy
checks pass, dependency audit passed, and the final diff was reviewed. No new runtime
dependencies or network behavior. The shared OS account remains the privacy boundary.

## Language selection at setup entry (2026-10-24)

New interactive sessions ask for a language before consent and the welcome screen.
Choices come from installed complete language packs and use their native names.
Saved sessions retain their language; explicit CLI or environment overrides skip
the question. No psychological content, scoring or personal answers were changed.

Validation: `make test lint audit` passes (271 tests, Ruff lint and format clean,
no known dependency vulnerabilities; the unpublished local package is skipped).
Code-quality checklist: reviewed changed functions for complexity, nesting,
parameters, duplication, unused code and empty blocks. No SonarQube is configured.
Security checklist: the entry point is local terminal input for the OS user, so
remote authentication does not apply. Language codes use existing validation and
complete plugin discovery. No dependencies, network calls or new security risks.
Reviewed the diff against both guides.

## Session controls as keys (2026-10-24)

Owner request: Back, Next, Pause and Start over no longer appear as answer rows.
`QuestionaryPrompter` removes them from the list and draws a key bar under the
choices (`← Back  → Next  P Pause  R Start over`); P and R end the prompt with the
same control values the session already handles, so `SessionPrompter`, scripted test
prompters and saved data are unchanged. Back and Next appear only when that move is
possible. Revisited questions show "✓ Saved answer: <label>" above the bar and start
with the pointer on it; the hint line is shortened because the bar shows the arrows.
Control constants moved to `navigation.py` (still importable from `session_ui`). New
English and Ukrainian strings: Back, Next, Pause, Saved answer, and the two shortened
hints. Checked in a pseudo-terminal by answering two items and pressing Left.
Validation: `make test lint audit` passes (265 tests).
Follow-up: the answer list stretched to fill spare terminal rows, which pushed the
bar to the bottom of the screen; the list now keeps its own height, so the bar sits
one line under the answers (checked on an emulated 80x50 screen; 267 tests pass).

## Clean screens at the end of the questionnaire (2026-10-24)

Owner report: from the known-result questions to the wellbeing question, each prompt
printed under the previous one and repeated the setup stepper. Fixes: each known-result
question now opens its own screen ("Optional: results you already know", N of 4); the
wellbeing notice, section breaks and a new "Questionnaire complete" notice start a fresh
screen; the stepper is printed once per screen. A fresh screen keeps lines printed since
the last answer (the welcome, a saved value). Saved known-result text is shown raw, so a
typed value such as "INTJ-A" no longer needs a translation in Ukrainian sessions.
Single-option menus say "(press Enter)". Known results now behave like other sections,
so a section break appears before and after them. Checked on an emulated 80x50 screen.

## Remote UI integration (2026-10-24)

Rebased the local language and navigation changes onto the remote module/persona
icons, welcome/resume/halfway moments and finish screen. Preserved both sets of
behavior and moved moment translations into the language catalogs. Module icons
also follow translated titles. Validation: `make test lint audit` passes with
261 tests, clean Ruff checks and no known dependency vulnerabilities (the local
unpublished package is skipped). Reviewed conflict resolutions against the code
quality and security checklists; no new dependencies or security entry points.

## Question navigation correction (2026-10-24)

Left/right now move between questions instead of selecting answer options. Back and
Next are visible in question menus. Up/down selects an answer and Enter saves it;
navigation preserves saved answers, including checkbox blocks. Saved choices are
restored on revisit. Navigation spans instruments, scenarios, preferences, known
result hint menus and optional wellbeing items, and remains available at the final
questionnaire screen. Skipped gaps are revisited before completion. Changed answers
invalidate inferred-statement review while preserving persona choices.

Validation: `make test lint audit` passes with 252 tests. Tests cover real keyboard
navigation, saved selection defaults, first-question boundaries, editing after resume,
cross-section edits, skipped gaps and unchanged optional answers. Code-quality
checklist: reviewed changed functions for complexity, nesting, parameter counts,
duplication, unused code and empty blocks; Ruff lint and format pass. No SonarQube
analysis is configured. An extra cyclomatic check passes changed functions but
reports the pre-existing complexity of untouched `check_known_identifiers` (18);
that function was left outside this change. Security checklist: controls are local OS-user input and
are intercepted before answer persistence; no remote authentication is needed.
Navigation does not remove saved answers. Existing validation, privacy and backup
tests pass; dependency audit reports no known vulnerabilities, skipping the local
unpublished package. Reviewed the diff with no new unresolved security risks.

## Session controls update (2026-10-24)

Answer menus and section breaks now offer Start over next to Pause. Confirmation
is required before the existing cleanup routine archives session files and removes
project-owned links; setup then starts again immediately. Both language packs have
the new controls. The initial horizontal-answer selection behavior was superseded by the
question navigation correction above.

Validation: `make test lint audit` passes with 244 tests, clean Ruff checks, and no
known dependency vulnerabilities (the unpublished local package is skipped).
Behavior tests cover both arrow directions, confirmed and declined restarts, saved
backups, and checkbox controls. Code-quality checklist: reviewed changed functions
for complexity, nesting, parameters, duplication, unused code and empty blocks.
No SonarQube analysis is configured; complexity review was manual.
Security checklist: entry points are local terminal controls used by the OS user,
so remote authentication is not applicable. Control values never become answers.
Restart defaults to cancellation and reuses the tested private backup and managed
link cleanup paths. Reviewed the diff; no new dependencies or network operations,
and no new unresolved security risks identified.

## Language plugin milestone (2026-10-24)

The owner expanded translation scope to the complete interactive setup and requested
contributor-friendly language plugins. English and Ukrainian now have separate JSON
catalogs and manifests under `data/languages/`; the six Ukrainian instrument overlays
were moved there without changing their wording or scoring. Consent, menus, authored
scenarios, review, personas and completion text use the selected pack. Missing messages
fail explicitly. GSE and O*NET are excluded from Ukrainian assessments pending verified
translation permission. Estimates and progress reflect each pack's instrument subset.
Reports and agent instructions stay English, and polish previews preserve exact text.

`make languages` validates installed complete packs. Draft packs are not selectable.
See [the contributor guide](languages.md) for schemas, coverage and permission review.
The published Ukrainian adaptation follow-up plan in `instruments.md` remains open.
Interactive setup stops before continuing an incompatible partially answered
instrument; existing personal answers are preserved. Terminal startup clears the
visible screen and scrollback on supported terminals, preserving saved progress and
shell history. The other agent's framed panels, stepper and module plan are retained.

Validation: `make test lint audit` passes with 239 tests, clean Ruff lint/format and
no known dependency vulnerabilities. The unpublished local package is skipped by
pip-audit. Tests exercise all five Ukrainian roles at all three depths, localized
consent, third-pack discovery, missing translations, unsupported modules, invalid
placeholders, controls, scoring changes, symlinks and path traversal.

Security checklist completed: entry points are local CLI language selection and
bounded JSON resources used by the local OS user, so no remote authentication is
needed. Codes, manifest fields, placeholders and instrument coverage are validated;
plugins execute no code and add no dependencies or network calls. Instrument overlays
cannot modify scoring definitions. Existing privacy and agent-output tests pass.
The diff was reviewed against the security guide. Remaining limitation: automated
checks cannot establish translation quality, psychological validity or reuse rights;
project-authored Ukrainian instruments still need independent review.

Code-quality checklist completed: changed functions were reviewed for complexity,
nesting, parameters, duplication and unused code. Dedicated validation and constants
modules keep dependencies one-way. Ruff's cyclomatic limit of 10 passes for the new
language modules and changed CLI, flow and session UI modules. No SonarQube analysis
is configured, so cognitive complexity was reviewed manually, not measured. Historical
complexity in unrelated questionnaire/persona functions was left outside this change.

## Implementation status (2026-10-23, second session)

Checks on the locked environment (Python 3.12.15, uv 0.13.1, `uv.lock`):
`make test lint audit` passes: 140 tests, Ruff lint and format clean, pip-audit reports
no known vulnerabilities (pytest was raised from 8.4.2 to 9.0.3 to fix PYSEC-2026-1845).

- M0 done. A private GitHub repository holds `main`. The first commit and push were
  made on 2026-10-23 at the owner's request.
- M1 done. `uv.lock` generated; the venv uses a uv-managed Python 3.12.15.
- M2 done, reworked. The schema now supports per-item response sets (labels and
  values from the source), mean or sum aggregation, and domains that pool facet
  scales. Bands use the position of the mean answer within the response range
  (below 0.4 low, above 0.6 high), which reproduces "below 2.6 / above 3.4" on 1 to 5.
- M3 done for the approved scope. Eight instruments were extracted by script from
  primary sources and checked against independently transcribed counts and keys.
  Owner decisions (2026-10-23): drop Grit-S, Need for Closure-15 and rMEQ (permission
  unverified); include GSE and NCS-6 under their research-worded grants with credit;
  offer the 40-item IPIP Honesty-Humility facets and the 213-item revised IPIP-VIA at
  Deep depth (no sourced short forms exist). See `docs/instruments.md`.
- M4 done. Quick, Standard and Deep depths; five role tracks; consent screen; resume
  after every answer (verified in a real pseudo-terminal, including Ctrl-C); the
  non-interactive `ANSWERS=` path. Scenario banks: 12 shared plus 12 per role.
  Estimated times from item counts: Quick about 11 minutes, Standard about 26, Deep
  about 62 (longer than the 45 originally planned, because of the full sourced sets).
- Readability (owner feedback): one question per screen with a progress header, a short
  hint and wrapped scenario text. IPIP items are shown with "I" added (owner decision;
  IPIP permits wording edits); all other item wording is unchanged, and tests check both.
- M5 done. Table-driven first-person rules in `data/insights`, role-aware rules,
  yes / partly / no review, derived four-letter label shown only in the report.
- M6 done. Claude rules file and output styles, Codex `pf-*.config.toml`, offline
  HTML report (inline SVG, light and dark, checked visually at desktop and phone
  widths). Golden-file and TOML round-trip tests.
- M7 done. Eight presets, complement and mirror egos, up to three custom egos,
  `make ego`.
- M8 implemented; real-machine check pending. `links.py` backs up, is idempotent,
  removes only its own links and cleans its own dangling links. The non-interactive
  end-to-end run with a temporary home passes, including "twice changes nothing" and
  "unlink keeps backups". Codex 0.163.0 was verified to load a generated profile with
  `CODEX_HOME=<temp> codex -p pf-mentor debug prompt-input` (profile and persona appear
  in a developer message; no model call). Claude Code docs confirm `~/.claude/rules/`
  and `~/.claude/output-styles/` are read (symlinked rules are skipped only in Cowork
  sessions). Not yet done on this machine: a real `make setup` with the owner's own
  answers, then `/output-style` and `/memory` in Claude Code and a live
  `codex -p pf-mentor exec`. Optional polish is implemented and tested with the
  subprocess mocked; it has not been run against the real `claude` or `codex` CLIs.
- M9 partial. The CBI work scale is the opt-in wellbeing module; results appear only
  in the report, and tests confirm agent files never contain scores, screener names
  or wellbeing wording (tips only with explicit consent). ASRS v1.1 is blocked: its
  primary terms page could not be retrieved, including through Chrome and DevTools
  on 2026-10-23 (timeout with `www`; Imperva proxy hostname resolution error without
  `www`). Reuse permission remains unverified, so it is not included. See
  `docs/instruments.md` for the access findings and next steps. Security
  checklist completed (see below).

Security review: the only caller is the local OS user. Entry points are CLI
arguments, the answers file and the optional polish subprocess. Answers are read with
a size limit, validated strictly (unknown fields, identifiers, values and over-long
text are refused) and cleaned of control characters. Generated file names come only
from validated slugs. Report text is HTML-escaped; TOML and YAML values are escaped
or quoted, with tests for hostile names. Personal files are written atomically with
owner-only permissions in ignored `out/`. Polish uses an argument list without a
shell, a timeout, no agent tools (`--tools ""` for Claude, a read-only sandbox for
Codex), shows the exact payload first, validates the reply and saves only after the
user accepts a diff. Remaining risks: the user's own free-text note is copied into
agent instructions by design; polish output is model text the user must read before
accepting.

Resume: real-machine M8 check, and ASRS if its terms can be verified.

Ukrainian support requested on 2026-10-23: psychological questionnaires only,
including their instructions and response options. The owner subsequently approved
project-authored translations while retaining the published-translation plan.
Implemented for four IPIP instruments, NCS-6 and CBI (406 items). GSE and O*NET
remain English pending verified translation permission; see `docs/instruments.md`.
Use `make setup QUESTIONNAIRE_LANGUAGE=uk` for a new session. Saved sessions retain
their language; conflicting overrides are rejected. Existing answer files default to
English. Display-only overlays preserve all scoring definitions and response values.
This request does not expand to translating menus, authored work scenarios, reports
or generated agent instructions.

Ukrainian milestone validation (2026-10-23): `make test lint audit` passes with
168 tests and clean Ruff lint/format checks. pip-audit reports no known dependency
vulnerabilities; the local, unpublished `persona-forge` package itself is skipped.
Security checklist: entry points are the local user's CLI flag, environment variable
and saved language field, all restricted to `en` or `uk`. Translation files are
bounded local JSON overlays with complete item/response coverage and no scoring fields.
Negative tests cover invalid languages and malformed overlays; agent-output comparisons
confirm that language selection does not change agent instructions. No dependency or
network behavior was added. Remaining limitation: project translations have not been
independently reviewed or psychometrically validated in Ukrainian.

Session reset added on 2026-10-23: `make clean` archives saved answers, profiles,
polish state and generated agent files into an owner-only `out/backups/session-*`
directory, then removes only this project's configuration links. Earlier backups
and unrelated files remain in place. Run `make setup QUESTIONNAIRE_LANGUAGE=uk`
afterward to restart in Ukrainian. The language-conflict error now points to this
command. The user's real session was not reset during implementation.

Clean milestone validation: `make test lint audit` passes (174 tests, Ruff lint and
format clean, no known dependency vulnerabilities; local package skipped as above).
Security checklist: the new entry point is a local-user CLI command; only fixed session
paths are archived, output/backup symlink roots are refused, backup directories are
private and unique, and existing link-ownership checks govern removal. Tests cover
preservation, repeated clean, restart in another language and unsafe backup paths.
No dependencies or network behavior were added. Backups retain personal answers by
design and stay in ignored `out/`.

Ukrainian wellbeing fix (2026-10-23): the reported English CBI screen was reproduced
with a failing regression test. The cause was deliberate English fallback for a
missing CBI overlay. Added the seven project-translated questions, both response
sets, Ukrainian title and work-specific hint under NFA's free-use grant (the
interpretation is recorded in `docs/instruments.md`). The published-translation
follow-up plan remains. Actual languages are now recorded per instrument, and older
partly answered CBI modules continue in English to avoid mixed-language administration.
Unanswered CBI modules use Ukrainian after restarting the CLI; personal answers were
not changed during implementation.

Validation: `make test lint audit` passes (179 tests, clean Ruff lint and format,
no known dependency vulnerabilities; local package skipped as above). The exact
reported screen now passes its regression test. Security checklist: language records
are bounded and allowlisted, unknown instrument references are refused, scoring keys
and response values remain unchanged, and privacy/agent-output tests still pass. No
network behavior or dependencies were added. The Ukrainian wording remains a project
translation without independent language review or psychometric validation.

Pause and overall progress (2026-10-23): interactive setup now offers "Pause and
continue later" in single-choice and checkbox menus and a continue/pause menu
between sections. `make setup` offers to continue a saved session. Explicit pause
and Ctrl-C save progress and exit successfully, without make reporting a failure.
An unsubmitted question or checkbox block is left unanswered. Optional known-result
prompts (including blanks) and custom persona drafts now save incrementally and
resume without repeating completed choices.

Each prompt shows the overall questionnaire answer count, bar and percentage alongside
the existing section display. Totals cover instrument items, scenarios, preferences,
four optional known-result prompts and the wellbeing opt-in decision. Opting in adds
the seven wellbeing questions; the undecided state explains that possible addition.
A separate four-stage indicator covers questionnaire, profile review, personas and
file generation. Resuming during review or persona selection shows the corresponding
stage instead of presenting a completed questionnaire as the whole setup.

Validation: `make test lint audit` passes (192 tests, clean Ruff lint/format, no known
dependency vulnerabilities; the local package is skipped as above). Tests include the
real questionary menu driven by keyboard input, pause/resume, section breaks, checkbox
controls, optional totals, custom drafts and Ukrainian labels. Security checklist:
the new controls are local-user input; pause is intercepted before answer conversion
or scoring; draft fields and values are strictly validated; private atomic saves are
unchanged. Personal files were not altered during implementation, and no network or
dependency changes were introduced. No new security risks were identified.

Terminal look (owner request, 2026-10-23): the questionnaire now follows the "Persona
Forge CLI" design system (https://claude.ai/artifact/5Ljz3JfFvSEhmTAeRcP5T3).
`terminal_ui.py` builds rich panels, the setup stepper, the module plan table and
section rules; `QuestionaryPrompter` applies a matching questionary style. Dark and
light palettes are picked by `PERSONA_FORGE_THEME` or `COLORFGBG`. The `Prompter`
interface is unchanged; the new display steps (`notice`, `progress`, `plan`,
`section_done`) are optional and fall back to plain text, so test prompters and all
saved progress text stay the same. Checked in a real pseudo-terminal through consent,
profile questions, the plan, instructions, the first item and Ctrl-C. Checks: `make test
lint audit` passes (203 tests, Ruff clean, no known vulnerabilities). Blocked:
`~/.agents/guides/security.md` and `python.md` are not present in the cloud session used
for this change, so their checklists could not be read; the change adds no input paths,
files, network or dependencies.

Personality layer (owner request, 2026-10-23): one emoji per module title, per persona
and per moment (welcome, welcome back with the resume point, halfway once per run,
forging, and a finish panel listing personas with their pf- names and next commands).
Emoji never appear in item text, answer labels, the wellbeing module, the report or
generated agent files. Every icon is a single wide emoji without a variation selector,
which a test enforces so box borders stay aligned. `PERSONA_FORGE_EMOJI=0`, `TERM=dumb`
or a non-UTF-8 terminal turns them off. Checked start to finish in a pseudo-terminal at
Quick depth. `make test lint audit` passes (212 tests).

The current user instruction requires explicit authorization for commits and pushes;
the historical kickoff wording below does not override that instruction.

## Context

Vitalii wants a private project that runs a short, mostly multiple-choice questionnaire built on recognised psychological instruments, aimed at IT roles (Software Engineer, Engineering Manager, PM, PO, CTO). The results produce:

1. A **work profile** that teaches Claude Code and Codex how to work with the user: communication style, decision style, strengths to lean on, growth points to nudge.
2. **Alter egos**: personas the agent adopts on demand (strict reviewer, mentor, devil's advocate, a "complement" persona built from the user's growth points, a "mirror" persona that writes in the user's voice, custom ones).
3. A local HTML report on personality, strengths and points of growth at work.

`make setup` runs the whole setup phase and ends by symlinking the generated files into `~/.claude` and `~/.codex`, following the existing pattern in `~/dev/personal/agent-config/links.sh` (back up anything in the way, never delete, uninstall only links that point into the repo).

The implementing agent starts with milestone M0: init the repo, refine the user's brief into a white paper, move this plan to `docs/implementation-plan.md`, and push to a private GitHub repo. It then implements M1 to M9, following `docs/implementation-plan.md` and the repo `AGENTS.md`. This file starts as `PLAN.md` in the project folder.

Decisions confirmed with the user: both directions (agent knows me + alter egos), terminal CLI, opt-in wellbeing module, private GitHub repository.

## Facts verified on this machine (2026-10-23)

- Claude Code 2.1.309 supports **output styles** (`~/.claude/output-styles/*.md`, frontmatter `name`, `description`, `keep-coding-instructions`) and **rules** files (`.claude/rules/*.md`). `~/.claude/CLAUDE.md` is a symlink into `agent-config`, so persona-forge must not edit it.
- Codex 0.163.0: the built-in `personality` feature is **removed**. `codex -p <name>` layers `$CODEX_HOME/<name>.config.toml` on top of `config.toml`; legacy `[profiles]` tables can no longer be written. The config key `developer_instructions` (non-blank string) adds instructions. `~/.codex/AGENTS.md` is a symlink into `agent-config`; `AGENTS.override.md` would replace it, so never create that.
- `uv` 0.13.1 is installed; system Python is 3.9, so the project pins Python 3.12 through uv.

## M0: repo bootstrap and documents

The original brief from the user, to refine into the white paper:

> Questionnaire using well-known psychological tests to: 1) understand your personality; 2) understand your strong sides and points of growth at work; 3) a setup phase whose result adds your personality to Claude and Codex, and can craft alter egos; 4) after the setup phase, `make setup` adds symlinks in the corresponding profiles; 6) the setup phase should be easy, using modern and classic psychology tests and other tests modern psychology or psychiatry can offer, mostly giving answer options and asking for typed input only in some cases; 7) the audience is the IT industry: software engineers, engineering managers, PMs, POs, CTOs and so on; 8) a private git repo in this folder holding the artifacts, with these instructions saved as a professional white paper.

1. In `~/dev/personal/persona-forge` (already holds `PLAN.md`), run `git init -b main`.
2. Write:
   - `docs/whitepaper.md`: the refined brief (outline below).
   - `docs/implementation-plan.md`: move `PLAN.md` here (`git mv` after the first add, or plain `mv`), keeping milestones and acceptance criteria.
   - `docs/instruments.md`: the instrument catalogue table (below) with columns for source URL, licence, and a "verified" flag that Codex fills in during M3.
   - `AGENTS.md`: project rules for Codex (stack, layout, commands, "never invent test items", the dash rule, stop-and-report rule). `CLAUDE.md` is one line: `@AGENTS.md`.
   - `README.md` (short: what it is, `make setup`, privacy note), `.gitignore` (`out/`, `.venv/`, `__pycache__/`, `.idea/`).
3. First commit `add white paper and implementation plan`, with no AI attribution (the user's global rule).
4. Create the private GitHub repository and push `main`.
5. Add a line to `~/dev/personal/ai-artifacts/INDEX.md` pointing at the repo docs (the docs themselves live in the repo, as the user asked).
6. Continue with M1. If the work is split across sessions, the kickoff prompt below resumes it.

### White paper outline (`docs/whitepaper.md`)

1. Abstract: a psychometric work profile that makes AI coding agents adapt to the person, plus switchable agent personas.
2. Problem: agents default to one generic voice; people in IT differ widely in how they take feedback, decide, and focus. Self-knowledge of strengths and growth areas is valuable but usually locked in paid, proprietary tests.
3. Goals and non-goals. Goals: under 25 minutes, mostly multiple choice, local-only data, outputs for Claude Code and Codex, a growth report. Non-goals: clinical diagnosis, hiring or selection decisions, performance evaluation, sharing data with third parties.
4. Audience: SE, EM, PM, PO, CTO / Head of Engineering, with role-tailored scenarios.
5. Method: validated public-domain or free instruments (Big Five, HEXACO Honesty-Humility, character strengths, grit, self-efficacy, cognitive style, chronotype, vocational interests), IT situational judgment tests (a standard modern industrial-organisational method), and a self-verification step where the user confirms or rejects each generated statement (reduces the Barnum effect).
6. Setup phase: depth levels, flow, time budget, where input is required.
7. Outputs: work profile, alter egos, report; how they plug into Claude Code (rules + output styles) and Codex (`-p` profiles).
8. Ethics, privacy, licensing: local-only, opt-in wellbeing screeners with non-diagnostic wording, proprietary tests (MBTI, CliftonStrengths, DISC, Enneagram RHETI, Belbin, TKI) are never reproduced, only their existing results can be typed in.
9. Limitations: self-report bias, raw bands not population norms, short forms are less reliable.
10. Roadmap: peer (360-lite) observer form, Claude subagents per alter ego, re-test and trend tracking.

## Architecture (for Codex)

Stack: Python 3.12 via uv, `questionary` (arrow-key prompts) and `rich` (tables, progress) as the only runtime deps, `pytest` + `ruff` (with `S` rules) + `pip-audit` for dev. Stdlib for everything else (`json`, `string.Template`, `tomllib` for verifying generated TOML, `argparse`, `subprocess` with arg lists).

```
persona-forge/
  Makefile  pyproject.toml  uv.lock  AGENTS.md  CLAUDE.md  README.md
  docs/whitepaper.md  docs/implementation-plan.md  docs/instruments.md
  data/instruments/<id>.json     # items, keys, scales, citation, source_url, licence (committed)
  data/sjt/<role>.json           # authored IT scenarios (committed)
  data/insights/*.json           # score band -> statements, agent tips (committed)
  data/egos/presets/*.json       # alter ego presets (committed)
  src/persona_forge/
    cli.py           # argparse: setup, ego, report, link, unlink, status
    model.py         # dataclasses: Instrument, Item, Scale, Answer, ScaleScore, Profile, Ego
    instruments.py   # load + validate instrument JSON
    scoring.py       # Likert with reverse keys, scale means, bands; SJT dimension weights
    questionnaire.py # runs modules, saves after every answer, resumes
    flow.py          # setup steps, depth levels, role tracks
    profile.py       # scores -> Profile (traits, strengths, growth points, preferences)
    insights.py      # table-driven rules from data/insights
    egos.py          # presets, complement ego, mirror ego, custom crafting
    render_claude.py # rules file + output styles
    render_codex.py  # <name>.config.toml with developer_instructions
    render_report.py # self-contained HTML report, inline SVG charts
    polish.py        # optional prose polish via `claude -p` / `codex exec`
    links.py         # symlink install/uninstall with backup (port of agent-config/links.sh)
  out/   (gitignored) answers.json, profile.json, claude/, codex/, report.html
  tests/
```

Make targets: `setup` (questionnaire, resume if partial, review, egos, generate, link), `ego` (craft or edit one alter ego, regenerate, relink), `report` (regenerate and open HTML), `link`, `unlink`, `status`, `test`, `lint`, `audit`. `setup` accepts `ANSWERS=path` for non-interactive runs (tests and re-generation).

### Instrument catalogue (Codex verifies source and licence in M3)

| Module | Instrument | Items | Licence (to verify) | Depth |
|---|---|---|---|---|
| Personality | Mini-IPIP (Donnellan et al. 2006) | 20 | IPIP public domain | Quick |
| Personality | IPIP-NEO-120 (Johnson 2014), 5 domains, 30 facets | 120 | IPIP public domain | Standard, Deep (replaces Mini-IPIP) |
| Personality | IPIP HEXACO Honesty-Humility scale | 10 | IPIP public domain | Standard+ |
| Strengths | IPIP-VIA proxy scales (24 character strengths) | 4 per strength short / full in Deep | IPIP public domain; short form flagged "not validated" | Standard+ |
| Drive | Grit-S (Duckworth and Quinn 2009) | 8 | free for non-commercial use | Standard+ |
| Drive | General Self-Efficacy Scale (Schwarzer and Jerusalem) | 10 | free to use | Standard+ |
| Thinking | Need for Cognition short form (NCS-6) | 6 | research use | Standard+ |
| Thinking | Need for Closure short form (Roets and Van Hiel 2011) | 15 | research use | Deep |
| Rhythm | reduced Morningness-Eveningness (rMEQ, Adan and Almirall 1991) | 5 | research use | All |
| Career | O*NET Interest Profiler Short Form (RIASEC) | 60 | US DOL public domain | Deep |
| Work | IT situational judgment tests (authored for this project) | 8 / 16 / 24 | own content | All |
| Agent fit | Collaboration preferences (authored) | about 10 | own content | All |
| Wellbeing (opt-in) | ASRS v1.1 Part A (WHO) | 6 | free screener, verify terms | Offered at end |
| Wellbeing (opt-in) | Copenhagen Burnout Inventory, work-related scale | 7 | free, no permission needed | Offered at end |

The MBTI-style 4-letter label is **derived** from Big Five scores (E/I from Extraversion, S/N from Openness, T/F from Agreeableness, J/P from Conscientiousness), shown as "approximate, for familiarity only", with no extra items. Known results from proprietary tests (16Personalities, CliftonStrengths top 5, DISC, Enneagram) can be typed in as optional hints. That is the only free-text input besides name and role.

Rule for Codex: **item text, keying and scale membership are copied from the primary source** (ipip.ori.org, the authors' published papers, onetcenter.org, WHO, NFA Denmark), and each instrument JSON records `source_url`, `retrieved` date and `licence`. If a source cannot be fetched or the licence does not allow use, stop and report. Never write items from memory.

### Setup flow (Standard depth, about 25 minutes)

0. Privacy and consent screen (data stays in `out/`, nothing is sent anywhere unless polish is chosen), depth (Quick 10 min / Standard 25 / Deep 45), role track, seniority. Input: name or nickname only.
1. Personality, 2. Strengths and drive, 3. Thinking and rhythm, 4. IT scenarios for the role (each scenario has 4 options mapped to dimensions: conflict mode on the 5-mode model, decision speed vs thoroughness, risk appetite, ownership, directness, feedback giving and receiving), 5. Agent collaboration preferences (verbosity, tone, push-back level, explanation depth, autonomy, output format, language).
6. Optional: known results, wellbeing opt-in.
7. **Review**: each generated statement shown with "yes / partly / no"; "no" drops it, "partly" softens it. Then free-text "anything the agent must know" (optional, length-limited).
8. Alter egos: pick presets, accept the suggested complement ego, optionally craft a custom one through multiple choice (purpose, bluntness, warmth, detail, risk stance, humour).
9. Generate, show a summary of files, link.

Answers are saved after each item, and Ctrl-C resumes where it stopped.

### Outputs and where they link

| Generated file in `out/` | Link | Used by |
|---|---|---|
| `claude/rules/persona-forge-profile.md` | `~/.claude/rules/persona-forge-profile.md` | always on in Claude Code |
| `claude/output-styles/pf-<ego>.md` | `~/.claude/output-styles/pf-<ego>.md` | `/output-style` or `/config` |
| `codex/pf-me.config.toml` | `~/.codex/pf-me.config.toml` | `codex -p pf-me` (work profile) |
| `codex/pf-<ego>.config.toml` | `~/.codex/pf-<ego>.config.toml` | `codex -p pf-<ego>` (profile + ego) |
| `report.html` | none | the user |

- Work profile sections: who I am at work (role, short trait summary), how to talk to me, how I decide, strengths to lean on, growth points (with concrete agent nudges, e.g. "suggest tests before refactors"), collaboration preferences, never do. Keep it under about 60 lines so it doesn't crowd the context.
- Output styles set `keep-coding-instructions: true`, so the persona sits on top of normal coding behaviour.
- Codex TOML: `developer_instructions` as a TOML basic multiline string with escaping; every generated file must round-trip through `tomllib` in tests.
- Codex has no include mechanism and the profile is opt-in through `-p`, so `make setup` prints a suggested alias `alias codex='codex -p pf-me'` and does not edit shell files or `config.toml`.
- Wellbeing results never go into agent files unless the user explicitly ticks "add practical tips"; even then only the tip text goes in (e.g. "break work into small steps"), never scores or screener names. High scores show a calm, non-diagnostic note suggesting a professional conversation.
- `links.py` checks that `~/.claude/rules` is actually read (M8 manual check). If not, it prints the `@` import line for the user to add to `agent-config/CLAUDE.md` instead of editing that repo.

### Optional prose polish

`polish.py` sends `profile.json` (no wellbeing data) to `claude -p` or `codex exec` (subprocess with an argument list, timeout), asks for improved wording with the same headings, and validates the output: required headings present, under the size limit, no code fences that contain commands. It shows a diff and writes only after the user accepts. If neither CLI is present or the call fails, the template text is used.

## Milestones for Codex (each ends green on `make test lint`)

- **M1 Skeleton**: pyproject (Python 3.12, deps pinned, uv.lock), Makefile, `cli.py` with subcommands stubbed, ruff with `S` rules, one smoke test.
- **M2 Scoring core**: model dataclasses, instrument loader with schema validation, Likert scoring with reverse keys, bands (low below 2.6, mid, high above 3.4 on a 1 to 5 mean, labelled "not normed"), SJT weights. Tests on hand-computed fixtures.
- **M3 Instrument data**: JSON for every catalogue row, copied from primary sources, `docs/instruments.md` filled in and marked verified. Tests: item counts, every scale has items, reverse keys match the source tables.
- **M4 Questionnaire and flow**: depth levels, role tracks, resume, consent screen, non-interactive `ANSWERS=` path. Author the SJT banks (24 scenarios per role track, realistic IT situations: code review dispute, 2 a.m. incident, scope creep, estimate pressure, tech debt vs features, hiring call, underperformer 1:1, ambiguous requirements, stakeholder escalation, build vs buy).
- **M5 Profile and insights**: rules in `data/insights`, phrased as tendencies, never labels or stereotypes, role-aware. Review step (yes/partly/no). Derived 4-letter label.
- **M6 Renderers**: Claude rules and output styles, Codex TOML, HTML report (self-contained, inline SVG, light and dark, works offline). Golden-file tests and TOML round-trip test.
- **M7 Alter egos**: presets (mentor, strict reviewer, devil's advocate, pair programmer, architect, product thinker, executive/CTO lens, coach), complement ego from the top growth points, mirror ego, custom crafting, `make ego`.
- **M8 Links and end to end**: `links.py` (backup, idempotent, uninstall only own links, `--home` override for tests), `make setup` full run, alias hint, optional polish.
- **M9 Wellbeing module and hardening**: opt-in screeners with the rules above, privacy text, README, security checklist from `~/.agents/guides/security.md` (entry points are CLI args, answers file and subprocess calls: validate lengths, keep paths inside `out/`, `shell=False`), `pip-audit`.

Kickoff prompt for a new session:

> Read AGENTS.md and docs/implementation-plan.md (or PLAN.md before M0) in this repo. Implement the first unfinished milestone, run `make test lint`, commit with a short imperative message, then continue with the next milestone. Stop and report if an instrument source cannot be verified.

## Verification

- `make test lint audit` green after every milestone.
- Non-interactive end to end: `HOME=$(mktemp -d) make setup ANSWERS=tests/fixtures/answers_standard.json` creates every file in the table above and the links point into `out/`; running it twice changes nothing; `make unlink` removes only its own links and leaves backups.
- Real check on this machine: `make setup`, then in Claude Code run `/output-style` (the `pf-*` styles are listed) and `/memory` (the profile rules file is loaded); run `codex -p pf-mentor exec "Who are you and how will you talk to me?"` and confirm the answer reflects the persona and the profile.
- Open `out/report.html` offline in a browser: charts render in light and dark mode.
