#!/usr/bin/env python3
"""Hash survival per transformation, against data/transformed/ (from #10).

For every generated variant: query it against the hash index, and record
whether its own original came back above threshold, and whether anything else
did. Groups the results by transformation and strength, which is what gives a
break-point rather than a single recall number.

    python tools/build_hash_index.py          # if the index is stale
    python tools/evaluate_transformations.py
    python tools/evaluate_transformations.py --only crop mirror

Read the two caveats at the bottom of the output before quoting the headline
percentage anywhere.
"""

from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.probes.phash_probe import (  # noqa: E402
    PDQ_STRONG,
    PHASH_CANDIDATE,
    load_index,
    query_bytes,
)

MANIFEST = Path("data/transformed/transformations.csv")

# Printed in this order; anything not listed is appended alphabetically.
ORDER = [
    "none_original",
    "re_encode_q90", "re_encode_q70", "re_encode_q50",
    "resize_50", "resize_25",
    "screenshot_s90q75",
    "logo_corner",
    "text_overlay_bar", "text_overlay_meme",
    "mirror_h",
    "crop_10", "crop_20", "crop_30", "crop_40",
]


def median(values: list[int]) -> int:
    v = sorted(values)
    return v[len(v) // 2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="only these transformations")
    args = ap.parse_args()

    if not MANIFEST.is_file():
        print(f"error: no manifest at {MANIFEST}. Run tools/generate_transformations.py")
        return 1

    index = load_index()
    if not index:
        print("error: no hash index. Run tools/build_hash_index.py")
        return 1

    rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8-sig")))
    if args.only:
        rows = [r for r in rows if r["transformation"] in args.only]

    stats: dict[str, dict] = collections.defaultdict(
        lambda: {"n": 0, "strong": 0, "candidate": 0, "miss": 0,
                 "pdq": [], "phash": [], "fp": 0, "orientations": collections.Counter()}
    )
    false_positives = []

    print(f"querying {len(rows)} variants against {len(index['entries'])} index entries\n")
    for i, r in enumerate(rows, 1):
        path = Path(r["output_path"])
        if not path.is_file():
            print(f"  missing file, skipped: {path}")
            continue
        results = query_bytes(path.read_bytes(), index)
        by_case = {x["case_id"]: x for x in results}
        own = by_case.get(r["case_id"])
        if own is None:
            print(f"  {r['case_id']} is not in the index, skipped")
            continue

        key = f"{r['transformation']}_{r['strength']}"
        s = stats[key]
        s["n"] += 1
        s[own["match_strength"] if own["match_strength"] != "none" else "miss"] += 1
        s["pdq"].append(own["pdq_distance"])
        s["phash"].append(own["phash_distance"])
        if own["match_strength"] != "none":
            s["orientations"][own["pdq_orientation"]] += 1

        for cid, x in by_case.items():
            if cid != r["case_id"] and x["match_strength"] != "none":
                s["fp"] += 1
                false_positives.append((path.as_posix(), cid, x))

        if i % 25 == 0:
            print(f"  {i}/{len(rows)}")

    keys = [k for k in ORDER if k in stats] + sorted(k for k in stats if k not in ORDER)

    print(f"\n{'variant':20} {'found':>8} {'strong':>7} {'cand':>5} {'miss':>5} "
          f"{'medPDQ':>7} {'medpH':>6} {'FP':>4}")
    print("-" * 72)
    tot = collections.Counter()
    for k in keys:
        s = stats[k]
        found = s["strong"] + s["candidate"]
        tot["n"] += s["n"]; tot["found"] += found; tot["fp"] += s["fp"]
        print(f"{k:20} {found:5}/{s['n']:<2} {s['strong']:7} {s['candidate']:5} "
              f"{s['miss']:5} {median(s['pdq']):7} {median(s['phash']):6} {s['fp']:4}")
    print("-" * 72)
    pct = tot["found"] / tot["n"] * 100 if tot["n"] else 0
    print(f"{'TOTAL':20} {tot['found']:5}/{tot['n']:<2}  "
          f"({pct:.0f}%)        false positives: {tot['fp']}")

    # Only real orientations, not None (PDQ did not match) or identity.
    oriented = {}
    for k in keys:
        turned = {o: n for o, n in stats[k]["orientations"].items()
                  if o not in (None, "identity")}
        if turned:
            oriented[k] = turned
    if oriented:
        print("\nmatched under a non-identity orientation:")
        for k, counts in oriented.items():
            print(f"  {k}: {counts}")

    if false_positives:
        print(f"\nfalse positives ({len(false_positives)}):")
        for p, cid, x in false_positives[:10]:
            print(f"  {p} -> {cid} as {x['match_strength']} "
                  f"(PDQ {x['pdq_distance']}, pHash {x['phash_distance']})")

    print(f"\nthresholds: PDQ <= {PDQ_STRONG}, pHash <= {PHASH_CANDIDATE}")
    print("""
Two caveats before quoting the headline number:

1. Every variant here preserves aspect ratio — the crops are centred, removing
   the same fraction from both dimensions. In the 10 real cases, 8 of 10 changed
   aspect ratio, and hashing found 1 of 5 real crops against 8 of 10 synthetic
   20% crops. This curve locates break-points; it overstates real-world recall.

2. These are all transformations of images already in the index. Real queries
   are of media that may not be in it at all, where the honest answer is
   no_evidence.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
