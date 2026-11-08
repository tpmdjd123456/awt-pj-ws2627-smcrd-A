"""Verification service — stub.

POST /verify currently returns a hardcoded example regardless of input. The
field names and the response shape are real, so the extension can be built
against it today. Probes get wired in from week 2.

Run:
    pip install -r requirements.txt
    uvicorn service.main:app --reload --port 8000

Then:
    curl -s localhost:8000/health
    curl -s -X POST localhost:8000/verify \
         -H 'content-type: application/json' \
         -d '{"media_url": "https://example.social/media/abc.jpg"}'

Interactive schema: http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
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

VERSION = "0.1.0"

app = FastAPI(
    title="SMCRD verification service",
    version=VERSION,
    description="Social Media Context Recovery against Disinformation — AWT PJ WS26/27",
)

# The extension calls this from a page context, so it needs CORS.
# Wide open is fine for local development; tighten before anything is hosted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- stub data ------------------------------------------------------------
# The Angers case from the Workshop 1 deck, as it should come back once the
# probes are real. Replace piece by piece as each probe lands.

STUB = VerifyResponse(
    query_id="q_7f3a9c21",
    media_sha256="9f2b1c4e00000000000000000000000000000000000000000000000000000000",
    earliest_known_appearance=Appearance(
        date="2023-03-14",
        source="Reuters",
        url="https://www.reuters.com/world/europe/",
        caption="Clashes between police and protesters in Angers",
        evidence_type=EvidenceType.hash_match,
        distance=4,
    ),
    candidates=[
        Appearance(
            date="2023-07-02",
            source="x.com/@someone",
            url="https://x.com/someone/status/0",
            evidence_type=EvidenceType.reverse_search,
        )
    ],
    attested_context=AttestedContext(
        description=(
            "Clashes between police and protesters in Angers during the "
            "pension reform protests"
        ),
        date="2023-03-14",
        location="Angers, France",
        source="Reuters Fact Check",
        url="https://www.reuters.com/fact-check/",
        evidence_type=EvidenceType.factcheck,
    ),
    confidence_tier=ConfidenceTier.strong_match,
    probes_run=["c2pa", "phash", "factcheck"],
    probes_failed=["reverse_search"],
    elapsed_ms=1840,
)

# A second shape worth building the panel against: nothing was found.
# Swap STUB for this to check the panel does not read as a clean bill of health.
STUB_NO_EVIDENCE = VerifyResponse(
    query_id="q_0000empty",
    media_sha256=None,
    earliest_known_appearance=None,
    candidates=[],
    attested_context=None,
    confidence_tier=ConfidenceTier.no_evidence,
    probes_run=["c2pa", "phash"],
    probes_failed=["reverse_search", "factcheck"],
    elapsed_ms=620,
)


# --- routes ---------------------------------------------------------------


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(ok=True, version=VERSION)


@app.post("/verify", response_model=VerifyResponse)
def verify(request: VerifyRequest, empty: bool = False) -> VerifyResponse:
    """Stub. Returns the example response; ignores the request body.

    Pass ?empty=true to get the no-evidence shape instead, so the panel can
    be built against both paths.
    """
    return STUB_NO_EVIDENCE if empty else STUB
