# Instrument catalogue

Sources and permissions were checked on 2026-10-23. "Verified" means the exact items,
response options, keys and scale membership were copied from the primary source and
the reuse terms were read on the source's own site. It does not mean the terms cover
public redistribution, commercial use or translation; those are recorded separately. Each JSON file in
`data/instruments/` repeats the source URL, retrieval date, citation and licence.

Items were extracted by a script that parses the downloaded source pages, so no item
text was retyped. Tests in `tests/test_instrument_data.py` compare the files with
counts and keys transcribed separately from the same sources.

## Included

| File | Instrument | Items | Depth | Primary source | Licence | Verified |
| --- | --- | --- | --- | --- | --- | --- |
| `mini-ipip` | Mini-IPIP (Donnellan et al. 2006) | 20 | Quick | [IPIP Mini-IPIP key](https://ipip.ori.org/MiniIPIPKey.htm) | IPIP public domain | Yes |
| `ipip-neo-120` | IPIP-NEO-120 (Johnson 2014), 30 facets, 5 domains | 120 | Standard, Deep | [IPIP-NEO-120 items](https://ipip.ori.org/30FacetNEO-PI-RItems.htm) | IPIP public domain | Yes |
| `ipip-hexaco-hh` | IPIP Honesty-Humility facets (preliminary HEXACO-PI proxies) | 40 | Deep | [IPIP HEXACO key](https://ipip.ori.org/newHEXACO_PI_key.htm) | IPIP public domain | Yes |
| `ipip-via` | Revised IPIP-VIA scales, 24 strengths | 213 | Deep | [IPIP-VIA key](https://ipip.ori.org/newVIAKey.htm) | IPIP public domain | Yes |
| `gse` | General Self-Efficacy Scale (Schwarzer and Jerusalem 1995) | 10 | Standard, Deep | [GSE English page](https://userpage.fu-berlin.de/~health/engscal.htm) | Use and reproduction granted "for your study" with credit ([FAQ](https://userpage.fu-berlin.de/~health/faq_gse.pdf)) | Yes, owner-approved |
| `ncs-6` | Need for Cognition Scale, 6 items (Lins de Holanda Coelho et al. 2020) | 6 | Standard, Deep | [Article appendix, PMC7545655](https://pmc.ncbi.nlm.nih.gov/articles/PMC7545655/) | CC BY 4.0 article | Yes, owner-approved |
| `onet-ip-sf` | O\*NET Interest Profiler Short Form | 60 | Deep | [Interest Profiler PDF](https://www.onetcenter.org/dl_tools/ipsf/Interest_Profiler.pdf) | CC BY-ND 4.0 ([tools licence](https://www.onetcenter.org/license_tools.html)) | Yes |
| `cbi-work` | Copenhagen Burnout Inventory, work-related scale | 7 | Wellbeing opt-in | [NFA CBI scales PDF](https://www.nfa.dk/media/a4wheblj/cbi-scales.pdf) | Free for noncommercial and commercial use with citation ([NFA page](https://www.nfa.dk/vaerktoejer/spoergeskemaer/spoergeskema-til-maaling-af-udbraendthed-cbi/copenhagen-burnout-inventory-cbi)) | Yes |

## Public edition (2026-10-24)

This repository is private and keeps every instrument above. The public release is a
limited copy built with `make public-export`. `data/permissions.json` records, per
instrument, item provenance, redistribution, commercial use, translation and
validation as separate statuses. Content ships publicly only when redistribution and
commercial use are granted; translations also need translation granted.

| Instrument | Redistribution | Commercial use | Translation | Public edition |
| --- | --- | --- | --- | --- |
| IPIP (Mini-IPIP, IPIP-NEO-120, Honesty-Humility, IPIP-VIA) | Granted | Granted | Granted | English and Ukrainian |
| CBI work scale | Granted | Granted | Unclear | English only |
| GSE | Unclear | Unclear | Unclear | Left out |
| NCS-6 | Unclear | Unclear | Unclear | Left out |
| O\*NET Interest Profiler Short Form | Unclear (integration audit pending) | Granted | Unclear | Left out |

In the public edition, Standard depth asks IPIP-NEO-120 only, Deep asks IPIP-NEO-120,
Honesty-Humility and IPIP-VIA, and the Ukrainian questionnaire has no wellbeing module.
See [NOTICE](../NOTICE) for third-party terms.

Project-authored content, not validated instruments:

| File | Content | Size | Status |
| --- | --- | --- | --- |
| `data/sjt/*.json` | IT work situations, 12 shared plus 12 per role track | 8 / 16 / 24 per run | Authored reflective prompts |
| `data/preferences.json` | Collaboration preferences for the agent | about 10 | Authored explicit preferences |

## Scoring notes

- IPIP scales use the IPIP five-point accuracy format from the
  [administration page](https://ipip.ori.org/New_IPIP-50-item-scale.htm) and its
  verbatim instructions. Scale scores are item means. Items are interleaved across
  scales, following that page's advice.
- IPIP items are shown in the first person ("I am the life of the party." for the
  source's "Am the life of the party."), an owner-approved readability change on
  2026-10-23. The [administration page](https://ipip.ori.org/New_IPIP-50-item-scale.htm)
  states that users "can edit the wording of items". Nothing else in the wording changes,
  and the data files keep the exact source text. Results may be slightly less comparable
  with studies that used the original wording. Other instruments are never reworded.
- Domain scores (IPIP-NEO-120, Honesty-Humility) pool all items of their facets.
- GSE is a sum of ten 1-to-4 answers (10 to 40), with no recoding.
- NCS-6 uses 1-to-5 answers with labelled endpoints only. Items marked (R) are reversed.
  The score is the item mean.
- O\*NET scores count the checked activities in each RIASEC area (0 to 10). Activities and
  scoring are unchanged, as CC BY-ND requires, and the report shows the O\*NET credit line.
- CBI answers score 100, 75, 50, 25 or 0; the last question is reversed; the score is the mean.
- Bands (low, mid, high) describe where the mean answer sits within the response range:
  below 40 percent is low, above 60 percent is high. On a 1 to 5 scale this is exactly
  "below 2.6" and "above 3.4". Bands are never population norms.

## Dropped or blocked

The project owner decided on 2026-10-23 to drop instruments whose permission could
not be verified. They can return once permission is documented.

| Instrument | Reason |
| --- | --- |
| Grit-S (Duckworth and Quinn 2009) | The [measures page](https://www.angeladuckworth.com/measures) offers the scales to "researchers and educators" for noncommercial use and says they "cannot be published or used for commercial purposes or wide public distribution". Use in a personal tool is not addressed. Dropped. |
| Need for Closure, 15 items (Roets and Van Hiel 2011) | No permission statement found for the Elsevier article. Dropped. |
| Reduced Morningness-Eveningness Questionnaire (Adan and Almirall 1991) | No permission statement found. Dropped. |
| ASRS v1.1 Part A | Secondary sources report free use of the 6-question screener with its copyright notice and unaltered scoring. The [primary page](https://www.hcp.med.harvard.edu/ncs/asrs.php) could not be retrieved on 2026-10-23, including through Chrome and DevTools. Reuse permission remains unverified. Blocked; see access findings below. |

### ASRS access findings (2026-10-23)

- The initial automated request returned HTTP 503; a later web retrieval timed out.
- Chrome access to `https://www.hcp.med.harvard.edu/ncs/asrs.php` returned
  `ERR_TIMED_OUT`.
- Chrome access without `www`, at `https://hcp.med.harvard.edu/ncs/asrs.php`,
  displayed an Imperva error page: "Resolving failed", Error 22. The page stated
  that its proxy failed to resolve the site's hostname. DevTools was also inspected.
- These browser results suggest a site infrastructure problem; they do not establish
  that access is blocked only for automated clients.
- The NovoPsych ASRS page and its questionnaire PDF were accessible in Chrome, but
  this secondary source does not verify the primary source's reuse permission.

Next steps: retry the official page later, or obtain written permission from the
rights holder covering reproduction in a distributed command-line application.
Before inclusion, verify and record the official ASRS v1.1 Part A item wording,
response options, scoring instructions, copyright notice and applicable reuse terms.

## Ukrainian questionnaires (requested 2026-10-23)

Original scope: psychological instrument instructions, item text and response options.
On 2026-10-24 the owner expanded the scope to the complete interactive setup and
contributor-friendly JSON language packs; reports and agent instructions stay English.
The owner approved project-authored Ukrainian translations on 2026-10-23, while
retaining the plan to obtain published Ukrainian versions below. Ukrainian is
implemented for Mini-IPIP (20 items), IPIP-NEO-120 (120), IPIP Honesty-Humility (40),
revised IPIP-VIA (213), NCS-6 (6) and CBI work scale (7): 406 items in total. GSE and
O*NET are excluded from new Ukrainian questionnaires until permission is verified.

### Current project translations

`data/languages/uk/instruments/` holds revision 1, translated from the existing English source
files, not copied from the Ukrainian candidates below. Each overlay records its
source URL, citation, date, permission URL and licence. IPIP explicitly permits
translation. The [NCS-6 publisher page](https://journals.sagepub.com/doi/10.1177/1073191118793208)
confirms CC BY 4.0; the existing caveat about the original scale's rights remains.
GSE's study-use permission does not explicitly address translation. O*NET's modification
licence has additional validation requirements. Those two instruments are not offered
by the Ukrainian language pack.
The project-authored CBI translation is included at the owner's request under
[NFA's free-use grant with citation](https://nfa.dk/vaerktoejer/spoergeskemaer/spoergeskema-til-maaling-af-udbraendthed-cbi/copenhagen-burnout-inventory-cbi),
checked again on 2026-10-23. This is the project's interpretation of that grant;
NFA's text does not separately discuss translation or endorse this adaptation.

These are project translations, not psychometrically validated Ukrainian adaptations.
The questionnaire displays that limitation before each translated instrument, and the
private report records the selected language and any historical English administration. Numeric
responses, reverse keys, item identifiers and scale membership are unchanged; this
does not establish psychological equivalence across languages. No English item data
was overwritten. Language selection is saved with answers and cannot be changed for
an existing saved session.

The actual administered language is now also saved per instrument. Older sessions
with existing CBI responses are recorded as English. Interactive Ukrainian setup now
stops before continuing an incompatible partially answered instrument. Existing
personal answers are not rewritten. New or unanswered modules use Ukrainian.
Titles, hints, questions and both CBI response sets are translated. See the
[language plugin guide](languages.md) for coverage and contribution requirements.

### Published Ukrainian versions: retained follow-up plan

Initial source checks on 2026-10-23 found the following leads and blockers. "Not
verified" records the outcome of this search, not proof that a translation does not
exist. Translation permission and evidence of psychometric validation must be
recorded separately.

| Instrument | Ukrainian source status | What is needed before inclusion |
| --- | --- | --- |
| Mini-IPIP | [Kuśnierz et al. (2020)](https://res.mdpi.com/d_attachment/ijerph/ijerph-17-05729/article_deploy/ijerph-17-05729-v3.pdf) report translating Mini-IPIP into Ukrainian for their study. Exact Ukrainian item text and response anchors were not verified. | Obtain the study's actual Ukrainian questionnaire and verify reuse terms and item mapping. |
| IPIP-NEO-120, IPIP Honesty-Humility, revised IPIP-VIA | Exact Ukrainian versions were not verified. The [official translation directory](https://ipip.ori.org/newItemTranslations.htm) has no Ukrainian entry in the page checked. | Obtain primary translation sources with item mappings, instructions, response anchors and reuse terms. Do not substitute proprietary HEXACO or VIA questionnaires for the shipped IPIP scales. |
| GSE | [Inna Haletska's author-posted Ukrainian adaptation](https://www.researchgate.net/publication/385381234_Skala_zagalnoi_samoefektivnosti_R_Svarcera_i_M_Erusalema_General_Self-Efficacy_Scale_GSE_Schwarzer_R_Jerusalem_M_adaptacia_ukrainskou_movou_IGalecka), DOI 10.13140/RG.2.2.33906.52161, is a candidate source. No explicit translation reuse licence was verified on that page. | Verify permission for redistributing this translation, then check its full wording, anchors and scoring against the shipped instrument. |
| NCS-6 | Exact Ukrainian six-item version was not verified. | Obtain a primary source for this specific short form, its response anchors and reuse terms. |
| O*NET Interest Profiler Short Form | No Ukrainian version was verified. The [official licence page](https://www.onetcenter.org/license_tools.html) distinguishes verbatim redistribution under CC BY-ND from modifications under its Developer License, which requires validation. | Verify an applicable Ukrainian source and licence. Do not distribute a new translation under the existing CC BY-ND grant. |
| CBI work scale | [Oleksandra Yakymets's author-posted Ukrainian translation](https://www.researchgate.net/publication/378141246_INVENTORY_OF_COPENHAGEN_BURNERS_CBI_in_Ukrainian), DOI 10.13140/RG.2.2.13229.26083, is a candidate source. Its description references an Italian translation; no explicit translation reuse licence was verified on the page. | Verify the translation's reuse permission, correspondence to the original seven-item work scale, response anchors and scoring. |

[IPIP permits translation](https://ipip.ori.org/), but that permission does not make
a new project-authored translation a published Ukrainian adaptation. The owner-approved
exception permits project translations of the verified English items where translation
rights allow it. Published Ukrainian candidates still need their own permission checks.
ASRS remains excluded for the separate permission blocker above.

Follow-up steps:

1. Obtain the exact published Ukrainian versions and permission for redistribution.
2. Compare every item, response anchor, key and scale with the shipped instrument;
   record validation evidence separately from licensing.
3. Introduce a new translation revision rather than silently replacing revision 1 in
   an interrupted session. Preserve the original administration language and revision
   when migrating answers or adding a retest.
4. Keep scoring-equivalence, coverage, language-selection and resume behavior tests.

## Changes from the original plan

- Honesty-Humility: IPIP publishes 40 items in four facets, not a 10-item scale. The full
  set is offered at Deep depth.
- Character strengths: no sourced 4-item IPIP-VIA short form exists, and choosing items
  would invent scale membership. The full 213-item revised set is offered at Deep depth.
- Deep depth is therefore much longer than 45 minutes. See the white paper for the
  revised time budget.
