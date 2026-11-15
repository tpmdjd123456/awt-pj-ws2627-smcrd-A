#!/usr/bin/env python3
"""Measure how well perceptual hashing recovers the originals in our dataset.

    python tools/evaluate_hashing.py

Two numbers that matter, and you need both:

  recall          For each reused image, does querying the index return its
                  own original as the best match?
  false positives Every original compared against every other original. The
                  pairs alone cannot tell you this, and a threshold tuned on
                  pairs alone matches everything.

Writes nothing. Prints a table and the summary that goes in the report.
"""
import csv
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from service.probes.phash_probe import (  # noqa: E402
    PDQ_STRONG, PHASH_CANDIDATE, load_index, query_bytes,
)

index = load_index()
if not index:
    sys.exit("no index — run python tools/build_hash_index.py first")

rows = list(csv.DictReader(open("data/dataset.csv", encoding="utf-8-sig")))
by_id = {e["case_id"]: e for e in index["entries"]}

print(f"{'case':9} {'transformation':15} {'found':6} {'rank':>5} {'strength':10} {'PDQ':>5} {'pHash':>6}")
print("-" * 70)

hits = {"strong": 0, "candidate": 0, "none": 0}
correct_top = 0
for row in rows:
    reused = Path(row["local_path_reused"])
    if not reused.is_file():
        continue
    results = query_bytes(reused.read_bytes(), index)
    own = next((i for i, r in enumerate(results) if r["case_id"] == row["case_id"]), None)
    r = results[own] if own is not None else None
    matched = [x for x in results if x["match_strength"] != "none"]
    top_is_own = bool(matched) and matched[0]["case_id"] == row["case_id"]
    correct_top += top_is_own
    hits[r["match_strength"]] += 1
    print(
        f"{row['case_id']:9} {row['transformation_observed'][:15]:15} "
        f"{'yes' if top_is_own else 'no':6} {own + 1 if own is not None else '-':>5} "
        f"{r['match_strength']:10} {r['pdq_distance']:5} {r['phash_distance']:6}"
    )

n = len(rows)
print()
print(f"recall@1 (own original is the best match above threshold): {correct_top}/{n}")
print(f"  strength of the correct entry: strong {hits['strong']}, "
      f"candidate {hits['candidate']}, below threshold {hits['none']}")

print()
print("=== false positives: query each REUSED image, count wrong entries above threshold")
print("    (originals vs originals is not enough — transformation moves hashes toward")
print("     the noise floor, which is where false positives appear)")
total_wrong = 0
for row in rows:
    reused = Path(row["local_path_reused"])
    if not reused.is_file():
        continue
    res = query_bytes(reused.read_bytes(), index)
    wrong = [r for r in res if r["match_strength"] != "none" and r["case_id"] != row["case_id"]]
    total_wrong += len(wrong)
    if wrong:
        detail = ", ".join(
            f"{w['case_id']}({w['match_strength']}, pdq={w['pdq_distance']}, "
            f"ph={w['phash_distance']}, seg={w['crop_segments_matched']})" for w in wrong)
        print(f"  {row['case_id']}: {len(wrong)} wrong -> {detail}")
n_cmp = len(rows) * (len(by_id) - 1)
print(f"  {total_wrong} false positives in {n_cmp} non-matching comparisons")

print()
print("=== baseline: every original vs every other original (untransformed)")
worst_pdq = worst_phash = None
import imagehash  # noqa: E402
from service.probes.phash_probe import _pdq_from_hex, pdq_distance  # noqa: E402

for a, b in itertools.combinations(by_id, 2):
    pd = pdq_distance(_pdq_from_hex(by_id[a]["pdq"]), _pdq_from_hex(by_id[b]["pdq"]))
    ph = int(imagehash.hex_to_hash(by_id[a]["phash"]) - imagehash.hex_to_hash(by_id[b]["phash"]))
    worst_pdq = pd if worst_pdq is None else min(worst_pdq, pd)
    worst_phash = ph if worst_phash is None else min(worst_phash, ph)

print(f"  closest unrelated pair — PDQ {worst_pdq} (threshold {PDQ_STRONG}, "
      f"margin {worst_pdq - PDQ_STRONG})")
print(f"  closest unrelated pair — pHash {worst_phash} (threshold {PHASH_CANDIDATE}, "
      f"margin {worst_phash - PHASH_CANDIDATE})")
print(f"  false positives at current thresholds: "
      f"{'0' if worst_pdq > PDQ_STRONG and worst_phash > PHASH_CANDIDATE else 'SOME — retune'}")
