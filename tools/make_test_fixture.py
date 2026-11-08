#!/usr/bin/env python3
"""Sign an image with a C2PA manifest, to produce a test fixture.

We need signed media to test the *happy* path of service/probes/c2pa_probe.py.
Real social media posts have had their manifests stripped, so they only ever
exercise the "no manifest" branch.

    python tools/make_test_fixture.py input.jpg tests/fixtures/signed.jpg

Uses the public test certificates from c2pa-rs, which are marked
FOR TESTING_ONLY and are what the library's own test suite signs with. They
are downloaded on first run and cached next to this script.

Two things cost an hour each to discover; both are handled below.

1.  ta_url must be None, not b"".
    An empty bytestring makes c2pa attempt a timestamp-authority call that
    fails with the useless message:
        C2paError.Signature: internal error (empty string)
    This looks exactly like a bad certificate, and sends you off generating
    certs with openssl for no reason. It is not the certificate.

2.  A c2pa.created action must carry a digitalSourceType.
    Without it, signing succeeds and then validation fails with:
        assertion.action.malformed: c2pa.created action must have a
        digitalSourceType
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import c2pa

CERT_BASE = (
    "https://raw.githubusercontent.com/contentauth/c2pa-rs/main/sdk/tests/fixtures/certs"
)
CACHE = Path(__file__).parent / ".c2pa-test-certs"


def fetch_certs() -> tuple[bytes, bytes]:
    """Download (and cache) the c2pa-rs public test cert chain and key."""
    CACHE.mkdir(exist_ok=True)
    out = []
    for name in ("es256.pub", "es256.pem"):
        dest = CACHE / name
        if not dest.exists():
            print(f"fetching {name} …")
            urllib.request.urlretrieve(f"{CERT_BASE}/{name}", dest)
        out.append(dest.read_bytes())
    return out[0], out[1]


def sign(src: Path, dest: Path) -> None:
    cert_chain, private_key = fetch_certs()

    manifest = {
        "claim_generator_info": [
            {"name": "awt-pj-ws2627-smcrd-A", "version": "0.1.0"}
        ],
        "title": src.name,
        "assertions": [
            {
                "label": "c2pa.actions",
                "data": {
                    "actions": [
                        {
                            "action": "c2pa.created",
                            # Required — see gotcha 2 in the module docstring.
                            "digitalSourceType": (
                                "http://cv.iptc.org/newscodes/"
                                "digitalsourcetype/digitalCapture"
                            ),
                        }
                    ]
                },
            },
            {
                "label": "stds.schema-org.CreativeWork",
                "data": {
                    "@context": "https://schema.org",
                    "@type": "CreativeWork",
                    "author": [{"@type": "Person", "name": "AMT PJ test fixture"}],
                },
            },
        ],
    }

    signer = c2pa.Signer.from_info(
        c2pa.C2paSignerInfo(
            alg=b"es256",
            sign_cert=cert_chain,
            private_key=private_key,
            ta_url=None,  # NOT b"" — see gotcha 1 in the module docstring.
        )
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    c2pa.Builder(manifest).sign_file(str(src), str(dest), signer)
    print(f"signed {src} -> {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    sign(Path(sys.argv[1]), Path(sys.argv[2]))
