"""Check data/dataset.csv: files present, dates sane, citations filled.

Run from the repository root:  python tools/check_dataset.py

Exits non-zero if anything fails, so it can gate a commit.

The date check is the one that catches silent damage. "Earliest known
appearance" only means something if it is earlier than the post reusing it, so
`earliest_date` must precede `reused_date`. A transcription slip there does not
break anything visibly: it produces a row that still loads, still hashes, and
still contributes a wrong number to the report.
"""
import csv
import os
import sys
from datetime import date

CSV_PATH = "data/dataset.csv"

PATH_COLUMNS = ("local_path_original", "local_path_reused", "local_path_reused_post")

# Agreed with Maryam, 26 Nov: a fact-check establishes the provenance of the
# media (original source and date), not which copy came first. So every row
# needs the fact-check that attributes it, and the earliest_* fields that must
# be consistent with that attribution.
REQUIRED = (
    "factcheck_url",
    "factcheck_outlet",
    "earliest_url",
    "earliest_date",
    "earliest_source",
    "reused_date",
    "resolvable",
)


def parse_date(value: str):
    """ISO date, or None. Accepts a timestamp and keeps the date part."""
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None


def main() -> int:
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    missing_files = []
    missing_fields = []
    bad_dates = []
    gaps = []

    for row in rows:
        cid = row["case_id"]

        for column in PATH_COLUMNS:
            path = (row.get(column) or "").strip()
            if not path:
                missing_fields.append((cid, column, "empty"))
            elif not os.path.isfile(path):
                missing_files.append((cid, column, path))

        for column in REQUIRED:
            if not (row.get(column) or "").strip():
                missing_fields.append((cid, column, "empty"))

        earliest = parse_date(row.get("earliest_date", ""))
        reused = parse_date(row.get("reused_date", ""))
        if earliest is None or reused is None:
            bad_dates.append((cid, "unparseable",
                              f"earliest={row.get('earliest_date')!r} "
                              f"reused={row.get('reused_date')!r}"))
        elif earliest >= reused:
            bad_dates.append((cid, "not earlier",
                              f"earliest_date {earliest} is not before "
                              f"reused_date {reused}"))
        else:
            gaps.append((reused - earliest).days)

    for cid, column, path in missing_files:
        print(f"MISSING FILE   {cid}  {column}: {path}")
    for cid, column, why in missing_fields:
        print(f"MISSING FIELD  {cid}  {column}: {why}")
    for cid, kind, detail in bad_dates:
        print(f"BAD DATE       {cid}  {kind}: {detail}")

    failures = len(missing_files) + len(missing_fields) + len(bad_dates)
    print(f"\n{len(rows)} cases checked.")
    print(f"  files missing      : {len(missing_files)}")
    print(f"  fields empty       : {len(missing_fields)}")
    print(f"  dates wrong        : {len(bad_dates)}")
    if gaps:
        gaps.sort()
        print(f"  earliest -> reused : {gaps[0]} to {gaps[-1]} days "
              f"(median {gaps[len(gaps) // 2]})")

    if failures:
        print(f"\nFAILED — {failures} problem(s).")
        return 1
    print("\nOK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
