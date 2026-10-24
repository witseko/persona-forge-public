# persona-forge

Start here: run `make setup` in this folder.

Interactive setup clears the terminal display and scrollback before its first prompt,
including when resuming. Saved questionnaire progress and shell history are preserved.

A private, local questionnaire about how you work. It teaches Claude Code and Codex
how to work with you, adds switchable agent personas, and writes an offline report.

## First run (about 30 minutes)

1. Install [uv](https://docs.astral.sh/uv/) if `uv --version` fails.
2. Run `make setup`, then choose a saved profile or create a new one.
3. Choose the questionnaire language, then pick a depth: Quick (about 11 minutes), Standard (about 26) or Deep (about 62).
4. Answer the questions. One question per screen; use up/down or a number to choose an answer, then Enter to save.
5. Review the statements (yes, partly or no) and pick personas.

Stopping is safe. Press Ctrl-C at any time; `make setup` continues where you stopped.

Session controls are keys, shown in a bar under each menu instead of as answers:

```
 ←  Back    →  Next    P  Pause    R  Start over
```

**P** (Pause) saves your progress and exits successfully. Run `make setup` again and
choose **Continue** to resume at the next unanswered question. Use Ctrl-C at text or
yes/no prompts. The current unsubmitted answer or checkbox block is not saved.

**R** (Start over) asks for confirmation, backs up the current session in
that profile's `backups/` directory, and immediately returns to the beginning of setup.

**Left/Right** (Back/Next) browse questions across sections; each key appears only
when there is a question in that direction. When you return to an answered question,
your saved answer is selected and shown as "✓ Saved answer". Moving does not save an
edit; press **Enter** to save only answers you want to change. Unanswered questions
remain unanswered when skipped and must be completed before continuing. The final
**Review answers or continue** screen lets you go back through a completed questionnaire.
Optional free-text hints have a navigation menu before the text editor.

Each question now shows overall questionnaire progress as well as section progress.
The total covers all instruments, work situations, preferences, optional known-result
prompts and the wellbeing decision. Opting into wellbeing adds its seven questions.
The setup-stage indicator also shows the later profile review, persona selection and
file generation, so finishing the questionnaire is visibly separate from finishing setup.

Each question sits in a framed panel with its section progress bar, under a line of
setup stages. A table at the start shows each module's size, time and status. Colors
assume a dark terminal; set `PERSONA_FORGE_THEME=light` for a light one (terminals
that set `COLORFGBG` are detected). `NO_COLOR=1` turns colors off.

A few emoji mark modules, personas and moments such as the welcome, the halfway point
and the finish screen. They never appear in questions, answers, the wellbeing module,
the report or agent files. Set `PERSONA_FORGE_EMOJI=0` to turn them off.

New questionnaires ask for language as their first question, unless you chose one
in `make settings`. The rest of setup uses that language. The language is saved with
the profile's answers; resume with `make setup`. Existing sessions keep their
original language - to switch, pick the new language in `make settings`, then retake
the profile's questionnaire there.

Mini-IPIP, IPIP-NEO-120, IPIP Honesty-Humility, revised IPIP-VIA, NCS-6 and CBI have
project-authored Ukrainian questions, instructions and response options. These are
not psychometrically validated Ukrainian adaptations. GSE and O*NET are excluded from
Ukrainian sessions pending translation permission checks. Consent, menus, work scenarios,
review and persona selection are translated too. Reports and agent instructions stay
English, as do exact optional polish previews. Each instrument's actual language is
saved; incompatible partial sessions stop before mixing wording. The
[instrument catalogue](docs/instruments.md#ukrainian-questionnaires-requested-2026-10-23)
keeps the plan to obtain published Ukrainian versions later.

Run `make languages` to list and validate installed packs. Contributors can add
JSON language plugins following [the language guide](docs/languages.md) and
[contribution instructions](CONTRIBUTING.md).

## People and profiles

Each person has separate answers, reports and personas in `out/profiles/<name>/`.
Profile names use lowercase letters, digits and hyphens, such as `alex` or `sam`.
Resuming a profile keeps its language and progress. Friends can use a separate
profile on your laptop.

`make settings` is where you choose who is active and in which language:

```
╭─ Settings ─────────────────────────────────────────────╮
│ • Profile: sam (linked to your agents)                  │
│ • Language for new questionnaires: English              │
╰─────────────────────────────────────────────────────────╯
? What would you like to change?
 » 1) Profile: sam
   2) Language: English
   3) Unlink this profile from your agents
   4) Retake this profile's questionnaire
   5) Done
```

Settings are saved in the private `out/settings.json` (a profile name and a language
code, no answers). Every other command uses the active profile. The first `make setup`
asks whose profile it is and remembers the answer.

| You want to | Run |
| --- | --- |
| Switch person, add a friend or change language | `make settings` |
| Start or resume the active profile's questionnaire | `make setup` |
| Use the active profile's instructions in your agents | `make link` (or `make settings`) |
| Unlink persona-forge from your agents | `make unlink` |
| Take the questionnaire again | `make settings`, then Retake (or `make retake`) |
| Open the active profile's report | `make report` |
| Change the active profile's personas | `make ego` |
| See progress and links | `make status` |
| List profiles and which one is active | `make profiles` |

Named profiles stay unlinked after setup or persona editing. Link explicitly when
ready. Linking switches all project-managed rules and personas to the selected
profile, removing previous profiles' active links while preserving their results.
Unrelated configuration and backups are kept.

Retaking asks for confirmation and archives previous answers, reports and personas
in that profile's private `backups/session-*` directory before starting fresh.
Other people's results are untouched. Start over inside setup has the same backup
behavior for the selected profile.

To keep a session created before profiles were introduced, choose **Copy the original
session into a new profile** in `make settings` (or run `make preserve`, which asks for
a name). This copies the original `out/` session into a new named profile and leaves
the original files intact. It refuses an existing profile. Scripts can still pass
`--out`, `--profile` and `--language` to the CLI directly; they are hidden from help.

Profiles separate data, but anyone using the same OS account can read them. They
are not password-protected user accounts.

## Use the result

| Where | What to type | What happens |
| --- | --- | --- |
| Claude Code | nothing | Your work profile loads in every session |
| Claude Code | `/output-style pf-mentor` | Switches to the mentor persona |
| Codex | `codex -p pf-me` | Codex uses your work profile |
| Codex | `codex -p pf-mentor` | Codex uses your profile plus the persona |
| Browser | `make report` | Opens your private report |

Swap `mentor` for any persona you picked. First link your profile with `make link`.

## Change something

| You want to | Run |
| --- | --- |
| Pick different personas | `make ego` |
| Redo the questionnaire | Press **R** (Start over) in setup |
| Remove the links | `make unlink` |
| Put the links back | `make link` |

To restart in Ukrainian, open `make settings`, set Language to Українська, then choose
Retake. `make clean` archives the active profile without starting setup.
Clean moves the saved answers and generated outputs into a private directory under
the profile's `backups/` and removes this project's configuration links. It preserves earlier
backups and unrelated files. It does not permanently delete your answers.

## Safe by design

- Answers and generated files stay in `out/`. Git ignores it, and files are owner-only.
- Nothing is sent anywhere. The one exception is the optional wording polish, which
  shows the exact text first and never sends scores or wellbeing answers.
- Existing files are backed up as `<name>.bak.<timestamp>`, never deleted.
  `make unlink` removes only this project's links.
- Your global `CLAUDE.md`, `AGENTS.md`, Codex `config.toml` and shell files are never
  edited. Setup prints an optional `alias codex='codex -p pf-me'` for you to add.

This is a reflection tool. It is not a diagnosis, a hiring test or a performance review.
Scores are not population norms, and the IT scenarios are reflective prompts, not
validated tests.

## For developers

- `make test lint audit` runs the checks (about 10 seconds).
- `make setup ANSWERS=tests/fixtures/answers_standard.json` runs setup without questions.
- [White paper](docs/whitepaper.md): goals, method and limits.
- [Implementation plan](docs/implementation-plan.md): status and open items.
- [Instrument catalogue](docs/instruments.md): every questionnaire's source and licence.
- `make public-export DEST=../persona-forge-public` builds the limited public edition
  in a new folder from committed files, leaving out instruments whose reuse permission is unclear
  (`data/permissions.json`). Code is MIT-licensed ([LICENSE](LICENSE)); questionnaire
  content keeps its own terms ([NOTICE](NOTICE)).
