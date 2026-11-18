# Findings — perceptual hashing on our corpus

Two measurements, and they disagree. Read both.

| | real reuse | synthetic transformations |
| --- | --- | --- |
| what | the 10 reused copies found in the wild | 150 generated variants of the same 10 originals |
| recall | **4/10 (40%)** | **133/150 (89%)** |
| false positives | 0 in 90 | 0 in 1,350 |
| reproduce | `python tools/evaluate_hashing.py` | `python tools/evaluate_transformations.py` |

The gap between 40% and 89% is the most useful thing in this document, and
[the section on it](#why-40-and-89-disagree) is the one to read before quoting
either number.

Measured 15 and 18 November 2026.

---

# Part 1 — real reuse (10 cases)

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
| PDQ | ≤ 31, under all 8 orientations | 104 | 73 — safe |
| pHash | ≤ 18, suppressed when a strong match exists | 22 | 4 — thin |
| crop-resistant | ≥ 2 segments, distance ≤ 16 | — | — |

Every one of these was changed after measurement, not chosen up front:

- **pHash was 20 and produced a false positive at exactly 20.** Querying
  case_04's reused image matched case_07 at pHash 20. Dropped to 18 — which
  then false-positived at exactly 18 on the synthetic set. Rather than chase it
  down to 16 and lose four mild-crop recoveries, we added the suppression rule
  below, which removed the false positive without costing recall.
- **crop-resistant required 1 matched segment and produced a false positive.**
  case_04's reused image matched case_09 on one segment. One segment is a
  coincidence. Raised to 2, which costs us case_02 and buys a clean record.
- **PDQ was compared in one orientation only**, which made it blind to
  mirroring. Now compared under all 8 dihedral orientations. See
  [Part 2](#mirroring-was-a-blind-spot).

### The suppression rule

**A candidate-tier match is reported only when nothing matched strongly.**

A candidate is a weak lead. When a strong match is already in hand, the weak
leads are noise — and one of them was the only false positive across 150
variants. When nothing strong exists, a candidate is all we have, so it stands.
This does not hide genuine duplicates: a second appearance of the same image
scores strong, not candidate.

Adding this rule let pHash stay at 18, which is worth 4 extra recoveries on
20% crops.

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

A second version of the same trap: the originals-vs-originals baseline was
still comparing PDQ in **one** orientation after the probe had moved to
comparing **eight**. A minimum over 8 hashes is 8 chances to collide, so the
test was measuring something the code no longer did. Fixed; the floor turns out
to be unchanged at 104, so orientation-invariance costs nothing in safety here.
The general lesson is that the evaluation has to change whenever the scoring
does.

---

# Part 2 — synthetic transformations (150 variants)

Generated by `tools/generate_transformations.py` (#10): 15 variants of each of
the 10 originals, each isolating one transformation.

## Results

| variant | found | strong | candidate | median PDQ |
| --- | --- | --- | --- | --- |
| unchanged (q95 re-save) | 10/10 | 10 | 0 | 0 |
| re-encode q90 / q70 / q50 | 30/30 | 30 | 0 | 0–2 |
| resize 50% / 25% | 20/20 | 20 | 0 | 6–12 |
| screenshot (90% + q75) | 10/10 | 10 | 0 | 6 |
| logo watermark | 10/10 | 10 | 0 | 20 |
| text overlay — caption bar | 10/10 | 9 | 1 | 34 |
| text overlay — meme | 10/10 | 5 | 5 | 50 |
| **mirror (horizontal flip)** | **10/10** | 10 | 0 | 8 |
| crop 10% | 10/10 | 4 | 6 | 86 |
| crop 20% | 8/10 | 2 | 6 | 114 |
| crop 30% | 3/10 | 2 | 1 | 116 |
| crop 40% | 2/10 | 2 | 0 | 120 |
| **total** | **133/150 (89%)** | | | |

**0 false positives in 1,350 non-matching comparisons.**

Compression, resizing, screenshots, watermarks and text overlays are
effectively solved. The large-text-on-image case André Paul asked about
survives at 10/10, which is worth saying to him directly.

**The break-point is the crop curve.** Full recall at 10%, 8/10 at 20%, then
collapse: 3/10 at 30% and 2/10 at 40%. Past roughly a 20% crop, a global
perceptual hash stops working, and the two that still match at 30–40% do so
through crop-resistant segment hashing, not PDQ.

## Mirroring was a blind spot

Plain PDQ scored **124 to 132** on the mirrored variants — indistinguishable
from unrelated images — and recovered **1 of 10**. The probe was calling
`pdqhash.compute`, which has no orientation invariance.

`pdqhash.compute_dihedral` returns the hash under all 8 orientations of the
square symmetry group, at essentially the same cost (3.5 ms against 3.2 ms,
because the transform is applied to the DCT coefficients rather than by
re-hashing rotated images). Comparing against all 8 recovers **10 of 10**, at
distances of 0 to 24.

The matched orientation is now reported, because *"this is the original,
mirrored"* is different evidence from *"this is the original"* — a mirrored
copy is not pixel-identical, and saying so explains the difference to a reader
instead of leaving it looking like an error.

Slot order was verified against explicitly transformed images rather than
assumed, and the labels describe how the **query** differs from the indexed
original, which is the inverse of the transform each slot represents.

An orientation is reported **only when PDQ is the measure that matched**. On a
crop-resistant or pHash match the PDQ distance is 114 or more, and the argmin
over its 8 orientations is noise; reporting "rotated 270" there would be
inventing evidence.

Without the mirror variant in this set, this would have reached Workshop 3
undetected.

## Reporting the deciding measure

A crop-resistant match can sit at PDQ 118 while its segment distance is 6.
Showing 118 beside "strong match" reads like a bug, because the numbers are on
different scales and only one of them decided anything.

Each appearance now carries `method` — `pdq`, `crop_segments` or `phash` — and
the `distance` belonging to that measure. The contract change is additive and
documented in [`api.md`](api.md).

---

# Why 40% and 89% disagree

Both numbers are correct. They measure different things, and the difference is
itself a finding.

**Every synthetic variant preserves aspect ratio.** The crops are centred,
removing the same fraction from each dimension, so the subject stays centred
and the frame keeps its proportions.

**Eight of the ten real reused copies changed aspect ratio.** They were
reframed by hand — off-centre, different proportions, sometimes recomposed.

The consequence, on the same ten images:

| | synthetic 20% crop | real crops |
| --- | --- | --- |
| recall | 8/10 | 1/5 |

Real-world cropping behaves like the synthetic 30–40% band, not the 10–20% one.
So:

- **Use the synthetic curve to locate break-points.** That is what it is for,
  and it does it well — it is how we know the limit is near 20%.
- **Do not quote 89% as expected real-world recall.** On real reuse this corpus
  gives 40%.
- **Report both, with this explanation.** A single number here would be either
  pessimistic or misleading depending on which one was picked.

The fix on the generator side is an **off-centre crop** variant — take the left
or top two-thirds, so the aspect ratio changes and the subject moves out of
centre. Requested on #8.

---

# What this means for the project

**Hashing solves the easy half of the problem, and solves it completely.**
Compression, resizing, screenshots, watermarks, text overlays and mirroring are
all at 10/10. It is fast, needs no API key and no network, and it is exact when
it fires. It is the right first probe.

**It cannot carry the demo on its own.** Six of ten real cases return
`no_evidence`, and real-world reuse in this corpus is dominated by heavy,
off-centre cropping.

**This is the empirical case for the multi-probe architecture.** Workshop 1
argued "no single method is enough, and each is strong where another is blind."
That was a claim from the literature. It is now a measurement on our own data,
and the blind spot has a measured shape: crops past 20%.

**It raises the stakes on reverse image search.** Search engines handle crops
because they match *local features*, not a global frame descriptor. That makes
the probe we have no API access to the one that covers our largest failure
class — which is worth saying plainly to André Paul rather than discovering in
February.

## Next technical step

For the cropped cases, the mechanisms that can work are the ones that compare
*parts* of images rather than whole frames.

**Local feature matching, measured.** ORB keypoints with a ratio test and RANSAC
geometric verification, run on the same 10 real pairs as an experiment (not
committed):

| | hashing | ORB + RANSAC |
| --- | --- | --- |
| real pairs recovered | 4/10 | **9/10** |
| real crops recovered | 1/5 | **5/5** |
| AI edits recovered | 1/2 | **2/2** |
| false positives in 90 | 0 | 0 |
| cost per query, 10 entries | ~30 ms | ~1,000 ms |

Correct pairs scored 40 to 1,739 inliers; unrelated pairs topped out at 29.
The only failure is case_10, the one with stacked transformations. Coincidental
descriptor matches do not agree on a shared homography, which is what makes the
precision hold.

The cost is linear in index size — about 2.5 s at 25 cases, 10 s at 100 — so it
works at our corpus size and does not scale to a real index. That is itself
worth stating in the report: it explains why reverse image search is a hosted
service rather than something anyone rebuilds.

**Embedding retrieval — CLIP, DINOv2 — is the option to avoid here.** It is
robust to crop and recomposition, but it matches on *semantic* similarity: two
different photographs of the same protest score as highly similar. That would
return a confident wrong original, which is precisely the failure mode of
"Similarity over Factuality" (WACV 2025) and precisely what
[`terminology.md`](terminology.md) exists to prevent.

Neither is in the Workshop 2 scope, and the plan puts reverse image search in
week 4 as a manual subset of ~15 cases. Recorded here so the choice is made
deliberately rather than by default.
