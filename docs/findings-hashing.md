# Findings — perceptual hashing on our corpus

Measured 15 November 2026 on the 10 cases in `data/dataset.csv`.
Reproduce with `python tools/evaluate_hashing.py`.

## Headline

**Perceptual hashing recovers 4 of 10 originals, with 0 false positives in 90
non-matching comparisons.**

It is not a partial success that more tuning will fix. The six it misses are
missed by a wide margin, and the reason is structural.

## What separates the hits from the misses

Aspect ratio, almost perfectly.

| case | transformation | aspect ratio | PDQ | pHash | crop-resistant | found |
| --- | --- | --- | --- | --- | --- | --- |
| case_06 | resize | preserved | **14** | **0** | — | strong |
| case_08 | resize | preserved | **10** | **4** | — | strong |
| case_07 | labelled resize, actually cropped | 1.54 → 1.75 | 138 | 20 | 3 seg, d16 | strong |
| case_01 | ai_edit | 1.50 → 0.75 | 112 | **16** | — | candidate |
| case_02 | ai_edit | 0.61 → 1.50 | 126 | 24 | 1 seg, d10 | no |
| case_03 | crop | 1.50 → 0.95 | 130 | 24 | 0 seg | no |
| case_04 | crop | 1.50 → 1.56 | 130 | 34 | — | no |
| case_05 | crop | 0.80 → 1.21 | 122 | 28 | — | no |
| case_09 | crop | 1.57 → 0.69 | 148 | 34 | — | no |
| case_10 | multiple | 1.50 → 1.07 | 130 | 32 | — | no |

Eight of ten reused images have a **different aspect ratio** from their
original. Those are not resizes, they are reframings — and a global perceptual
hash describes the whole frame, so changing which part of the image is the
frame changes the hash completely.

The two aspect-preserving cases score PDQ 10 and 14. Every other case scores
112 or above, where unrelated images sit. There is no threshold between those
two groups to find.

**`case_07` is mislabelled** as `resize` in the dataset; its aspect ratio
changed from 1.54 to 1.75, which makes it a mild crop. Worth fixing, and worth
noting that it is the one crop that crop-resistant hashing catches.

## Thresholds, and why they are what they are

| Hash | Threshold | Unrelated floor | Margin |
| --- | --- | --- | --- |
| PDQ | ≤ 31 | 104 | 73 — safe |
| pHash | ≤ 18 | 22 | 4 — thin |
| crop-resistant | ≥ 2 segments, distance ≤ 16 | — | — |

Two of these were tightened after measurement, not chosen up front:

- **pHash was 20 and produced a false positive at exactly 20.** Querying
  case_04's reused image matched case_07 at pHash 20. Dropped to 18.
- **crop-resistant required 1 matched segment and produced a false positive.**
  case_04's reused image matched case_09 on one segment. One segment is a
  coincidence. Raised to 2, which costs us case_02 and buys a clean record.

Losing case_02 to gain a clean false-positive record is the right trade for
this project. A wrong "original" is the exact failure the design is built to
avoid: the panel would state a false provenance with confidence, which is worse
than saying nothing.

## A methodological trap worth recording

Comparing **originals against other originals** reports **0 false positives**
and is misleading. All ten originals are visually unrelated, so of course they
do not collide.

The real test is querying the **reused** images against the index. Transformation
pushes a hash toward the noise floor, and that is exactly where false positives
appear. That test found 2 false positives the first run, at thresholds the
original-vs-original test had declared safe.

`tools/evaluate_hashing.py` now does both, and reports the query-side test first.

## What this means for the project

**Hashing solves the easy fifth of the problem.** It is fast, needs no API key
and no network, and it is exact when it fires. It is the right first probe.

**It cannot carry the demo.** Six of ten real cases return `no_evidence`, and
real-world reuse in this corpus is dominated by cropping — 8 of 10 cases.

**This is the empirical case for the multi-probe architecture.** Workshop 1
argued "no single method is enough, and each is strong where another is blind."
That was a claim from the literature. It is now a measurement on our own data.

**It raises the stakes on reverse image search.** Search engines handle crops
because they match *local features*, not a global frame descriptor. That makes
the probe we have no API access to the one that covers our largest failure
class — which is worth saying plainly to André Paul rather than discovering in
February.

## Next technical step

For the cropped cases, the mechanisms that can work are the ones that compare
*parts* of images rather than whole frames:

- local feature matching — SIFT, ORB — which is roughly what reverse image
  search does internally
- embedding retrieval — CLIP, DINOv2 — robust to crop and recomposition,
  at the cost of being approximate rather than exact

Either is a larger piece of work than hashing and neither is in the Workshop 2
scope. Noted here so the choice is made deliberately.
