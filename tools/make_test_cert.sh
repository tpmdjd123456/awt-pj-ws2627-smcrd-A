#!/usr/bin/env bash
# Generate a self-signed test certificate chain for signing C2PA fixtures.
#
# STATUS: INCOMPLETE. The chain below is produced correctly, but c2pa-python
# 0.38 rejects it at signing time with:
#
#     C2paError.Signature: internal error (empty string)
#
# c2pa-rs enforces a certificate profile stricter than a plain EC leaf with
# emailProtection EKU. Before sinking more time into openssl, try the test
# certs that ship with c2pa-rs:
#
#     https://github.com/contentauth/c2pa-rs  ->  sdk/tests/fixtures/certs/
#
# Those are known-good (es256.pub / es256.pem) and are what the library's own
# test suite signs with. Point SIGN_CERT and PRIVATE_KEY at them instead.
#
# Reading manifests does not need any of this — service/probes/c2pa_probe.py
# works today. This is only needed to produce a *signed* fixture so the happy
# path can be tested locally.

set -euo pipefail
OUT="${1:-./c2pa-test-certs}"
mkdir -p "$OUT"
cd "$OUT"

# Root CA
openssl ecparam -name prime256v1 -genkey -noout -out ca.key
openssl req -new -x509 -key ca.key -out ca.pem -days 3650 -sha256 \
  -subj "/C=DE/O=AMT PJ Test CA/CN=AMT PJ Test Root" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"

# Leaf, signed by the CA
openssl ecparam -name prime256v1 -genkey -noout -out leaf.key
openssl pkcs8 -topk8 -nocrypt -in leaf.key -out leaf.pkcs8.key   # c2pa wants PKCS#8
openssl req -new -key leaf.key -out leaf.csr \
  -subj "/C=DE/O=TU Berlin/CN=AMT PJ Test Signer"

cat > leaf.ext <<'EXT'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=critical,emailProtection
EXT

openssl x509 -req -in leaf.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
  -out leaf.pem -days 365 -sha256 -extfile leaf.ext

cat leaf.pem ca.pem > chain.pem

echo
echo "Wrote $OUT/chain.pem and $OUT/leaf.pkcs8.key"
echo "Note the STATUS comment at the top of this script before using them."
