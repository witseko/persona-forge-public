# persona-forge

Read `docs/implementation-plan.md` before implementation or review. Its status section
records unfinished work. Read `docs/whitepaper.md` when changing product scope and
`docs/instruments.md` before adding psychological content.

- Use Python 3.12, uv, argparse, questionary and rich. Keep other runtime needs in
  the standard library. Source lives in `src/persona_forge`, tests in `tests`, and
  versioned instrument, scenario, insight and persona data in `data`.
- Read `~/.agents/guides/security.md` before feature work and finish its checklist.
  Read `~/.agents/guides/python.md` before Python work.
- Copy instrument items, keying and membership from verified primary sources.
  Record source URL, retrieval date, citation and licence in every instrument.
  Stop and report if the source or permission cannot be verified. Never invent
  test items or imply that authored work scenarios are validated instruments.
- Keep personal answers and generated artifacts in ignored `out/`. Wellbeing
  scores and screener names stay out of agent files and optional polish input.
- Preserve existing user configuration. Back up link conflicts; remove only
  links owned by this project. Never write global AGENTS.md, CLAUDE.md,
  AGENTS.override.md, shell configuration or Codex config.toml.
- Run `make test lint audit` at milestone boundaries. Record blocked checks as
  blocked, not passed. Add behavior tests for new features.
- Use plain functions, explicit names, type hints and short docstrings. Use only
  plain hyphens, never long dash characters, in code and prose.
- Commit and push only when explicitly authorized by the user. Keep commit
  subjects short, imperative and free of AI attribution.
