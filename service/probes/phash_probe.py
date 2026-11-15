"""Perceptual hash probe — find near-duplicates of a query image in our index.

Three hashes, because they fail in different places (see docs/findings-hashing.md):

  PDQ               Meta's 256-bit hash, what platforms actually run. Very precise:
                    on our corpus, true pairs score 10-14 and unrelated images
                    never go below 104. Catches resizes and re-encodes.
  pHash             64-bit DCT hash, the academic baseline. Slightly more
                    sensitive than PDQ, with a much thinner safety margin.
  crop-resistant    Segments the image and hashes each segment. Recovers one
                    case the global hashes miss, with no false positives, but
                    it is slow — so it only runs when the fast hashes find
                    nothing.

None of them survive a heavy crop or an AI edit. That is measured, not assumed,
and it is the empirical reason the pipeline needs more than a hash index.

CLI:
    python -m service.probes.phash_probe <image>
"""

from __future__ import annotations

import io
import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

warnings.filterwarnings("ignore", module="imagehash")

import imagehash  # noqa: E402
import pdqhash  # noqa: E402

PROBE_NAME = "phash"

INDEX_PATH = Path("data/hash_index.json")

# Thresholds derived from the 10 real pairs in data/dataset.csv plus every
# original compared against every other original. See docs/findings-hashing.md
# for the measurements these come from. Re-derive them when the dataset grows.
PDQ_STRONG = 31          # Meta's own guidance; our unrelated floor is 104
PHASH_CANDIDATE = 18     # 20 produced a false positive at exactly the threshold
CROP_SEGMENT_DIST = 16   # max per-segment distance for a crop-resistant match
CROP_MIN_SEGMENTS = 2    # one matched segment is a coincidence — it false-positived


# --- hashing --------------------------------------------------------------


def _pdq_bits(img: Image.Image) -> tuple[np.ndarray, int]:
    bits, quality = pdqhash.compute(np.asarray(img.convert("RGB")))
    return np.array(bits, dtype=np.uint8), int(quality)


def _pdq_hex(bits: np.ndarray) -> str:
    return "".join(f"{b:02x}" for b in np.packbits(bits))


def _pdq_from_hex(hexs: str) -> np.ndarray:
    return np.unpackbits(np.frombuffer(bytes.fromhex(hexs), dtype=np.uint8))


def pdq_distance(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def hash_image(img: Image.Image, include_crop_resistant: bool = True) -> dict[str, Any]:
    """Compute every hash we use for one image."""
    img = img.convert("RGB")
    bits, quality = _pdq_bits(img)
    out: dict[str, Any] = {
        "pdq": _pdq_hex(bits),
        "pdq_quality": quality,
        "phash": str(imagehash.phash(img)),
        "dhash": str(imagehash.dhash(img)),
    }
    if include_crop_resistant:
        multi = imagehash.crop_resistant_hash(img)
        out["crop_resistant"] = [str(h) for h in multi.segment_hashes]
    return out


def _multihash(segments: list[str]) -> "imagehash.ImageMultiHash":
    return imagehash.ImageMultiHash([imagehash.hex_to_hash(s) for s in segments])


# --- index ----------------------------------------------------------------


def build_index(csv_path: str | Path = "data/dataset.csv") -> dict[str, Any]:
    """Hash every earliest-known copy in the dataset.

    Keyed on local_path_original, not earliest_url: Instagram and TikTok CDN
    URLs carry expiry timestamps, so the committed files are the durable copy.
    """
    import csv

    entries = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            path = Path(row["local_path_original"])
            if not path.is_file():
                print(f"  skipped {row['case_id']}: missing {path}")
                continue
            with Image.open(path) as img:
                hashes = hash_image(img)
            entries.append(
                {
                    "case_id": row["case_id"],
                    "event": row["event"],
                    "path": str(path),
                    "earliest_date": row["earliest_date"],
                    "earliest_source": row["earliest_source"],
                    "earliest_url": row["earliest_url"],
                    "earliest_caption": row["earliest_caption"],
                    **hashes,
                }
            )
            print(f"  hashed {row['case_id']}")

    return {"version": 1, "source": str(csv_path), "entries": entries}


def load_index(path: str | Path = INDEX_PATH) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text())


