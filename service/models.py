"""Request and response models for the verification service.

These mirror docs/api.md exactly. FastAPI generates the OpenAPI schema from
them, so http://localhost:8000/docs is always in step with this file.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    """Where a piece of evidence came from."""

    c2pa_manifest = "c2pa_manifest"
    hash_match = "hash_match"
    reverse_search = "reverse_search"
    factcheck = "factcheck"
    publisher_caption = "publisher_caption"


class ConfidenceTier(str, Enum):
    """How strongly the evidence supports the answer.

    verified_origin  - valid C2PA manifest, signature chain trusted
    strong_match     - hash distance under threshold to an indexed original
    candidate_match  - reverse-search hit only, no hash confirmation
    no_evidence      - nothing recovered by any probe
    """

    verified_origin = "verified_origin"
    strong_match = "strong_match"
    candidate_match = "candidate_match"
    no_evidence = "no_evidence"


class VerifyRequest(BaseModel):
    media_url: str = Field(..., description="Direct URL of the image or video")
    post_url: str | None = Field(None, description="Permalink of the post")
    post_caption: str | None = Field(
        None,
        description=(
            "The post's own text. Compared against the recovered original "
            "claim — that comparison is what exposes the reuse."
        ),
    )
    post_date: str | None = Field(None, description="ISO 8601, from <time datetime>")
    post_author: str | None = None
    platform: str | None = None


class Appearance(BaseModel):
    """One place this media was found. A retrieval result, nothing more.

    Says nothing about whether the claim attached to it is true.
    """

    date: str | None = None
    source: str | None = None
    url: str | None = None
    caption: str | None = None
    evidence_type: EvidenceType
    distance: int | None = Field(
        None, description="Perceptual hash distance, when evidence_type is hash_match"
    )


class AttestedContext(BaseModel):
    """What the media actually shows.

    Only ever populated from a fact-check record, a valid C2PA manifest, or
    the earliest credible publisher's own caption. Never inferred from
    earliest_known_appearance — see docs/terminology.md.
    """

    description: str
    date: str | None = None
    location: str | None = None
    source: str
    url: str | None = None
    evidence_type: EvidenceType


class VerifyResponse(BaseModel):
    query_id: str
    media_sha256: str | None = None

    earliest_known_appearance: Appearance | None = None
    candidates: list[Appearance] = []
    attested_context: AttestedContext | None = None

    confidence_tier: ConfidenceTier
    probes_run: list[str] = []
    probes_failed: list[str] = Field(
        default=[],
        description=(
            "Probes that could not run. Not an error: a missing API key "
            "lowers confidence, it does not break the response."
        ),
    )
    elapsed_ms: int = 0


class Health(BaseModel):
    ok: bool
    version: str
