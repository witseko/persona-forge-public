# Contributing

Read [AGENTS.md](AGENTS.md) and the status in
[the implementation plan](docs/implementation-plan.md) before changing code.
Run `make test lint audit` and add behavior tests for new features.

To contribute a language, follow [the language plugin guide](docs/languages.md).
Language packs contain JSON catalogs and permitted instrument overlays, with no
runtime dependency or Python registration required.

Psychological content requires verified primary sources and reuse permission.
Every instrument needs an entry in `data/permissions.json`. It ships in the public
edition only when redistribution and commercial use are both granted, and its
translations only when translation is granted too.
Keep personal answers and generated outputs in ignored `out/`; do not include
them in contributions. Preserve existing user configuration and saved sessions.
