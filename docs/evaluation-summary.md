# Does it work? What we tested

**Short answer:** a persona-forge profile kept answers correct and made assistants a bit
better at working the way you asked than no instructions at all. A short note written by
hand did better than the full profile. So the most useful part is writing down how you
like to work.

![The short answer: correct answers same, a bit better than nothing, worse than a short note](images/short-answer.svg)

This was a small test with made-up people, not real users. It shows how AI assistants
follow written instructions. It does not show that any personality trait is measured.

## What we tested

![What we tested: 3 made-up people, 4 kinds of notes, 2 AI assistants, an AI judge](images/what-we-tested.svg)

1. We wrote 3 made-up people: a tired senior developer who wants short answers, a keen
   junior developer, and a demanding manager who wants tables and clear confidence.
2. Each person gave the assistant one of 4 kinds of notes: no instructions, a short
   5-line note, their settings only, or a full persona-forge profile.
3. Claude Code and Codex each answered the same 4 work tasks, twice: 192 replies.
4. Another AI read every reply and scored it. It was not told which note was used.

## Which kind of note fit best?

![All four did well. The short note fit best.](images/fit-score.svg)

| Kind of note | Fit score out of 8 (both assistants) |
| --- | --- |
| No instructions | 7.3 |
| A short note (5 lines) | 7.9 |
| Settings only | 7.5 |
| persona-forge profile | 7.5 |

Answers stayed correct with every kind of note (1.00 and 0.99 of the required points).

## Which reply did the judge prefer?

![The judge preferred the profile to nothing, not to a note](images/judge-preference.svg)

| Profile compared with | Profile better | Same | Other better | Unsure |
| --- | --- | --- | --- | --- |
| No instructions | 22 | 4 | 7 | 15 |
| A short note | 0 | 4 | 36 | 8 |
| Settings only | 10 | 11 | 6 | 21 |

"Unsure" means the judge picked a different reply when we swapped the order, so we do
not count those.

## Did it respect "keep it short"?

![Asked for short answers, the profile kept replies long](images/reply-length.svg)

| Kind of note | Claude Code, words per reply | Codex, words per reply |
| --- | --- | --- |
| No instructions | 902 | 536 |
| A short note (5 lines) | 483 | 397 |
| Settings only | 667 | 446 |
| persona-forge profile | 902 | 426 |

With Claude Code the profile added extra advice that made replies long again: tips
suggested by the questionnaire outweighed the person's own "keep it short" setting. This
is a known issue.

## Did people get the formats they asked for?

![The manager got the formats they asked for](images/requested-formats.svg)

| What the manager asked for | Without a note | With a note or profile |
| --- | --- | --- |
| A comparison table (Claude Code) | 2 of 8 | 8 of 8 |
| Saying how sure it is (both assistants) | 1 of 8 | 7-8 of 8 |

## What this means for you

1. Your written preferences matter most. Spend your time on them.
2. The questionnaire is a guided way to find and word those preferences. It is not a test
   that measures you.
3. Review the statements it suggests and drop any that do not fit. Fewer, clearer lines
   work better than many.

The graphics are drawn from `data/evaluation-summary.json` by `make graphics`.
