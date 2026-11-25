# awt-pj-ws2627-smcrd-A

**Social Media Context Recovery against Disinformation**

Advanced Media Technologies project, WiSe 2026/27, TU Berlin / Fraunhofer FOKUS.
Supervisor: André Paul.

## The problem

Authentic images and videos reused in a false context. The media is genuine and
unedited — what is false is the claim about when, where, or under what
circumstances it was created. Standard forensics find nothing, because nothing
in the file was altered.

## What we are building

A browser extension. Right-click any image or video in a social feed and a side
panel answers three questions:

- **Where has this appeared before?** An earliest-appearance timeline, with the source of each hit.
- **What did it originally show?** The original caption, date and place.
- **How certain is that answer?** A stated confidence tier, with the evidence behind it.

We never label a post true or false. We answer factual questions and state how
confident we are.

## Terminology

These are kept strictly separate:

| Term | What it is | Where it comes from |
| --- | --- | --- |
| **Earliest known appearance** | A retrieval result | Our index plus reverse search. Measurable, possibly incomplete. |
| **Attested context** | A claim about what the media shows | Only a fact-check record, a C2PA manifest, or a publisher's own caption |
| **Confidence tier** | How strongly the evidence supports the answer | The two above |

**Rule:** never derive attested context from earliest appearance. The earliest
copy we find may not be the original, and may itself carry a false claim.

Full decision, with the date fields and what it changes in the schema and API:
[`docs/terminology.md`](docs/terminology.md).

## Scope

The French student protests of autumn 2026 are the motivating case study. The
evaluation corpus is deliberately **cross-event**, so results show whether the
system generalises rather than whether it was tuned to one event's
transformation patterns: [`docs/scope.md`](docs/scope.md).
The dataset lives in `data/dataset.csv` (UTF-8 with BOM), the only canonical file: edit it in Excel locally if you like, but export to CSV and run `python tools/check_dataset.py` before every commit.

## Pipeline

```
Capture → Normalise → Probe (C2PA · perceptual hash · web search) → Score → Panel
```

The three probes run independently, so a missing API key lowers confidence
rather than breaking the tool.

## Running the service

```bash
pip install -r requirements.txt
python tools/build_hash_index.py        # once, and again after the dataset changes
uvicorn service.main:app --reload --port 8000
```

Two ways in:

```bash
curl -s localhost:8000/health

# JSON — the service downloads the media itself
curl -s -X POST localhost:8000/verify \
     -H 'content-type: application/json' \
     -d '{"media_url": "https://example.social/media/abc.jpg"}'

# multipart — the caller sends the bytes
curl -s -X POST localhost:8000/verify/file -F file=@some-image.jpg
```

`POST /verify/file` exists because downloading is the fragile part: Instagram
and TikTok CDN URLs expire, video is served as `blob:` streams the service
cannot fetch at all, and some hosts refuse unauthenticated requests. The
extension already holds the bytes, so handing them over skips all of that.
**Use it for the demo.**

The C2PA and perceptual-hash probes are live. Reverse search and fact-check
lookup are not built, so they are listed in `probes_failed` rather than quietly
left out — the panel can then say which evidence was actually looked for.

Interactive schema: <http://localhost:8000/docs> · contract: [`docs/api.md`](docs/api.md)

### C2PA probe

```bash
python -m service.probes.c2pa_probe path/to/file.jpg
```

Prints the manifest summary, or reports that there is none. **No manifest is
the expected result** for anything downloaded from social media — platforms
strip them on upload. How often that happens across our corpus is a finding
for the report, not a bug.

Two fixtures are committed so both branches can be checked:

```bash
python -m service.probes.c2pa_probe tests/fixtures/signed-sample.jpg    # valid manifest
python -m service.probes.c2pa_probe tests/fixtures/unsigned-sample.jpg  # no manifest
```

`read_manifest_bytes(data, mime_type)` is the entry point the service uses —
media arrives from a download, in memory. `read_manifest(path)` wraps it for
the CLI.

Regenerate the signed fixture with `python tools/make_test_fixture.py <in> <out>`.
It uses the public c2pa-rs test certificates and documents the two traps that
cost an afternoon.

### Perceptual hash probe

```bash
python tools/build_hash_index.py                       # hash every original in the dataset
python -m service.probes.phash_probe some-image.jpg    # query it
python tools/evaluate_hashing.py                       # recall@k, date accuracy, ablation, false positives
python tools/evaluate_transformations.py               # synthetic set: survival per transformation
```

Three hashes, because they fail in different places: **PDQ** (Meta's 256-bit
hash, what platforms actually run, compared under all 8 orientations so a
mirrored copy still matches), **pHash** (the 64-bit academic baseline), and
**crop-resistant hashing** (per-segment, slow, so it only runs when the fast
hashes find nothing).

The index is keyed on `local_path_original`, not `earliest_url` — the CDN URLs
in the dataset carry expiry timestamps, so the committed media files are the
durable copy.

### Measured results

| | real reuse (25 cases) | synthetic variants (500) |
| --- | --- | --- |
| recall | **13/25 (52%)** | **373/500 (75%)** |
| false positives, `strong` | 0 in 600 | 0 in 12,000 |
| false positives, `candidate` | 0 | 1 |

Both are correct, and the gap is the finding. Compression, resizing,
screenshots, watermarks, text overlays and mirroring are all recovered 25/25.
Cropping is the break-point: full recall at 5% and 10%, 14/25 at 20%, then
collapse — 5/25 at 30%.

**No image in the corpus carries a C2PA manifest** — 0 of 50, originals and
reused copies alike. Platforms strip Content Credentials on upload, so the
provenance metadata is missing exactly where it would help most. That is the
project's premise, measured. Inside the hash probe no measure is redundant
either: PDQ finds 6 of the 13, crop-resistant segments 3, pHash 4.

Recall does not improve with k — recall@1, @3 and @5 are all 13/25. When
hashing finds the original it ranks first; when it misses, the original is not
in the list at all.

By transformation on real reuse: **resizes 8/8, crops 4/14**, AI edits 1/2.
Real crops are heavy and off-centre, which is what a global hash cannot
survive. The off-centre synthetic crops reproduce that (4–10 of 25), so the
synthetic set now brackets reality rather than flattering it — but it still
**overstates real-world recall**. Quote both numbers, not one.

Thresholds are a property of the corpus, not the algorithm: two of the three
had to be re-derived when the dataset grew from 10 cases to 25, and the
crop-resistant rule produced 8 false positives at 25 that did not exist at 10.
**Re-run both evaluations after adding cases.**

Thresholds, the measurements behind them, the mirroring blind spot and what to
do about crops: [`docs/findings-hashing.md`](docs/findings-hashing.md).

## Team

- Maryam Afzal Khan
- Mohamed Aziz Ben Aissa
- Luca Toni

## Milestones

| Date | Milestone |
| --- | --- |
| 4 Nov 2026 | Workshop 1 |
| 16 Dec 2026 | Workshop 2 |
| 10 Feb 2027 | Workshop 3 — final presentation and demo |
| 28 Feb 2027 | Final submission: report and source code |
