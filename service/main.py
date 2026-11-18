"""Verification service.

The perceptual hash probe is live: `/verify` returns real matches against our
own index. The reverse-search and fact-check probes are not built yet, so they
report in `probes_failed` rather than silently going missing.

Run:
    pip install -r requirements.txt
    python tools/build_hash_index.py        # once, and after the dataset changes
    uvicorn service.main:app --reload --port 8000

Two ways in:
    POST /verify        JSON, with media_url — the service downloads it
    POST /verify/file   multipart upload — the caller sends the bytes

/verify/file exists because downloading is the fragile part: Instagram and
TikTok CDN URLs expire, video is served as blob: streams the service cannot
fetch at all, and some hosts refuse unauthenticated requests. The extension
already holds the bytes, so handing them over skips every one of those
problems. Use it for the demo.

Interactive schema: http://localhost:8000/docs
"""

from __future__ import annotations

import time
import urllib.request

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from service.models import (
    Appearance,
    AttestedContext,
    ConfidenceTier,
    EvidenceType,
    Health,
    VerifyRequest,
    VerifyResponse,
)
from service.probes import c2pa_probe, phash_probe

VERSION = "0.2.0"

# Probes that exist. Anything not here lands in probes_failed, so the panel can
# tell the user which evidence was actually looked for.
PLANNED_PROBES = ["c2pa", "phash", "reverse_search", "factcheck"]

app = FastAPI(
    title="SMCRD verification service",
    version=VERSION,
    description="Social Media Context Recovery against Disinformation — AWT PJ WS26/27",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_INDEX = None


def index():
    global _INDEX
    if _INDEX is None:
        _INDEX = phash_probe.load_index()
    return _INDEX


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(ok=True, version=VERSION)


def _tier(strength: str | None, c2pa_valid: bool) -> ConfidenceTier:
    if c2pa_valid:
        return ConfidenceTier.verified_origin
    if strength == "strong":
        return ConfidenceTier.strong_match
    if strength == "candidate":
        return ConfidenceTier.candidate_match
    return ConfidenceTier.no_evidence


def run_probes(data: bytes, mime: str = "image/jpeg") -> VerifyResponse:
    """The real pipeline, as far as it exists."""
    started = time.perf_counter()
    ran, failed = [], []

    # --- C2PA ---------------------------------------------------------------
    manifest = None
    try:
        manifest = c2pa_probe.read_manifest_bytes(data, mime)
        ran.append("c2pa")
    except Exception:
        failed.append("c2pa")

    # --- perceptual hash ----------------------------------------------------
    candidates: list[Appearance] = []
    best = None
    if index() is None:
        failed.append("phash")
    else:
        try:
            results = phash_probe.query_bytes(data, index())
            ran.append("phash")
            for r in results:
                if r["match_strength"] == "none":
                    continue
                candidates.append(
                    Appearance(
                        date=r["date"] or None,
                        source=r["source"] or None,
                        url=r["url"] or None,
                        caption=r["caption"] or None,
                        evidence_type=EvidenceType.hash_match,
                        distance=r["match_distance"],
                        method=r["match_method"],
                        orientation=(
                            None
                            if r.get("pdq_orientation") in (None, "identity")
                            else r["pdq_orientation"]
                        ),
                    )
                )
            best = next((r for r in results if r["match_strength"] != "none"), None)
        except Exception:
            failed.append("phash")

    # Not built yet. Reported as failed rather than quietly omitted, so the
    # confidence tier can be read honestly.
    failed += ["reverse_search", "factcheck"]

    earliest = candidates[0] if candidates else None

    # attested_context stays None on every path here. A hash match says WHERE
    # the media appeared, never WHAT it shows — see docs/terminology.md. It is
    # only ever filled from a fact-check, a C2PA manifest or a credible
    # publisher's own caption, and the first two of those are not wired yet.
    attested: AttestedContext | None = None

    c2pa_valid = bool(manifest and manifest.get("is_valid"))

    return VerifyResponse(
        query_id=f"q_{int(time.time() * 1000) % 100000000:08x}",
        media_sha256=None,
        earliest_known_appearance=earliest,
        candidates=candidates[1:],
        attested_context=attested,
        confidence_tier=_tier(best["match_strength"] if best else None, c2pa_valid),
        probes_run=ran,
        probes_failed=[p for p in PLANNED_PROBES if p in failed],
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


@app.post("/verify", response_model=VerifyResponse)
def verify(request: VerifyRequest) -> VerifyResponse:
    """Download the media and run the probes.

    Downloading is the fragile part — expiring CDN URLs, blob: streams, hosts
    that refuse unauthenticated requests. If it fails, every probe reports as
    failed and the tier is no_evidence, which is the honest answer: we could
    not look, so we found nothing.
    """
    try:
        req = urllib.request.Request(
            request.media_url, headers={"User-Agent": "smcrd-verifier/0.2"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            mime = resp.headers.get_content_type() or "image/jpeg"
    except Exception:
        return VerifyResponse(
            query_id="q_fetchfail",
            confidence_tier=ConfidenceTier.no_evidence,
            probes_run=[],
            probes_failed=PLANNED_PROBES,
            elapsed_ms=0,
        )
    return run_probes(data, mime)


@app.post("/verify/file", response_model=VerifyResponse)
async def verify_file(file: UploadFile = File(...)) -> VerifyResponse:
    """Run the probes on uploaded bytes. No download, so nothing to fail."""
    return run_probes(await file.read(), file.content_type or "image/jpeg")
