"""Check that every file named in data/dataset.csv exists on disk.

Run from the repository root:  python tools/check_dataset.py
"""
import csv
import os

CSV_PATH = "data/dataset.csv"

missing = 0
with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

for row in rows:
    for column in ("local_path_original", "local_path_reused"):
        path = row[column].strip()
        if not os.path.isfile(path):
            missing += 1
            print(f"MISSING  {row['case_id']}  {column}: {path}")

print(f"\n{len(rows)} cases checked, {missing} files missing.")