# --- query ----------------------------------------------------------------


def query_bytes(data: bytes, index: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Rank index entries against a query image. Best candidate first.

    Fast hashes first. Crop-resistant hashing only runs if nothing clears
    PDQ_STRONG, because it costs seconds per comparison.
    """
    index = index if index is not None else load_index()
    if not index:
        return []

    with Image.open(io.BytesIO(data)) as img:
        q = hash_image(img, include_crop_resistant=False)

    q_pdq = _pdq_from_hex(q["pdq"])
    q_phash = imagehash.hex_to_hash(q["phash"])

    results = []
    for e in index["entries"]:
        results.append(
            {
                "case_id": e["case_id"],
                "date": e["earliest_date"],
                "source": e["earliest_source"],
                "url": e["earliest_url"],
                "caption": e["earliest_caption"],
                "pdq_distance": pdq_distance(q_pdq, _pdq_from_hex(e["pdq"])),
                "phash_distance": int(q_phash - imagehash.hex_to_hash(e["phash"])),
                "crop_segments_matched": None,
                "crop_distance": None,
            }
        )

    if not any(r["pdq_distance"] <= PDQ_STRONG for r in results):
        with Image.open(io.BytesIO(data)) as img:
            q_multi = imagehash.crop_resistant_hash(img.convert("RGB"))
        for r, e in zip(results, index["entries"]):
            if not e.get("crop_resistant"):
                continue
            matched, dist = q_multi.hash_diff(_multihash(e["crop_resistant"]))
            r["crop_segments_matched"] = int(matched)
            r["crop_distance"] = int(dist)

    for r in results:
        r["match_strength"] = _strength(r)

    order = {"strong": 0, "candidate": 1, "none": 2}
    results.sort(key=lambda r: (order[r["match_strength"]], r["pdq_distance"]))
    return results


def _strength(r: dict[str, Any]) -> str:
    if r["pdq_distance"] <= PDQ_STRONG:
        return "strong"
    if (
        r["crop_segments_matched"]
        and r["crop_segments_matched"] >= CROP_MIN_SEGMENTS
        and r["crop_distance"] is not None
        and r["crop_distance"] <= CROP_SEGMENT_DIST
    ):
        return "strong"
    if r["phash_distance"] <= PHASH_CANDIDATE:
        return "candidate"
    return "none"


def best_match(data: bytes, index: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The single best candidate, or None if nothing clears the thresholds."""
    for r in query_bytes(data, index):
        if r["match_strength"] != "none":
            return r
    return None


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"error: no such file: {path}")
        return 1
    if load_index() is None:
        print(f"error: no index at {INDEX_PATH}. Run: python tools/build_hash_index.py")
        return 1

    results = query_bytes(path.read_bytes())
    print(f"{path}: {len(results)} index entries compared\n")
    print(f"{'case':9} {'strength':10} {'PDQ':>5} {'pHash':>6} {'cropSeg':>8} {'cropDist':>9}")
    print("-" * 56)
    for r in results[:8]:
        cs = "-" if r["crop_segments_matched"] is None else r["crop_segments_matched"]
        cd = "-" if r["crop_distance"] is None else r["crop_distance"]
        print(
            f"{r['case_id']:9} {r['match_strength']:10} {r['pdq_distance']:5} "
            f"{r['phash_distance']:6} {str(cs):>8} {str(cd):>9}"
        )
    best = next((r for r in results if r["match_strength"] != "none"), None)
    print()
    if best:
        print(f"best: {best['case_id']} — {best['date']} · {best['source']} ({best['match_strength']})")
    else:
        print("no match above threshold — the panel reports this as no_evidence")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
