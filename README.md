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

## Pipeline

```
Capture → Normalise → Probe (C2PA · perceptual hash · web search) → Score → Panel
```

The three probes run independently, so a missing API key lowers confidence
rather than breaking the tool.

## Running the service

```bash
pip install -r requirements.txt
uvicorn service.main:app --reload --port 8000
```

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/verify \
     -H 'content-type: application/json' \
     -d '{"media_url": "https://example.social/media/abc.jpg"}'
```

`POST /verify` is a stub — it returns a hardcoded example regardless of input,
so the extension can be built against the real shape before the probes exist.
Add `?empty=true` for the no-evidence response, which the panel also has to
handle.

Interactive schema: <http://localhost:8000/docs> · contract: [`docs/api.md`](docs/api.md)

### C2PA probe

```bash
python -m service.probes.c2pa_probe path/to/file.jpg
```

Prints the manifest summary, or reports that there is none. **No manifest is
the expected result** for anything downloaded from social media — platforms
strip them on upload. How often that happens across our corpus is a finding
for the report, not a bug.

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
