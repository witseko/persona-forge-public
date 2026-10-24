# persona-forge

A private questionnaire about how you work. It teaches Claude Code and Codex how to
work with you, adds switchable agent personas and writes an offline report.

## Start (about 30 minutes)

1. Install [uv](https://docs.astral.sh/uv/) if `uv --version` fails.
2. Run `make setup`.
3. Pick a language and a depth: Quick (about 11 minutes), Standard (about 26) or Deep
   (about 62).
4. Answer one question per screen: arrows or a number, then Enter.
5. Review the statements about you, then pick personas.

Stopping is safe. Press **P** or Ctrl-C; `make setup` continues where you stopped.

Keys under each question: `←` Back, `→` Next, `P` Pause, `R` Start over.

## Use the result

Run `make link` once, then:

| Where | Type | What happens |
| --- | --- | --- |
| Claude Code | nothing | Your work profile loads in every session |
| Claude Code | `/output-style pf-mentor` | Switches to the mentor persona |
| Codex | `codex -p pf-me` | Codex uses your work profile |
| Codex | `codex -p pf-mentor` | Your profile plus the persona |
| Browser | `make report` | Opens your private report |

Swap `mentor` for any persona you picked.

## Common commands

| You want to | Run |
| --- | --- |
| Switch person or language | `make settings` |
| Change personas | `make ego` |
| Take the questionnaire again | `make retake` |
| Remove the links | `make unlink` |
| See progress and links | `make status` |

More commands, keys, profiles and languages: [usage guide](docs/usage.md).

## Privacy

- Answers and outputs stay in `out/`, which Git ignores; files are owner-only.
- Nothing is sent anywhere, except the optional wording polish. It shows the exact text
  first and never sends scores or wellbeing answers.
- Existing files are backed up as `<name>.bak.<timestamp>`, never deleted.
- Your global `CLAUDE.md`, `AGENTS.md`, Codex `config.toml` and shell files are never
  edited.

This is a reflection tool, not a diagnosis, hiring test or performance review. Scores
are not population norms, and the work situations are reflective prompts, not
validated tests.

## For developers

- `make test lint audit` runs the checks (about 10 seconds).
- `make setup ANSWERS=tests/fixtures/answers_standard.json` runs setup without questions.
- `make public-export DEST=../persona-forge-public` builds the limited public edition
  from committed files, leaving out questionnaires with unclear reuse permission
  (`data/permissions.json`).
- Docs: [white paper](docs/whitepaper.md), [implementation plan](docs/implementation-plan.md),
  [instrument catalogue](docs/instruments.md), [contributing](CONTRIBUTING.md).
- Code is MIT-licensed ([LICENSE](LICENSE)). Questionnaire content keeps its own terms
  ([NOTICE](NOTICE)).
