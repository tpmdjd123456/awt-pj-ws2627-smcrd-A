# Evaluation scope — decided

Agreed by all three, 15 November 2026. Settled.

## The decision

The evaluation corpus is **deliberately cross-event**, not French-only.

The French student protests of autumn 2026 remain the **motivating case study** —
the deck opens with them and the Angers video is the worked example throughout.
They are not the whole corpus.

## What changed, and why

At Workshop 1 we presented the French protests as our evaluation corpus and
defended the narrow focus. We have changed that on purpose, and will say so at
Workshop 2 rather than let it be noticed.

Evaluating on a single event only tells you whether the thresholds were tuned to
that event's transformation patterns. It cannot tell you whether the system
generalises. That is the overfitting risk we flagged ourselves when defending the
narrow scope, and a mixed corpus is what removes it.

Cross-event also makes the retrieval problem honestly varied:

- **Different languages** in the surrounding claims and the fact-checks
- **Different fact-check outlets**, with different record formats and coverage
- **Very different reverse-search footprints** — a 2020 Iraq story and a 2026
  French one are not comparable retrieval problems, and a system that only works
  on recent, heavily indexed Western media is worth knowing about
- **Different platform mixes** per event

## What we keep from the original argument

The reason for picking a single well-covered event was never the event itself. It
was that **ground truth is the bottleneck**: we need pairs where a fact-checker
has already established which copy came first, and densely covered events supply
those cheaply. That still holds, and is still how cases get found — we just do not
stop at one event.

## Practical rule

No per-event quota. But **at least three events with two or more cases each**,
so per-event comparison is possible at Workshop 3. Ten events with one case apiece
would give no basis for saying the system performs differently across them.

## Consequence for the write-up

Results are reported **per event as well as in aggregate**. An aggregate number
across a mixed corpus hides exactly the thing the mixed corpus was built to
expose.
