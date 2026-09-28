"""A spent Scrape.do quota must not stop Brubru reading walled documents.

On 28 Sep 2026 the Scrape.do plan (1,000 requests a month) was spent, every call
answered 401 "Monthly request limit exceeded", and for three days no committee
PDF was extracted: the PDF extractor had no route after the paid one. These tests
pin the order (direct, paid, browser), the quota breaker, and that a genuine 404
(listed in eMeeting, not yet published) is never sent round the fallbacks.
"""
import pytest

from services.analysis import pdf_text_extractor as pte
from services.scrapers import scrapedo_quota

PDF = b"%PDF-1.7 fake"


@pytest.fixture(autouse=True)
def _reset_quota():
    scrapedo_quota.reset()
    yield
    scrapedo_quota.reset()


def test_quota_refusal_trips_the_breaker_and_other_failures_do_not():
    assert not scrapedo_quota.note(502, b"ROTATION_FAILED")
    assert not scrapedo_quota.note(401, b"invalid token")
    assert not scrapedo_quota.is_exhausted()
    assert scrapedo_quota.note(401, b'{"Message":["Monthly request limit exceeded."]}')
    assert scrapedo_quota.is_exhausted()


def test_walled_pdf_falls_through_to_the_browser(monkeypatch):
    calls = []
    monkeypatch.setattr(pte, "_direct", lambda u: (None, "HTTP 202, 0 bytes"))
    monkeypatch.setattr(pte, "_via_scrapedo", lambda u: (calls.append("paid"), (None, "Scrape.do: monthly quota spent"))[1])
    monkeypatch.setattr(pte, "_via_browser", lambda urls: {u: (PDF, "browser") for u in urls})
    got = pte.fetch_pdf_bytes_many(["https://x/a.pdf"])
    assert got["https://x/a.pdf"] == (PDF, "browser")
    assert calls == ["paid"]


def test_paid_success_skips_the_browser(monkeypatch):
    monkeypatch.setattr(pte, "_direct", lambda u: (None, "HTTP 202, 0 bytes"))
    monkeypatch.setattr(pte, "_via_scrapedo", lambda u: (PDF, "scrapedo"))
    monkeypatch.setattr(pte, "_via_browser", lambda urls: pytest.fail("browser must not run"))
    assert pte.fetch_pdf_bytes_many(["https://x/a.pdf"])["https://x/a.pdf"] == (PDF, "scrapedo")


def test_genuine_404_goes_nowhere_else(monkeypatch):
    monkeypatch.setattr(pte, "_direct", lambda u: (None, "HTTP 404"))
    monkeypatch.setattr(pte, "_via_scrapedo", lambda u: pytest.fail("paid tier must not run on a 404"))
    monkeypatch.setattr(pte, "_via_browser", lambda urls: pytest.fail("browser must not run on a 404"))
    raw, why = pte.fetch_pdf_bytes_many(["https://x/a.pdf"])["https://x/a.pdf"]
    assert raw is None and why == "HTTP 404"


def test_one_browser_for_many_documents(monkeypatch):
    batches = []
    monkeypatch.setattr(pte, "_direct", lambda u: (None, "HTTP 202, 0 bytes"))
    monkeypatch.setattr(pte, "_via_scrapedo", lambda u: (None, "Scrape.do: no key"))
    monkeypatch.setattr(pte, "_via_browser",
                        lambda urls: (batches.append(list(urls)), {u: (PDF, "browser") for u in urls})[1])
    urls = [f"https://x/{i}.pdf" for i in range(4)]
    got = pte.fetch_pdf_bytes_many(urls)
    assert batches == [urls]
    assert all(v == (PDF, "browser") for v in got.values())


def test_spent_quota_is_not_asked_again(monkeypatch):
    monkeypatch.setenv("SCRAPEDO_API_KEY", "k")
    scrapedo_quota.note(401, b"Monthly request limit exceeded")

    class Boom:
        def __init__(self, *a, **k):
            pytest.fail("Scrape.do must not be called once the quota is spent")

    monkeypatch.setattr(pte.httpx, "Client", Boom)
    raw, why = pte._via_scrapedo("https://x/a.pdf")
    assert raw is None and "quota" in why


def test_browser_body_that_is_not_a_pdf_is_refused(monkeypatch):
    import services.scrapers.waf_browser_fetcher as wbf
    monkeypatch.setattr(wbf, "fetch_bytes_isolated",
                        lambda urls, **k: {u: (200, b"<html>Just a moment...</html>", None) for u in urls})
    raw, why = pte._via_browser(["https://x/a.pdf"])["https://x/a.pdf"]
    assert raw is None and "not a PDF" in why
