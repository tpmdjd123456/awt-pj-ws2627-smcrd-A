
"""
 
Posts each case's reused image (local_path_reused) with its reused caption (reused_caption),
as "unlisted", behind a content warning that marks it as a research demo.
 
Usage (from the repo root):
    export MASTODON_URL=https://mastodon.social
    export MASTODON_TOKEN=...            # never commit this
    python tools/seed_mastodon.py data/dataset.csv --dry-run           # check only, posts nothing
    python tools/seed_mastodon.py data/dataset.csv --only case_01 --weeks 0   # one test post in ~1 h
    python tools/seed_mastodon.py data/dataset.csv --weeks 6                  # all cases over 6 weeks
"""

import argparse, csv, os, random, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_CHARS = 500  # Mastodon default post limit (links count as 23 characters)
CW = "Research demo: real image, deliberately false context (TU Berlin student project)"
TAG = "\n\n#SMCRDdemo"


def post_text(row):
    return row["reused_caption"].strip() + TAG


def check(rows, root):
    problems = []
    for r in rows:
        path = root / r["local_path_reused"]
        if not path.is_file():
            problems.append(f"{r['case_id']}: image not found: {path}")
        if not r["reused_caption"].strip():
            problems.append(f"{r['case_id']}: empty reused_caption")
        if len(post_text(r)) > MAX_CHARS:
            problems.append(f"{r['case_id']}: caption too long ({len(post_text(r))} > {MAX_CHARS})")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--weeks", type=float, default=6, help="spread posts over this many weeks (0 = all in ~1 h)")
    ap.add_argument("--only", help="comma-separated case_ids, e.g. case_01,case_02")
    ap.add_argument("--dry-run", action="store_true", help="check files and print the plan, post nothing")
    ap.add_argument("--no-cw", action="store_true", help="post without the content warning")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    root = Path.cwd()  # local_path_reused is relative to the repo root
    rows = [r for r in csv.DictReader(open(csv_path, encoding="utf-8-sig")) if r.get("case_id")]
    if args.only:
        wanted = set(args.only.split(","))
        rows = [r for r in rows if r["case_id"] in wanted]
    if not rows:
        sys.exit("No cases selected.")

    problems = check(rows, root)
    if problems:
        print("Not posting anything. Fix these first:")
        print("\n".join("  " + p for p in problems))
        sys.exit(1)

    start = datetime.now(timezone.utc) + timedelta(hours=1)
    step = timedelta(weeks=args.weeks) / max(len(rows), 1)
    plan = []
    for i, r in enumerate(rows):
        jitter = timedelta(minutes=random.randint(0, 240)) if args.weeks > 0 else timedelta(minutes=5 * i)
        plan.append((r, start + step * i + jitter))

    for r, when in plan:
        print(f"{r['case_id']}  {when:%Y-%m-%d %H:%M} UTC  {r['local_path_reused']}")
    if args.dry_run:
        print(f"\nDry run: {len(plan)} posts planned, nothing sent.")
        return

    import requests
    base = os.environ["MASTODON_URL"].rstrip("/")
    head = {"Authorization": f"Bearer {os.environ['MASTODON_TOKEN']}"}

    for r, when in plan:
        with open(root / r["local_path_reused"], "rb") as f:
            m = requests.post(f"{base}/api/v2/media", headers=head, files={"file": f})
        m.raise_for_status()
        data = {
            "status": post_text(r),
            "media_ids[]": m.json()["id"],
            "visibility": "unlisted",
            "scheduled_at": when.isoformat(),
            "language": "en",
        }
        if not args.no_cw:
            data["spoiler_text"] = CW
        s = requests.post(f"{base}/api/v1/statuses", headers=head, data=data)
        s.raise_for_status()
        print(f"scheduled {r['case_id']} for {when:%Y-%m-%d %H:%M} UTC (id {s.json().get('id')})")


if __name__ == "__main__":
    main()
