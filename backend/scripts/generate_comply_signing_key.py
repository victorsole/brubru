"""Generate the Ed25519 keypair that signs compliance evidence manifests.

Without a key, a sealed run carries a SHA-256 digest. That detects accident and
a casual edit, but not a party who can also rewrite the stored digest. Signing
is what closes that gap, and it is deliberately off until someone sets a key.

  python3.12 -m scripts.generate_comply_signing_key

Prints a private seed for COMPLY_SIGNING_KEY and the matching public key. Put
the private seed in the environment (Railway variables, .env locally) and NEVER
commit it. Publish the public key: it is what a third party needs to check a
signature, and it is useless for forging one.

Rotating: set a new COMPLY_SIGNING_KEY_ID alongside the new key. Manifests
already sealed keep the old key id, so an old signature stays checkable against
the old public key. Do not reuse an id for a different key.
"""
from __future__ import annotations

import base64
import os
import sys


def main() -> int:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        print("[ERROR] `cryptography` is not installed. It normally arrives with "
              "python-jose[cryptography]; install it before generating a key.")
        return 1

    seed = os.urandom(32)
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)

    print("Ed25519 keypair for EU Law Comply evidence manifests\n")
    print("Private seed. Set this in the environment. Never commit it:\n")
    print(f"  COMPLY_SIGNING_KEY={base64.b64encode(seed).decode()}")
    print(f"  COMPLY_SIGNING_KEY_ID=comply-2026-08\n")
    print("Public key. Safe to publish; a verifier needs it and cannot forge with it:\n")
    print(f"  {base64.b64encode(public).decode()}\n")
    print("Once set, every run sealed afterwards carries a signature. Runs sealed")
    print("before it keep their digest and report signature_present: false, which")
    print("is accurate rather than a failure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
