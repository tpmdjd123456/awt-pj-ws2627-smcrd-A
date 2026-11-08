# Verification service API

Contract between the browser extension and the verification service.
Published so the extension can be built before the probes are real.

Base URL in development: `http://localhost:8000`

---

## `GET /health`

```json
{ "ok": true, "version": "0.1.0" }
```

---

## `POST /verify`

### Request

```json
{
  "media_url":    "https://example.social/media/abc123.jpg",
  "post_url":     "https://example.social/@someaccount/114029...",
  "post_caption": "Paris right now! The city is burning",
  "post_date":    "2026-10-14T09:12:00Z",
  "post_author":  "@someaccount",
  "platform":     "mastodon"
}
```

Only `media_url` is required. Everything else is best-effort from the page —
send `null` for anything the content script could not find.

`post_caption` matters more than it looks: it is the text we later compare
against the recovered original claim. That comparison is what exposes the
reuse.

### Response

```json
{
  "query_id":     "q_7f3a9c21",
  "media_sha256": "9f2b1c4e...",

  "earliest_known_appearance": {
    "date":          "2023-03-14",
    "source":        "Reuters",
    "url":           "https://www.reuters.com/world/europe/...",
    "caption":       "Clashes between police and protesters in Angers",
    "evidence_type": "hash_match",
    "distance":      4
  },

  "candidates": [
    {
      "date":          "2023-07-02",
      "source":        "x.com/@someone",
      "url":           "https://x.com/someone/status/...",
      "caption":       null,
      "evidence_type": "reverse_search",
      "distance":      null
    }
  ],

  "attested_context": {
    "description":   "Clashes between police and protesters in Angers during the pension reform protests",
    "date":          "2023-03-14",
    "location":      "Angers, France",
    "source":        "Reuters Fact Check",
    "url":           "https://www.reuters.com/fact-check/...",
    "evidence_type": "factcheck"
  },

  "confidence_tier": "strong_match",
  "probes_run":      ["c2pa", "phash", "factcheck"],
  "probes_failed":   ["reverse_search"],
  "elapsed_ms":      1840
}
```

---

## The two outputs are independent

This is the rule from [`terminology.md`](terminology.md), expressed in the
response shape:

- **`earliest_known_appearance`** is a retrieval result. A date and a source we
  found. It says nothing about whether the claim attached to it is true.
- **`attested_context`** is what the media actually shows. It is only ever
  populated from a fact-check record, a valid C2PA manifest, or the earliest
  *credible publisher's* own caption.

**Either may be `null` while the other is populated.** `attested_context` is
never filled in from `earliest_known_appearance`.

Why: if someone reposted the Angers video in July 2023 captioned "riots in
Marseille", and our search finds that post but misses the March original, then
treating earliest as original makes us report Marseille as the truth. We would
have confidently repeated a different lie.

So all four combinations are valid responses:

| `earliest_known_appearance` | `attested_context` | What the panel says |
| --- | --- | --- |
| set | set | Full answer — earliest appearance plus verified context |
| set | `null` | "Published at least as early as *date*. No verified context available." |
| `null` | set | Rare. A C2PA manifest with no earlier copy found. |
| `null` | `null` | "No earlier appearance found. **This is not a clearance.**" |

That last cell matters. Finding nothing is not evidence that a post is honest,
and the panel must not let it read that way.

---

## Enums

### `evidence_type`

| Value | Meaning |
| --- | --- |
| `c2pa_manifest` | From a valid C2PA manifest embedded in or recovered for the file |
| `hash_match` | Perceptual hash match against our own index |
| `reverse_search` | A reverse image search hit, unconfirmed by hashing |
| `factcheck` | From a published fact-check record |
| `publisher_caption` | The earliest credible publisher's own caption |

### `confidence_tier`

| Value | Requires |
| --- | --- |
| `verified_origin` | Valid C2PA manifest, signature chain trusted |
| `strong_match` | Hash distance under threshold to an indexed original |
| `candidate_match` | Reverse-search hit only, no hash confirmation |
| `no_evidence` | Nothing recovered by any probe |

---

## `probes_run` and `probes_failed`

Probe names: `c2pa`, `phash`, `reverse_search`, `factcheck`.

A probe in `probes_failed` is **not an error**. A missing API key, a rate
limit or a timeout lowers our confidence; it does not break the response. The
panel should say which probes did not run, so the user can read the confidence
tier correctly.

The service always returns `200` with a complete body unless the request
itself was malformed.

---

## Status

Implemented as a **stub**: `POST /verify` currently returns the hardcoded
example above regardless of input. Field names and shape are real. Probes are
wired in from week 2 onward.

Interactive schema while the service is running: `http://localhost:8000/docs`
