# Terminology — decided

Agreed by all three, 8 November 2026. Settled, not up for revisiting.

Raised by André Paul in Workshop 1: we were using "earliest appearance" and
"original context" as if they were the same thing, while also admitting the
earliest copy we find may not be the original. This closes that.

## Two outputs, never derived from each other

**Earliest known appearance** — a retrieval result. A date and a source we
found. It says nothing about whether the claim attached to it is true. Always
reported.

**Attested context** — what the media actually shows. Only ever comes from one
of three places:

1. a fact-check record,
2. a valid C2PA manifest,
3. the earliest *credible publisher's* own caption.

Reported only when one of those exists. Otherwise `null`, shown to the user as
**unknown** — never guessed, never inferred from the earliest hit.

## The rule

> Never derive attested context from earliest appearance.

Why it matters: if someone reposted the Angers video in July 2023 captioned
"riots in Marseille", and our search finds that post but misses the March 2023
original, then equating earliest with original makes us report "Marseille" as
the true context. We would have confidently repeated a different lie.

## Dates

| Field | Meaning |
| --- | --- |
| `post_date` | **Canonical.** Publication date of the post we are looking at. |
| `earliest_date` | Publication date of the earliest copy we found. |
| `factcheck_date` | When the fact-check was published. |
| `embedded_date` | Any date visible inside the image itself. Recorded, never trusted. |

## What this changes

**Dataset** — separate columns for the earliest appearance and for the attested
context. Not one "original context" column.

**API** — `/verify` returns `earliest_known_appearance` and `attested_context`
as two independent nullable objects. Either can be present without the other.

**UI** — the panel can show an earliest appearance with no attested context.
That is a normal result, not a failure.
