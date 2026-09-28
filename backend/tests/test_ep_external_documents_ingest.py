"""The follow-up ingest must not invent anything, and must not read a refusal as absence.

Both failure modes are ones this repo has already paid for. rsb_opinions stored a date
parsed out of a filename for all 44 rows; several jobs recorded EP's 429 or its
200-with-an-error-body as "there is nothing here". The identifiers here make the first
especially tempting: SP-2026-04-14-TA-10-2025-0343 contains a date, and using it would
produce numbers that look right and are fabricated.
"""
import importlib.util
import pathlib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ingest_extdocs", BACKEND / "scripts" / "ingest_ep_external_documents.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class _Resp:
    def __init__(self, payload=None, status_code=200, headers=None, text=""):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _Client:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, params=None):
        self.calls += 1
        return self._responses[min(self.calls - 1, len(self._responses) - 1)]


def test_an_error_body_is_retried_then_raises(monkeypatch):
    """200 with an `error` key and no `data` is a fault, never an empty year."""
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    c = _Client([_Resp({"@id": "x", "error": "404 Not Found from POST admin.data..."})])
    with pytest.raises(mod.EPBlocked):
        mod._get(c, "http://x", {"year": 2026})
    assert c.calls == 4, "a fault deserves retries before it is called a fault"


def test_a_429_honours_retry_after_then_raises(monkeypatch):
    slept = []
    monkeypatch.setattr(mod.time, "sleep", lambda s: slept.append(s))
    c = _Client([_Resp(None, status_code=429, headers={"Retry-After": "7"})])
    with pytest.raises(mod.EPBlocked):
        mod._get(c, "http://x", {"year": 2026})
    assert slept and all(s >= 5 for s in slept), "Retry-After must be honoured, with a floor"


def test_a_404_is_a_genuine_absence():
    c = _Client([_Resp(None, status_code=404)])
    assert mod._get(c, "http://x", {}) is None


def test_a_real_payload_comes_back():
    c = _Client([_Resp({"data": [{"identifier": "SP-2026-04-14-TA-10-2025-0343"}]})])
    got = mod._get(c, "http://x", {})
    assert got["data"][0]["identifier"] == "SP-2026-04-14-TA-10-2025-0343"


def test_the_docx_extractor_keeps_line_breaks():
    """<w:cr/> is how EP documents break a line; dropping it fuses the words."""
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml",
                   '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
                   '<w:p><w:r><w:t>Vice-President Fitto</w:t></w:r>'
                   '<w:r><w:cr/><w:t>on behalf of the Commission</w:t></w:r></w:p>'
                   "</w:body></w:document>")
    out = mod._docx_text(buf.getvalue())
    assert "Fittoon" not in out
    assert "Vice-President Fitto" in out and "on behalf of the Commission" in out


def test_a_non_docx_yields_nothing_rather_than_garbage():
    assert mod._docx_text(b"%PDF-1.7 not a docx at all") is None


def test_the_english_manifestation_is_chosen():
    rec = {"is_realized_by": [{"is_embodied_by": [
        {"is_exemplified_by": "distribution/doc/SP-1_fr.docx"},
        {"is_exemplified_by": "distribution/doc/SP-1_en.docx"},
        {"is_exemplified_by": "distribution/doc/SP-1_en.pdf"}]}]}
    assert mod._en_docx(rec).endswith("SP-1_en.docx")


def test_no_manifestation_gives_no_url():
    assert mod._en_docx({"is_realized_by": []}) is None


def test_a_language_map_label_prefers_english():
    assert mod._label({"fr": "Suivi", "en": "Follow up"}) == "Follow up"
    assert mod._label({"fr": "Suivi"}) == "Suivi"
    assert mod._label(None) is None
