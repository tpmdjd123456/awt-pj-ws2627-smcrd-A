"""C2PA probe — read Content Credentials from media.

Uses the CAI open-source library (`c2pa-python`, bindings to c2pa-rs), which
is what André Paul asked us to build on: FOKUS has no proprietary verification
code, they use the same libraries.

The common case on social media is **no manifest at all** — platforms strip
them on upload. Both entry points return None for that, and that is a normal
result, not an error. Measuring how often it happens across our corpus is
itself a finding for the report.

`read_manifest_bytes` is the one the service uses: media arrives from a
download, in memory, never as a file on disk. `read_manifest` is a thin
convenience wrapper for the CLI and for tests.

CLI:
    python -m service.probes.c2pa_probe path/to/file.jpg
"""

from __future__ import annotations

import io
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

try:
    import c2pa
except ImportError:  # pragma: no cover
    c2pa = None  # type: ignore[assignment]


PROBE_NAME = "c2pa"

DEFAULT_MIME = "image/jpeg"


class C2paUnavailable(RuntimeError):
    """The c2pa library is not installed."""


def _require_c2pa() -> None:
    if c2pa is None:
        raise C2paUnavailable(
            "c2pa-python is not installed. pip install c2pa-python (needs Python 3.10+)"
        )


def read_manifest_bytes(data: bytes, mime_type: str = DEFAULT_MIME) -> dict[str, Any] | None:
    """Read the active C2PA manifest from media held in memory.

    Returns a flat summary dict, or None when the media carries no manifest
    or c2pa cannot parse the format.

    Raises C2paUnavailable if the library is missing — a setup problem, which
    should be loud, unlike a missing manifest which is expected.
    """
    _require_c2pa()

    try:
        reader = c2pa.Reader(mime_type, io.BytesIO(data))
    except (c2pa.C2paError.ManifestNotFound, c2pa.C2paError.NotSupported):
        # No JUMBF data, or a format c2pa cannot parse. Nothing to report.
        # Every other C2paError propagates: a decoding or signature failure
        # is a real problem and must not be silently swallowed.
        return None

    try:
        report = json.loads(reader.json())
        active_id = report.get("active_manifest")
        manifest = report.get("manifests", {}).get(active_id, {}) or {}
        signature = manifest.get("signature_info") or {}

        return {
            "evidence_type": "c2pa_manifest",
            # NB: is_valid is a property on Reader; everything else is a method.
            "is_valid": reader.is_valid,
            "validation_state": str(reader.get_validation_state()),
            "is_embedded": reader.is_embedded(),
            "remote_url": reader.get_remote_url(),
            "manifest_id": active_id,
            "title": manifest.get("title"),
            "claim_generator": manifest.get("claim_generator_info"),
            "issuer": signature.get("issuer"),
            "common_name": signature.get("common_name"),
            "signature_alg": signature.get("alg"),
            "cert_serial_number": signature.get("cert_serial_number"),
            # Only present when the signature carries a trusted timestamp.
            # Absent is normal and does not mean the manifest is invalid.
            "signed_at": signature.get("time"),
            "assertions": [a.get("label") for a in manifest.get("assertions", [])],
            "ingredients": len(manifest.get("ingredients") or []),
        }
    finally:
        try:
            reader.close()
        except Exception:  # pragma: no cover
            pass


def read_manifest(path: str | Path) -> dict[str, Any] | None:
    """Read the active C2PA manifest from a file on disk.

    Convenience wrapper around read_manifest_bytes. Raises FileNotFoundError
    for a missing path — c2pa would otherwise wrap that in its own error and
    it would be indistinguishable from "no manifest", which would make a
    failed download look like media without provenance.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    mime = mimetypes.guess_type(path.name)[0] or DEFAULT_MIME
    return read_manifest_bytes(path.read_bytes(), mime)


def summarise(result: dict[str, Any] | None) -> str:
    """One-line human summary, for the CLI and for logs."""
    if result is None:
        return "no manifest"
    state = "valid" if result["is_valid"] else "INVALID"
    when = result["signed_at"] or "no trusted timestamp"
    who = result["common_name"] or result["issuer"] or "unknown signer"
    return f"{state} manifest · {who} · {when}"


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    target = argv[1]
    try:
        result = read_manifest(target)
    except C2paUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"error: no such file: {target}", file=sys.stderr)
        return 1

    if result is None:
        print(f"{target}: no C2PA manifest found.")
        print(
            "  Expected for anything downloaded from social media — platforms\n"
            "  strip manifests on upload. Not a bug."
        )
        return 0

    print(f"{target}: {summarise(result)}")
    print()
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
