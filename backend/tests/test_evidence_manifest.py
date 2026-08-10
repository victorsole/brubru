"""Evidence manifest: does the seal actually detect a change?

A tamper-evident feature that does not detect tampering is worse than none,
because it invites reliance. Every test here changes exactly one thing and
insists the right check fails and the others do not.

Run: python3.12 -m pytest tests/test_evidence_manifest.py -q
"""
from __future__ import annotations

import base64
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.compliance.evidence_manifest import (  # noqa: E402
    build_manifest, canonical_bytes, digest_of, public_key_b64, seal,
    sha256_text, sign_digest, verify, verify_signature,
)


def analysis(**kw):
    base = dict(
        id=1, started_at=datetime(2026, 8, 10, 9, 0), completed_at=datetime(2026, 8, 10, 9, 5),
        status="completed", compliance_score=42.5, total_requirements=10,
        analysis_params={"requirements_selected": 12, "requirements_analysed": 12,
                         "failed_requirements": 0, "partial": False},
    )
    base.update(kw)
    return SimpleNamespace(**base)


def cluster(**kw):
    base = dict(id=58, name="Textiles: EPR, Ecodesign and DPP")
    base.update(kw)
    return SimpleNamespace(**base)


def req(rid=1, article="Article 4", text="Register the product passport."):
    return SimpleNamespace(id=rid, article=article, requirement_text=text)


def finding(status="gap", confidence=80.0, evidence="Section 3 says nothing."):
    return SimpleNamespace(status=status, confidence_score=confidence, evidence_text=evidence)


def doc(did="a1", filename="policy.txt", content="Our textile policy."):
    return SimpleNamespace(id=did, original_filename=filename, title=filename, content=content)


def full():
    return build_manifest(analysis(), cluster(),
                          [(finding(), req(1)), (finding("met", 95.0, "Section 4 covers it."), req(2, "Article 5", "Keep records."))],
                          [doc(), doc("b2", "annex.txt", "Annex content.")])


# ------------------------------------------------------------- determinism

def test_canonical_bytes_are_order_independent():
    assert canonical_bytes({"b": 1, "a": 2}) == canonical_bytes({"a": 2, "b": 1})


def test_same_content_gives_same_digest():
    assert digest_of(full()) == digest_of(full())


def test_document_order_does_not_change_the_digest():
    """Rows come back in whatever order the database chose."""
    a = build_manifest(analysis(), cluster(), [(finding(), req(1))], [doc(), doc("b2")])
    b = build_manifest(analysis(), cluster(), [(finding(), req(1))], [doc("b2"), doc()])
    assert a["documents_digest"] == b["documents_digest"]


def test_finding_order_does_not_change_the_digest():
    f1, f2 = (finding(), req(1)), (finding("met"), req(2))
    a = build_manifest(analysis(), cluster(), [f1, f2], [doc()])
    b = build_manifest(analysis(), cluster(), [f2, f1], [doc()])
    assert a["verdicts_digest"] == b["verdicts_digest"]


def test_hash_is_of_extracted_text_not_the_file():
    """The text is what was analysed. Same text, different filename, same hash."""
    a = build_manifest(analysis(), cluster(), [(finding(), req(1))], [doc(filename="a.pdf")])
    b = build_manifest(analysis(), cluster(), [(finding(), req(1))], [doc(filename="b.docx")])
    assert a["documents"][0]["sha256"] == b["documents"][0]["sha256"]


# ------------------------------------------------------------- verification

def test_untouched_run_verifies():
    sealed = seal(full())
    result = verify(sealed["manifest"], sealed["manifest_sha256"], sealed["signature"], full())
    assert result["verified"], result
    assert all(result["checks"].values())


def test_changed_document_is_caught():
    sealed = seal(full())
    tampered = build_manifest(
        analysis(), cluster(),
        [(finding(), req(1)), (finding("met", 95.0, "Section 4 covers it."), req(2, "Article 5", "Keep records."))],
        [doc(content="Our textile policy, quietly rewritten."), doc("b2", "annex.txt", "Annex content.")])
    result = verify(sealed["manifest"], sealed["manifest_sha256"], sealed["signature"], tampered)
    assert not result["verified"]
    assert result["checks"]["documents_unchanged"] is False
    assert result["checks"]["verdicts_unchanged"] is True


