# Using persona-forge

The [README](../README.md) covers the basics. This page has the details.

## During the questionnaire

Interactive setup clears the terminal display and scrollback before its first prompt,
including when resuming. Saved progress and shell history are kept.

One question per screen. Use up/down or a number to pick an answer, then Enter to save.
Session controls are keys, shown in a bar under each menu:

```
 ←  Back    →  Next    P  Pause    R  Start over
```

- **P** (Pause) saves your progress and exits. Run `make setup` and choose
  **Continue** to resume at the next unanswered question. At text or yes/no prompts,
  use Ctrl-C instead. An answer or checkbox block you have not submitted is not saved.
- **R** (Start over) asks first, backs up the session in the profile's `backups/`
  folder, then returns to the start of setup.
- **Left/Right** (Back/Next) move between questions across sections. Each key shows
  only when there is a question in that direction. A saved answer is preselected and
  marked "✓ Saved answer". Moving does not save; press **Enter** to save a change.
  Skipped questions stay unanswered and must be answered before you continue. The
  final **Review answers or continue** screen lets you go back through everything.
  Optional free-text hints have a navigation menu before the text editor.

Each question shows section progress and overall progress. The total covers all
questionnaires, work situations, preferences, optional known-result prompts and the
wellbeing decision; opting into wellbeing adds its seven questions. A line of setup
stages also shows the later review, persona and file-generation steps. A table at the
start lists each module's size, time and status.

## Colours and emoji

- Colours assume a dark terminal. Set `PERSONA_FORGE_THEME=light` for a light one
  (terminals that set `COLORFGBG` are detected). `NO_COLOR=1` turns colours off.
- A few emoji mark modules, personas and moments such as the welcome, halfway point
  and finish. They never appear in questions, answers, the wellbeing module, the
  report or agent files. `PERSONA_FORGE_EMOJI=0` turns them off.

## Languages

New questionnaires ask for a language first, unless you chose one in `make settings`.
The language is saved with the profile's answers. Existing sessions keep their
language; to switch, pick the new language in `make settings`, then choose Retake.

Ukrainian questions, instructions and answer options are project translations, not
psychometrically validated Ukrainian adaptations. Questionnaires without translation
permission are left out of Ukrainian sessions. Consent, menus, work situations, review
and persona selection are translated too; reports and agent instructions stay English,
as do optional polish previews. Each questionnaire's actual language is saved, and an
incompatible partial session stops rather than mixing wording. See the
[instrument catalogue](instruments.md#ukrainian-questionnaires-requested-2026-10-23)
for coverage and plans.

French (Belgium) and Dutch (Belgium) work the same way. They cover the four IPIP
questionnaires only, the ones with granted translation permission, so they have no
optional wellbeing check. Their wording is a project translation, not a validated
adaptation, and still needs review by fluent speakers.

`make languages` lists and validates installed language packs. To add one, follow
[the language guide](languages.md) and [CONTRIBUTING](../CONTRIBUTING.md).

## People and profiles

Each person has separate answers, reports and personas in `out/profiles/<name>/`.
Names use lowercase letters, digits and hyphens, such as `alex` or `sam`.

`make settings` chooses who is active and in which language:

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

- Settings live in the private `out/settings.json` (a profile name and a language
  code, no answers). Every other command uses the active profile. The first
  `make setup` asks whose profile it is and remembers it.
- Named profiles stay unlinked after setup or persona editing; run `make link` when
  ready. Linking switches all project-managed rules and personas to that profile and
  removes other profiles' active links, keeping their results.
- Retake asks first, then archives answers, reports and personas in the profile's
  private `backups/session-*` folder. Other people's results are untouched.
- `make clean` archives the active profile's answers and outputs under `backups/` and
  removes this project's links, without starting setup. Nothing is deleted.
- To keep a session from before profiles existed, choose **Copy the original session
  into a new profile** in `make settings` (or run `make preserve`). It copies `out/`
  into a new named profile, leaves the original intact and refuses an existing name.
- Scripts can pass `--out`, `--profile` and `--language` to the CLI; they are hidden
  from help.

Profiles separate data, but anyone using the same OS account can read them. They are
not password-protected accounts.

## All commands

| You want to | Run |
| --- | --- |
| Start or resume the questionnaire | `make setup` |
| Switch person, add a friend or change language | `make settings` |
| Use the profile in your agents | `make link` |
| Remove this project's links | `make unlink` |
| Take the questionnaire again | `make retake` (or Retake in `make settings`) |
| Archive the profile without starting setup | `make clean` |
| Open the report | `make report` |
| Change personas | `make ego` |
| See progress and links | `make status` |
| List profiles | `make profiles` |
| Copy a pre-profile session into a profile | `make preserve` |
| List language packs | `make languages` |
