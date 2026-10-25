# Contributing a language

Language plugins are local JSON data under `data/languages/<code>/`. No plugin
Python code, installation hooks or network requests are executed. English (`en`)
is the reference catalog; Ukrainian (`uk`) is a complete interactive setup pack.

Run `make languages` to validate and list installed packs. Select a pack in
`make settings` (Language), or let setup ask at the start of a new questionnaire.
Saved sessions keep their language. Terminal setup clears the visible screen and
scrollback on supported terminals, without deleting saved progress or shell history.

## Pack layout

Create a folder such as `data/languages/fr/` with `manifest.json`, `messages.json`
and an `instruments/` directory. Language codes contain two or three lowercase
letters, optionally followed by a region such as `pt-BR`.

Start with a draft manifest:

```json
{
  "schema_version": 1,
  "code": "fr",
  "name": "Français",
  "status": "draft",
  "instrument_ids": ["mini-ipip"]
}
```

Drafts are not selectable. A complete pack must support at least Mini-IPIP or
IPIP-NEO-120. Only known instrument identifiers are accepted. No Python registry
change is needed when adding a folder.

## Translate the interface

Copy `en/messages.json`. Keep every English key and translate its value. Include
consent, navigation, scenarios, preferences, review statements, personas, keyboard
hints and completion messages. Preserve named placeholders such as `{count}` and
`{path}` exactly. Attributes, conversions and format expressions are forbidden.

Missing messages fail explicitly instead of falling back to English. Control
characters and symlinked plugin resources are rejected. Tool names, paths and
user-entered text remain unchanged. Reports and generated agent instructions stay
English. Optional polish previews and diffs display the exact outgoing or proposed
text, even when that text is English. CLI help and diagnostic errors remain English.

## Translate instruments separately

Read [the instrument catalogue](instruments.md) first. Verify permission from primary
sources before copying or translating psychological material. Include only permitted
instruments in the manifest. Unsupported instruments are omitted from that language's
questionnaire, estimates and progress totals. Packs with different coverage do not
produce directly comparable assessments.

English supports eight instruments. Ukrainian currently supports four IPIP instruments,
NCS-6 and CBI (406 library items). French (Belgium, `fr-BE`) and Dutch (Belgium,
`nl-BE`) support the four IPIP instruments only (393 items), the ones whose translation
permission is granted in `data/permissions.json`; they offer no optional wellbeing check.
GSE and O*NET are excluded until translation permission is verified. Optional wellbeing
is offered only when its overlay exists.

Use the Ukrainian overlays as schema examples. Each `<instrument-id>.json` records
`instrument_id`, `language`, `revision`, `translated`, `source_url`, `citation`,
`licence`, `permission_url`, `instructions`, `items` and `response_sets`.
Revision 1 is currently supported. Preserve every original item identifier, response
set identifier and numeric response value. Translate all items and response labels.
Do not add scoring keys, weights or membership definitions. Scoring always uses the
canonical instrument. All declared overlays are validated before setup starts.

## Review and submit

1. Obtain fluent human review of every screen and instrument overlay. Document the
   source, retrieval date, attribution and reuse permission in each overlay.
2. Set the manifest status to `complete` and run `make languages`.
3. Run `make test lint audit`. Add coverage for the new language's supported flows,
   including pause/resume, optional modules and unsupported instruments.
4. Submit the pack with its permission evidence and review status.

Automated checks establish schema coverage and preserve scoring definitions. They
cannot establish translation quality, psychological equivalence or legal permission.
Project-authored translations must remain labelled as unvalidated adaptations.

The [published Ukrainian translation follow-up plan](instruments.md#published-ukrainian-versions-retained-follow-up-plan)
remains open. A future official version needs verified reuse rights, item mappings
and a new revision with explicit session migration. Never silently replace wording
inside an interrupted instrument. Existing answers and recorded administration
languages are preserved; incompatible partial sessions are stopped before questioning.
