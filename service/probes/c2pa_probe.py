"""C2PA probe — read Content Credentials from a media file.

Uses the CAI open-source library (`c2pa-python`, bindings to c2pa-rs), which
is what André Paul asked us to build on: FOKUS has no proprietary verification
code, they use the same libraries.

The common case on social media is **no manifest at all** — platforms strip
them on upload. `read_manifest` returns None for that, and that is a normal
result, not an error. Measuring how often it happens on our corpus is itself a
finding for the report.

CLI:
    python -m service.probes.c2pa_probe path/to/file.jpg
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import c2pa
except ImportError:  # pragma: no cover
    c2pa = None  # type: ignore[assignment]


PROBE_NAME = "c2pa"


class C2paUnavailable(RuntimeError):
    """The c2pa library is not installed."""


def read_manifest(path: str | Path) -> dict[str, Any] | None:
    """Read the active C2PA manifest from a file.

    Returns a flat summary dict, or None when the file carries no manifest.

    Raises C2paUnavailable if the library is missing — that is a setup problem
    and should be loud, unlike a missing manifest which is expected.
    """
    if c2pa is None:
        raise C2paUnavailable(
            "c2pa-python is not installed. pip install c2pa-python (needs Python 3.10+)"
        )

    path = Path(path)

    # Check this ourselves. c2pa wraps a missing file in C2paError.Io, which
    # would otherwise be indistinguishable from "this file has no manifest" —
    # and a failed download must not look like media without provenance.
    if not path.is_file():
        raise FileNotFoundError(path)

    try:
        reader = c2pa.Reader(str(path))
    except (c2pa.C2paError.ManifestNotFound, c2pa.C2paError.NotSupported):
        # No JUMBF data, or a format c2pa cannot parse. Both mean: nothing to
        # report for this file. Every other C2paError propagates — a decoding
        # or signature failure is a real problem and should be loud.
        return None

    try:
        report = json.loads(reader.json())
        active_id = report.get("active_manifest")
        manifest = report.get("manifests", {}).get(active_id, {})
        signature = manifest.get("signature_info", {}) or {}

        return {
            "evidence_type": "c2pa_manifest",
            "is_valid": reader.is_valid(),
            "validation_state": str(reader.get_validation_state()),
            "is_embedded": reader.is_embedded(),
            "remote_url": reader.get_remote_url(),
            "claim_generator": manifest.get("claim_generator_info"),
            "title": manifest.get("title"),
            "issuer": signature.get("issuer"),
            "cert_serial_number": signature.get("cert_serial_number"),
            "signed_at": signature.get("time"),
            "assertions": [a.get("label") for a in manifest.get("assertions", [])],
            "ingredients": len(manifest.get("ingredients", []) or []),
        }
    finally:
        try:
            reader.close()
        except Exception:  # pragma: no cover
            pass


def summarise(result: dict[str, Any] | None) -> str:
    """One-line human summary, for the CLI and for logs."""
    if result is None:
        return "no manifest"
    state = "valid" if result["is_valid"] else "INVALID"
    return (
        f"{state} manifest · signed {result['signed_at'] or 'unknown time'} "
        f"by {result['issuer'] or 'unknown issuer'}"
    )


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
