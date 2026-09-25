"""A bot-verification page is not an article, and must never be stored as one.

Cedefop answers HTTP 200 with "Due to unusually high traffic, we need to verify that requests
are coming from real users" and an arithmetic puzzle. The extractors read that as a short
document and stored it: on 25 September 2026, 505 economy rows and 50 news rows were serving a
challenge page as the body of an article. Cleared, backed up, and guarded here.

Brubru never solves such a challenge. It detects one, refuses to store it, and backs off.
"""
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_BACKEND = str(pathlib.Path(__file__).resolve().parents[1])
for _p in (_BACKEND, str(pathlib.Path(_BACKEND, "scripts"))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from services.news.rendered_article import extract_article, looks_like_challenge  # noqa: E402

CEDEFOP = ("Cedefop Webportal www.cedefop.europa.eu Due to unusually high traffic, we need to "
           "verify that requests are coming from real users. Please complete the verification "
           "below to continue. 9 9 8 + 1 1 3 7 6")


@pytest.mark.parametrize("text", [
    CEDEFOP,
    "Checking your browser before accessing the site.",
    "Please enable JavaScript and cookies to continue.",
    "Access denied. Cloudflare Ray ID: 8f2c",
])
def test_challenge_pages_are_recognised(text):
    assert looks_like_challenge(text)


@pytest.mark.parametrize("text", [
    "The Commission adopted new rules on vocational training today.",
    "The Court held that the verification of professional qualifications was proportionate.",
    "",
])
def test_real_documents_are_not_mistaken_for_challenges(text):
    assert not looks_like_challenge(text)


def test_the_extractor_refuses_a_challenge_page():
    page = f"<html><body><div class='ecl-col-12'><p>{CEDEFOP}</p></div></body></html>"
    text, _, reason = extract_article(page)
    assert text is None, "a challenge page was accepted as an article"
    assert "challenge" in (reason or "").lower()


def test_the_fetcher_refuses_a_challenge_page(monkeypatch):
    """The economy extractor path is the one that stored 555 of them."""
    import fetch_institutional_news_bodies as fetcher

    monkeypatch.setattr(fetcher, "_read",
                        lambda url, timeout, accept="*/*": f"<html><body>{CEDEFOP}</body></html>".encode())
    body_txt, body_html, reason = fetcher.fetch("https://www.cedefop.europa.eu/en/news/x")
    assert body_txt is None and body_html is None
    assert "challenge" in (reason or "").lower(), f"reason was {reason!r}"


def test_no_stored_body_is_a_challenge_page():
    """The corpus itself, not just the code path. 555 rows held one before this ran."""
    import psycopg2

    dsn = next((l.split("=", 1)[1].strip() for l in pathlib.Path(_BACKEND, ".env").read_text().splitlines()
                if l.startswith("DATABASE_URL=")), None)
    if not dsn:
        pytest.skip("no DATABASE_URL")
    pattern = ("(unusually high traffic|verify that requests are coming from real users"
               "|complete the verification below|enable javascript and cookies to continue"
               "|checking your browser)")
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        for table in ("economy_items", "eu_news_items"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE body_txt ~* %s", (pattern,))
            count = cur.fetchone()[0]
            assert count == 0, f"{count} row(s) in {table} serve a bot challenge as an article"
    finally:
        conn.close()


# --- PDF bytes are not text -------------------------------------------------------------

def test_pdf_bytes_are_never_stored_as_a_body(monkeypatch):
    """A direct PDF link decoded as UTF-8 is long, and looks like text to every length check.

    118 CJEU press releases and 17 ECB documents held "%PDF-1.7 %... 1 0 obj </Metadata" as
    their article, one ECB row at 623,585 characters of it.
    """
    import fetch_institutional_news_bodies as fetcher

    fake_pdf = b"%PDF-1.7\n%\xc3\xa3\xcf\xd3\n1 0 obj <</Metadata 142 0 R>> endobj\n%%EOF"
    monkeypatch.setattr(fetcher, "_read", lambda url, timeout, accept="*/*": fake_pdf)
    body_txt, body_html, reason = fetcher.fetch("https://curia.europa.eu/docs/cp260037en.pdf")
    assert body_txt is None, "raw PDF bytes were accepted as an article"
    assert "pdf" in (reason or "").lower()


def test_a_readable_pdf_is_parsed_not_refused(monkeypatch):
    """The point is to READ the document, not to drop every PDF."""
    import fetch_institutional_news_bodies as fetcher

    monkeypatch.setattr(fetcher, "_read", lambda url, timeout, accept="*/*": b"%PDF-1.7 fake")
    monkeypatch.setattr(fetcher, "_pdf_text",
                        lambda raw: "PRESS RELEASE No 37/26 Luxembourg, 17 March 2026. " * 10)
    body_txt, _, reason = fetcher.fetch("https://curia.europa.eu/docs/cp260037en.pdf")
    assert reason is None and body_txt.startswith("PRESS RELEASE")


def test_looks_like_pdf_does_not_fire_on_html():
    import fetch_institutional_news_bodies as fetcher

    assert fetcher.looks_like_pdf(b"%PDF-1.7\n...")
    assert not fetcher.looks_like_pdf(b"<html><body><p>The Commission adopted</p></body></html>")


def test_no_stored_body_is_raw_pdf():
    """The corpus, not the code path: 135 rows held one before this ran."""
    import psycopg2

    dsn = next((l.split("=", 1)[1].strip() for l in pathlib.Path(_BACKEND, ".env").read_text().splitlines()
                if l.startswith("DATABASE_URL=")), None)
    if not dsn:
        pytest.skip("no DATABASE_URL")
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute("SET statement_timeout='90s'")
        for table in ("eu_news_items", "economy_items", "eu_general_publications"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE left(body_txt, 8) LIKE %s", ("%PDF-%",))
            count = cur.fetchone()[0]
            assert count == 0, f"{count} row(s) in {table} hold raw PDF bytes as their body"
    finally:
        conn.close()
