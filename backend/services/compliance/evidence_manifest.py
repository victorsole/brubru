"""Turn a compliance run into evidence: what was checked, against what, and when.

Why
---
A compliance report is currently a PDF asserting a score. A regulated client
needs something else: proof of what was actually examined on a given date. "We
checked our supplier policy against the textile EPR package on 10 August and
these were the findings" is only worth anything if the policy, the obligations
and the findings can be shown not to have changed since.

Taken from Mike OSS, which hashes document versions with SHA-256 and can sign
them with Ed25519.

What the manifest fixes in place
--------------------------------
  * the documents, by SHA-256 of the extracted TEXT the analyser actually read,
    not of the original file. The text is what was analysed; a re-saved PDF with
    identical text is the same evidence, and a PDF whose text changed is not.
  * the obligations, by a digest over each requirement's article and text, so a
    later edit to the corpus is visible rather than silently rewriting history.
  * the findings, by a digest over each verdict, its confidence and the evidence
    quoted for it.
  * the package, the run's timestamps, the counts and the score.

`manifest_sha256` covers all of it. If a key is configured the digest is signed,
and the signature is over the digest so a verifier needs only the manifest and
the public key.

Honest limits, stated because a document like this invites over-claiming:
  * This proves INTEGRITY, not correctness. It says the findings are the ones
    produced that day; it does not say they were right.
  * The timestamp is our server's, not a trusted timestamping authority's. It
    shows sequence, not notarised time.
  * Without a configured key the manifest is a checksum, which detects accident
    and casual edits but not a determined party who can also rewrite the stored
    digest. Signing is what closes that, and it is off unless a key is set.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Bumped when the manifest's SHAPE changes, so an old manifest is reported as
# built by a different version rather than failing verification.
MANIFEST_VERSION = 1

# Base64 of a 32-byte Ed25519 seed. Absent means hash-only.
SIGNING_KEY_ENV = "COMPLY_SIGNING_KEY"
SIGNING_KEY_ID_ENV = "COMPLY_SIGNING_KEY_ID"


def canonical_bytes(obj: Any) -> bytes:
    """Deterministic JSON: sorted keys, no incidental whitespace, UTF-8.

    Two runs of the same content must produce the same bytes on any machine, or
    the digest is meaningless.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_text(text: Optional[str]) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def digest_of(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def _load_signing_key():
    """The Ed25519 key, or None. Never raises: signing is optional."""
    raw = os.environ.get(SIGNING_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        seed = base64.b64decode(raw)
        if len(seed) != 32:
            logger.warning(
                f"{SIGNING_KEY_ENV} must decode to 32 bytes, got {len(seed)}; "
                "manifests will be hashed but not signed")
            return None
        return Ed25519PrivateKey.from_private_bytes(seed)
    except Exception as exc:  # noqa: BLE001
        # A broken key must never fail a compliance run. The manifest degrades
        # to hash-only and says so in `signed: false`.
        logger.warning(f"Could not load {SIGNING_KEY_ENV}: {type(exc).__name__}: {exc}")
        return None


def public_key_b64() -> Optional[str]:
    key = _load_signing_key()
    if not key:
        return None
    from cryptography.hazmat.primitives import serialization
    raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def sign_digest(digest_hex: str) -> Tuple[Optional[str], Optional[str]]:
    """(signature_b64, key_id) or (None, None) when no key is configured."""
    key = _load_signing_key()
    if not key:
        return None, None
    sig = key.sign(digest_hex.encode("utf-8"))
    return base64.b64encode(sig).decode(), os.environ.get(SIGNING_KEY_ID_ENV, "default")


def verify_signature(digest_hex: str, signature_b64: str,
                     public_b64: Optional[str] = None) -> bool:
    """Check a signature against a digest using the configured or supplied key."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub_b64 = public_b64 or public_key_b64()
        if not pub_b64:
            return False
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
        pub.verify(base64.b64decode(signature_b64), digest_hex.encode("utf-8"))
        return True
    except Exception:  # noqa: BLE001
        return False


def build_manifest(analysis, cluster, findings_with_reqs, documents) -> Dict[str, Any]:
    """Assemble the manifest from already-loaded rows.

    Takes loaded objects rather than a session so it stays pure and testable,
    and so the caller controls exactly which rows are being attested.

    findings_with_reqs: iterable of (GapFinding, LawRequirement)
    documents:          iterable of UserDocument
    """
    doc_entries: List[Dict[str, Any]] = []
    for d in documents:
        doc_entries.append({
            "id": str(d.id),
            "filename": d.original_filename or d.title,
            "characters": len(d.content or ""),
            "sha256": sha256_text(d.content),
        })
    doc_entries.sort(key=lambda x: x["id"])

    obligations: List[Dict[str, str]] = []
    verdicts: List[Dict[str, Any]] = []
    for finding, req in findings_with_reqs:
        obligations.append({
            "requirement_id": req.id,
            "article": req.article or "",
            "sha256": sha256_text(req.requirement_text),
        })
        verdicts.append({
            "requirement_id": req.id,
            "status": finding.status,
            "confidence": (float(finding.confidence_score)
                           if finding.confidence_score is not None else None),
            "evidence_sha256": sha256_text(finding.evidence_text),
        })
    obligations.sort(key=lambda x: x["requirement_id"])
    verdicts.sort(key=lambda x: x["requirement_id"])

    body = {
        "manifest_version": MANIFEST_VERSION,
        "analysis": {
            "id": analysis.id,
            "started_at": analysis.started_at.isoformat() if analysis.started_at else None,
            "completed_at": (analysis.completed_at.isoformat()
                             if analysis.completed_at else None),
            "status": analysis.status,
            "compliance_score": (float(analysis.compliance_score)
                                 if analysis.compliance_score is not None else None),
            "total_requirements": analysis.total_requirements,
            "coverage": {
                k: (analysis.analysis_params or {}).get(k)
                for k in ("requirements_selected", "requirements_analysed",
                          "failed_requirements", "partial")
            },
        },
        "package": {
            "id": cluster.id if cluster else None,
            "name": cluster.name if cluster else None,
            # The obligation set is what a package IS for evidential purposes,
            # so the package is fixed by the digest of its obligations rather
            # than by a version number nobody maintains.
            "obligations_digest": digest_of(obligations),
            "obligation_count": len(obligations),
        },
        "documents": doc_entries,
        "documents_digest": digest_of(doc_entries),
        "verdicts_digest": digest_of(verdicts),
        # Kept in full so a verifier can recompute without the database.
        "obligations": obligations,
        "verdicts": verdicts,
    }
    return body


def seal(body: Dict[str, Any]) -> Dict[str, Any]:
    """Digest the manifest and sign it if a key is configured."""
    digest = digest_of(body)
    signature, key_id = sign_digest(digest)
    return {
        "manifest": body,
        "manifest_sha256": digest,
        "signature": signature,
        "key_id": key_id,
        "signed": bool(signature),
    }


def verify(stored_manifest: Optional[Dict[str, Any]],
           stored_digest: Optional[str],
           stored_signature: Optional[str],
           rebuilt: Dict[str, Any]) -> Dict[str, Any]:
    """Compare a sealed manifest against the current state of the database.

    Reports each part separately: a changed document and an edited finding are
    different problems and a reader needs to know which happened.
    """
    if not stored_manifest or not stored_digest:
        return {"verified": False, "reason": "no_manifest",
                "detail": "This run was never sealed, so there is nothing to verify."}

    recomputed = digest_of(stored_manifest)
    if recomputed != stored_digest:
        return {"verified": False, "reason": "manifest_altered",
                "detail": "The stored manifest does not match its own recorded digest."}

    checks = {
        "documents_unchanged":
            stored_manifest.get("documents_digest") == rebuilt.get("documents_digest"),
        "obligations_unchanged":
            (stored_manifest.get("package", {}).get("obligations_digest")
             == rebuilt.get("package", {}).get("obligations_digest")),
        "verdicts_unchanged":
            stored_manifest.get("verdicts_digest") == rebuilt.get("verdicts_digest"),
    }

    signature_ok = None
    if stored_signature:
        signature_ok = verify_signature(stored_digest, stored_signature)

    verified = all(checks.values()) and (signature_ok is not False)
    return {
        "verified": verified,
        "checks": checks,
        "signature_present": bool(stored_signature),
        "signature_valid": signature_ok,
        "manifest_sha256": stored_digest,
        "sealed_at": stored_manifest.get("analysis", {}).get("completed_at"),
        "detail": None if verified else
                  "The run no longer matches what was sealed. See `checks` for which part changed.",
    }
