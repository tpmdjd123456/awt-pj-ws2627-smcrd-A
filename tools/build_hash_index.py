#!/usr/bin/env python3
"""Build the perceptual hash index from data/dataset.csv.

    python tools/build_hash_index.py

Writes data/hash_index.json. Re-run whenever the dataset changes.
Keyed on local_path_original rather than earliest_url, because Instagram and
TikTok CDN URLs expire — the committed files are the durable copy.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from service.probes.phash_probe import INDEX_PATH, build_index  # noqa: E402

if __name__ == "__main__":
    index = build_index()
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=1))
    print(f"\n{len(index['entries'])} entries -> {INDEX_PATH}")