def test_edited_verdict_is_caught():
    sealed = seal(full())
    tampered = build_manifest(
        analysis(), cluster(),
        [(finding("met"), req(1)), (finding("met", 95.0, "Section 4 covers it."), req(2, "Article 5", "Keep records."))],
        [doc(), doc("b2", "annex.txt", "Annex content.")])
    result = verify(sealed["manifest"], sealed["manifest_sha256"], sealed["signature"], tampered)
    assert not result["verified"]
    assert result["checks"]["verdicts_unchanged"] is False
    assert result["checks"]["documents_unchanged"] is True


def test_rewritten_obligation_is_caught():
    """A later edit to the corpus must not silently rewrite history."""
    sealed = seal(full())
    tampered = build_manifest(
        analysis(), cluster(),
        [(finding(), req(1, text="Register the product passport, or do not.")),
         (finding("met", 95.0, "Section 4 covers it."), req(2, "Article 5", "Keep records."))],
        [doc(), doc("b2", "annex.txt", "Annex content.")])
    result = verify(sealed["manifest"], sealed["manifest_sha256"], sealed["signature"], tampered)
    assert not result["verified"]
    assert result["checks"]["obligations_unchanged"] is False


def test_altered_manifest_body_is_caught():
    """Editing the stored manifest without recomputing its digest."""
    sealed = seal(full())
    body = dict(sealed["manifest"])
    body["analysis"] = {**body["analysis"], "compliance_score": 99.9}
    result = verify(body, sealed["manifest_sha256"], sealed["signature"], full())
    assert not result["verified"]
    assert result["reason"] == "manifest_altered"


def test_unsealed_run_reports_itself_as_unverifiable():
    result = verify(None, None, None, full())
    assert result["verified"] is False
    assert result["reason"] == "no_manifest"


# ---------------------------------------------------------------- signing

def test_no_key_means_hash_only_and_never_raises(monkeypatch):
    monkeypatch.delenv("COMPLY_SIGNING_KEY", raising=False)
    sealed = seal(full())
    assert sealed["signed"] is False
    assert sealed["signature"] is None
    assert len(sealed["manifest_sha256"]) == 64
    assert public_key_b64() is None


def test_broken_key_degrades_rather_than_failing_the_run(monkeypatch):
    monkeypatch.setenv("COMPLY_SIGNING_KEY", "not-base64-at-all!!")
    sealed = seal(full())
    assert sealed["signed"] is False

    monkeypatch.setenv("COMPLY_SIGNING_KEY", base64.b64encode(b"tooshort").decode())
    assert seal(full())["signed"] is False


def test_signature_round_trip(monkeypatch):
    monkeypatch.setenv("COMPLY_SIGNING_KEY", base64.b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("COMPLY_SIGNING_KEY_ID", "test-key")
    sealed = seal(full())
    assert sealed["signed"] is True
    assert sealed["key_id"] == "test-key"
    assert verify_signature(sealed["manifest_sha256"], sealed["signature"])
    # A signature over a different digest must not validate.
    assert not verify_signature("0" * 64, sealed["signature"])


def test_signature_from_another_key_is_rejected(monkeypatch):
    monkeypatch.setenv("COMPLY_SIGNING_KEY", base64.b64encode(os.urandom(32)).decode())
    sealed = seal(full())
    monkeypatch.setenv("COMPLY_SIGNING_KEY", base64.b64encode(os.urandom(32)).decode())
    assert verify_signature(sealed["manifest_sha256"], sealed["signature"]) is False


def test_verify_reports_invalid_signature(monkeypatch):
    monkeypatch.setenv("COMPLY_SIGNING_KEY", base64.b64encode(os.urandom(32)).decode())
    sealed = seal(full())
    monkeypatch.setenv("COMPLY_SIGNING_KEY", base64.b64encode(os.urandom(32)).decode())
    result = verify(sealed["manifest"], sealed["manifest_sha256"], sealed["signature"], full())
    assert result["signature_valid"] is False
    assert result["verified"] is False


def test_sha256_text_handles_none():
    assert sha256_text(None) == sha256_text("")
