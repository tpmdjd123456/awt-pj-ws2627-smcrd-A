# Findings — perceptual hashing on our corpus

Two measurements, and they disagree. Read both.

| | real reuse | synthetic transformations |
| --- | --- | --- |
| what | the 25 reused copies found in the wild | 500 generated variants of the same 25 originals |
| recall | **13/25 (52%)** | **373/500 (75%)** |
| recall@3 and @5 | 13/25 — unchanged | — |
| earliest-date accuracy | **13/13 of answered queries** | — |
| false positives, `strong` tier | **0 in 600** | **0 in 12,000** |
| false positives, `candidate` tier | 0 | 1 |
| reproduce | `python tools/evaluate_hashing.py` | `python tools/evaluate_transformations.py` |

Two results that are not in that table and matter as much:

- **No image in the corpus carries a C2PA manifest** — 0 of 50, originals and
  reused copies alike. [Ablation](#ablation--what-each-probe-and-measure-contributes).
- **Recall does not improve with k.** When hashing finds the original it ranks
  first; when it misses, the original is not in the list at all.

The gap between 52% and 75% is the most useful thing in this document, and
[the section on it](#why-the-two-numbers-disagree) is the one to read before
quoting either.

Measured 15, 18 and 25 November 2026 — the last on the 25-case dataset. The
10-case figures that earlier drafts quoted (40% and 89%) are superseded; see
[Thresholds](#thresholds-and-why-they-are-what-they-are) for why they changed
by more than the extra cases alone explain.

---

# Part 1 — real reuse (25 cases)

## Headline

**Perceptual hashing recovers 13 of 25 originals, with 0 false positives in 600
non-matching comparisons.**

It is not a partial success that more tuning will fix. The twelve it misses are
missed by a wide margin, and the reason is structural.

## What separates the hits from the misses

The transformation, almost entirely:

| transformation | recovered |
| --- | --- |
| resize | **8/8** |
| AI edit | 1/2 |
| crop | **4/14** |
| multiple | 0/1 |

Every resize is found. Two thirds of crops are missed. That is the whole
result, and it holds on 25 cases exactly as it did on 10.

The mechanism is aspect ratio. A global perceptual hash describes the whole
frame, so a resize — which keeps the frame and changes only its scale — barely
moves the hash, while a crop changes *what the frame contains* and moves it
completely. In the first ten cases, 8 of 10 reused copies had a different
aspect ratio from their original; those are reframings, not resizes.

The found cases score PDQ 6 to 34. The missed ones score 102 to 124, which is
where unrelated images sit. There is no threshold between those two groups to
find.

Four of the thirteen are recovered at `candidate` strength rather than
`strong`, through pHash or a single-segment match — real but weaker evidence,
and the tier says so.

## recall@k: the system is binary

| k | recall |
| --- | --- |
| 1 | 13/25 (52%) |
| 3 | 13/25 (52%) |
| 5 | 13/25 (52%) |

**Recall does not improve with k at all.** When the correct original is found it
ranks first; when it is missed it is not in the list anywhere. There is no
middle ground where the right answer sits at rank 3 waiting to be noticed.

That is worth knowing for two reasons. It means the headline recall figure is
not hiding near-misses that a longer candidate list would rescue — 52% is the
real number, not an artefact of only counting rank 1. And it tells the panel
what to show: a long candidate list adds nothing here, because the candidates
below the top result are never the answer.

## Earliest-date accuracy

Recall asks *"did we find the right case?"* This asks *"was the date we
reported actually the earliest?"* — which is the claim the panel puts in front
of a user, and a different question.

| tier | answered | date exact | accuracy |
| --- | --- | --- | --- |
| `strong` | 9 | 9 | 100% |
| `candidate` | 4 | 4 | 100% |
| all | 13 | 13 | **100%** |

12 of 25 queries returned `no_evidence` and are not counted here — there is no
date to be right or wrong about.

**Read this as a corollary, not as independent evidence.** With zero false
positives, every answered query matched the correct case, and the correct case
carries the correct date by construction. The metric is near-tautological on a
clean run. It is still worth having: it is the check that would catch a date
being mangled somewhere in the pipeline, and on any run with a false positive
it drops immediately — a wrong case means a wrong date, which is exactly the
user-facing harm.

## Thresholds, and why they are what they are

| Hash | Threshold | Unrelated floor | Margin |
| --- | --- | --- | --- |
| PDQ | ≤ 31, under all 8 orientations | 94 | 63 — safe |
| pHash | ≤ 18, suppressed when a strong match exists | 16 on transformed queries | 0 — see below |
| crop-resistant | 3+ segments within 16, **or** 2 segments within 8 | — | — |

Every one of these was changed after measurement, not chosen up front, and
**two of them had to be changed again when the dataset grew from 10 cases to
25.** That is the single most transferable lesson here: a bigger index means
more chances to collide, so a threshold is only valid for the corpus it was
derived on.

- **pHash was 20 and produced a false positive at exactly 20.** Dropped to 18 —
  which then false-positived at exactly 18 on the synthetic set. Rather than
  chase it down and lose mild-crop recoveries, we added the suppression rule
  below.
- **crop-resistant required 1 matched segment and produced a false positive.**
  Raised to 2 within distance 16, which was clean at 10 cases — and produced
  **8 false positives at 25 cases, 7 of them at `strong`.** See below.
- **PDQ was compared in one orientation only**, which made it blind to
  mirroring. Now compared under all 8 dihedral orientations. See
  [Part 2](#mirroring-was-a-blind-spot).

### The crop-resistant rule: count traded against distance

The 8 false positives at 25 cases all shared a signature: **exactly 2 matched
segments at a distance of exactly 16**, the threshold. The genuine matches sat
elsewhere:

| | segments | distance |
| --- | --- | --- |
| case_07 (genuine) | 3 | 16 |
| case_23 (genuine) | 2 | 4 |
| all 8 false positives | 2 | 16 |

No single pair of numbers separates those. A tier does:

```
3+ segments  →  distance up to 16
2  segments  →  distance up to 8
```

One loosely matching segment pair is a coincidence; three agreeing segments, or
two very close ones, are not. This keeps both genuine matches and removes all
eight false positives — **7 of which were at `strong` tier**, the worst kind,
because the panel would have stated a false provenance confidently.

### The suppression rule

**A candidate-tier match is reported only when nothing matched strongly.**

A candidate is a weak lead. When a strong match is already in hand, the weak
leads are noise. When nothing strong exists, a candidate is all we have, so it
stands. This does not hide genuine duplicates: a second appearance of the same
image scores strong, not candidate.

### The one remaining false positive, and why it stays

One candidate-tier false positive survives in the synthetic set: a 20% crop of
case_16 matches case_23 at pHash exactly 16. Sweeping pHash over all 500
variants:

| threshold | correct pairs within | wrong pairs within |
| --- | --- | --- |
| 14 | 299 | **0** |
| 16 | 307 | 1 |
| 18 | 316 | 5 |

Tightening to 14 would buy a perfect record for up to 17 recoveries. We are
keeping 18, deliberately:

**Zero false positives at `strong` is the hard requirement, and it is met.** The
`candidate` tier exists precisely to carry evidence that might not hold —
demanding perfection from it defeats the point of having tiers at all. One
weak-tier miss in 500, labelled weak, is the system behaving as designed.

A wrong `strong` match is the failure the design is built to prevent: the panel
would state a false provenance with confidence, which is worse than saying
nothing. A wrong `candidate` says "possible, unconfirmed", which is true.

## A methodological trap worth recording

Comparing **originals against other originals** reports **0 false positives**
and is misleading. All the originals are visually unrelated, so of course they
do not collide.

The real test is querying the **reused** images against the index. Transformation
pushes a hash toward the noise floor, and that is exactly where false positives
appear. That test found 2 false positives the first run, at thresholds the
original-vs-original test had declared safe.

`tools/evaluate_hashing.py` now does both, and reports the query-side test first.

A second version of the same trap: the originals-vs-originals baseline was
still comparing PDQ in **one** orientation after the probe had moved to
comparing **eight**. A minimum over 8 hashes is 8 chances to collide, so the
test was measuring something the code no longer did. Fixed; the floor turned
out to be unchanged, so orientation-invariance costs nothing in safety here.
The general lesson is that the evaluation has to change whenever the scoring
does.

---

# Part 2 — synthetic transformations (500 variants)

Generated by `tools/generate_transformations.py` (#10, #11): 20 variants of
each of the 25 originals, each isolating one transformation.

## Results

| variant | found | strong | candidate | median PDQ |
| --- | --- | --- | --- | --- |
| unchanged (q95 re-save) | 25/25 | 25 | 0 | 0 |
| re-encode q90 / q70 / q50 | 75/75 | 75 | 0 | 0 |
| resize 50% / 25% | 50/50 | 50 | 0 | 6–12 |
| screenshot (90% + q75) | 25/25 | 25 | 0 | 6 |
| logo watermark | 25/25 | 25 | 0 | 20 |
| text overlay — caption bar | 25/25 | 23 | 2 | 36 |
| text overlay — meme | 25/25 | 8 | 17 | 52 |
| **mirror (horizontal flip)** | **25/25** | 25 | 0 | 6 |
| crop 5% | 25/25 | 8 | 17 | 46 |
| crop 10% | 25/25 | 5 | 20 | 80 |
| crop 20% | 14/25 | 2 | 12 | 114 |
| crop 30% | 5/25 | 3 | 2 | 116 |
| crop 40% | 2/25 | 2 | 0 | 118 |
| off-centre crop, top 67% | 10/25 | 10 | 0 | 118 |
| off-centre crop, right 67% | 7/25 | 7 | 0 | 114 |
| off-centre crop, left 67% | 6/25 | 5 | 1 | 116 |
| off-centre crop, bottom 67% | 4/25 | 4 | 0 | 116 |
| **total** | **373/500 (75%)** | | | |

**0 false positives at `strong` tier in 12,000 non-matching comparisons**, and
one at `candidate` (see above).

Compression, resizing, screenshots, watermarks, text overlays and mirroring are
effectively solved. The large-text-on-image case André Paul asked about
survives at 25/25, which is worth saying to him directly.

**The break-point is the crop curve.** Full recall at 5% and 10%, 14/25 at 20%,
then collapse: 5/25 at 30% and 2/25 at 40%. Past roughly a 20% crop, a global
perceptual hash stops working, and the few that still match at 30–40% do so
through crop-resistant segment hashing, not PDQ.

**The off-centre crops are the honest ones.** Keeping 67% of the image from one
side changes the aspect ratio — 0.67× for left/right, 1.49× for top/bottom —
which is what real reframing does. They score 4–10 of 25, far below the
centred crops at the same severity, and in line with the 4/14 that hashing
recovers from real crops. Adding them dropped total synthetic recall from 89%
to 75%: not a regression, the benchmark getting honest.

## Mirroring was a blind spot

Plain PDQ scored **124 to 132** on the mirrored variants — indistinguishable
from unrelated images — and recovered **1 of 10**. The probe was calling
`pdqhash.compute`, which has no orientation invariance.

`pdqhash.compute_dihedral` returns the hash under all 8 orientations of the
square symmetry group, at essentially the same cost (3.5 ms against 3.2 ms,
because the transform is applied to the DCT coefficients rather than by
re-hashing rotated images). Comparing against all 8 recovers **every mirrored
variant** — 10 of 10 then, 25 of 25 on the full set, at a median distance of 6.

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

# Ablation — what each probe and measure contributes

## Across probes

| probe | cases recovered |
| --- | --- |
| `c2pa` only | **0/25** |
| `phash` only | 13/25 |
| both | 13/25 |

**Not one of the 50 images in this corpus — originals and reused copies alike —
carries a C2PA manifest.**

That is the premise of the project measured rather than asserted. Platforms
strip Content Credentials on upload, so provenance metadata is unavailable
exactly where it would be most useful. It answers "why not just use C2PA?"
with a number instead of an argument, and it is the single most quotable line
in this document for Workshop 2.

The probe stays in the pipeline for two reasons. When a manifest *is* present
it is the only probe that can establish **attested context** rather than mere
appearance — see [`terminology.md`](terminology.md) — and its absence is itself
a finding worth reporting. But hashing carries the load, and whatever replaces
hashing carries the project.

## Inside the hash probe

With `c2pa` contributing nothing, the ablation that carries information is
which measure actually did the work:

| measure | cases | tier it reports |
| --- | --- | --- |
| PDQ | 6/13 | `strong` |
| crop-resistant segments | 3/13 | `strong` |
| pHash | 4/13 | `candidate` |

**No measure is redundant.** Dropping any one costs between a quarter and a
half of all recall:

- **PDQ** is the backbone — exact, fast, and the only one with a comfortable
  safety margin (63 to the noise floor).
- **Crop-resistant segments** earn their cost: 3 of 13 recoveries come from
  nowhere else, and they are the only thing that recovers any heavy crop.
- **pHash** contributes 4 of 13 — nearly a third — which settles an open
  question. Its margin is thin (4) and it produced the only surviving false
  positive, so dropping it was tempting. The ablation says it would cost 31% of
  recall to remove. It stays, at `candidate` tier, which is the honest place for
  a measure that is this useful and this noisy.

---

# Why the two numbers disagree

**52% on real reuse, 75% on synthetic transformations.** Both are correct. They
measure different things, and the difference is itself a finding.

A generated variant applies **one** transformation to an image, in a
controlled way. Real reuse applies **whatever a person did** — often a heavy,
off-centre crop, sometimes several changes at once, sometimes a re-edit.

The comparison that shows it:

| | synthetic centred 20% crop | synthetic off-centre crop | real crops |
| --- | --- | --- | --- |
| recall | 14/25 (56%) | 4–10/25 (16–40%) | **4/14 (29%)** |

Real cropping behaves like the **off-centre** variants, not the centred ones.
That is exactly why the off-centre crops were added, and it worked: the
synthetic set now brackets reality instead of flattering it.

So:

- **Use the synthetic curve to locate break-points.** That is what it is for,
  and it does it well — it is how we know the limit is near a 20% crop.
- **Do not quote 75% as expected real-world recall.** On real reuse this corpus
  gives 52%.
- **Report both, with this explanation.** A single number would be either
  pessimistic or misleading depending on which was picked.

Earlier drafts of this document quoted 40% and 89%, measured on 10 cases and
150 variants. Both moved, and **not only because the corpus grew**: real recall
rose because the new cases include more resizes, and synthetic recall fell
because the off-centre crops are harder than anything in the first set. A
benchmark number is a property of the benchmark as much as of the system, which
is the argument for reporting what is in it rather than just the score.

---

# What this means for the project

**Hashing solves the easy half of the problem, and solves it completely.**
Compression, resizing, screenshots, watermarks, text overlays and mirroring are
all at 25/25. It is fast, needs no API key and no network, and it is exact when
it fires. It is the right first probe.

**It cannot carry the demo on its own.** Twelve of twenty-five real cases return
`no_evidence`, and real-world reuse in this corpus is dominated by heavy,
off-centre cropping — 14 of the 25 cases are crops, and 10 of those are missed.

**Thresholds are a property of the corpus, not of the algorithm.** Two of the
three were re-derived when the dataset went from 10 cases to 25, and the
crop-resistant rule produced 8 false positives at 25 that did not exist at 10.
They will need deriving again at 40. This belongs in the report: it is the kind
of thing that is obvious in hindsight and expensive to discover late.

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
geometric verification, run as an experiment (not committed) on the **first 10
real pairs** — so these figures are against hashing's 4/10 on that same subset,
not against the 13/25 above. Worth re-running on all 25 before anyone acts on
it:

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
