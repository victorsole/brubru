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


# --- who counts as institutional ---------------------------------------------------------

def test_a_spoofed_host_is_not_institutional():
    """The check decides whose text Brubru will fetch and store. It must test the HOST.

    It was `any(domain in url)`, a substring test over the whole URL, so
    `https://europa.eu.evil.com/a` passed, and so did any URL with the string anywhere in its
    path or query. An attacker-controlled host reading as an EU institution is how third-party
    content gets stored and served as official.
    """
    import fetch_institutional_news_bodies as fetcher

    for url in ("https://europa.eu.evil.com/a",
                "https://notepthinktank.eu.evil.com/a",
                "https://evil.com/?redirect=https://europa.eu/a",
                "https://europa.eu.attacker.test/news",
                "https://notepthinktank.eu/a",
                "https://www.politico.eu/article"):
        assert not fetcher.is_institutional(url), f"{url} must not read as institutional"


def test_the_real_institutions_still_pass():
    import fetch_institutional_news_bodies as fetcher

    for url in ("https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1129",
                "https://www.europarl.europa.eu/news/en/x",
                "https://www.consilium.europa.eu/en/press/x",
                "https://epthinktank.eu/2026/02/24/x/",
                "https://www.ecb.int/press/x"):
        assert fetcher.is_institutional(url), f"{url} is institutional and must pass"


def test_epthinktank_is_the_parliaments_own_site():
    """Verified 25 September 2026: epthinktank.eu/about is titled
    "About | Epthinktank | European Parliament" and describes EPRS as the Parliament's
    research service. It is in the list on that evidence, not on the strength of its name.
    """
    import fetch_institutional_news_bodies as fetcher

    assert "epthinktank.eu" in fetcher.INSTITUTIONAL


# --- navigation prefixes ------------------------------------------------------------------

def test_a_navigation_prefix_is_stripped_not_the_whole_article():
    """110 rows opened with navigation and then carried a real article.

    Refusing them throws away genuine bodies; storing them whole puts "Skip to main content
    Highlights Back to highlights" into the text a partner searches. Strip the run, then judge
    what is left.
    """
    from services.news.rendered_article import strip_page_furniture

    osha = ("Skip to main content Highlights Back to highlights 14/12/2025 "
            "Together for a safer and healthier 2026. " + "The campaign continues. " * 20)
    cleaned = strip_page_furniture(osha)
    assert "Skip to main content" not in cleaned
    assert "Together for a safer" in cleaned
    assert len(cleaned) > 400, "the article itself must survive"


def test_a_leading_close_button_does_not_hide_the_furniture():
    """EUR-Lex opens with "x Skip to main content"; startswith missed it by one character,
    so 3,178 characters of portal navigation read as an article."""
    from services.news.rendered_article import looks_like_chrome

    assert looks_like_chrome("× Skip to main content EUR-Lex Access to European Union law")
    assert looks_like_chrome("  ✕ This site uses cookies. Visit our policy page.")
    assert not looks_like_chrome("X-ray screening and skip counts are covered in the report.")


def test_an_article_that_merely_mentions_skipping_is_untouched():
    from services.news.rendered_article import strip_page_furniture

    real = "The Commission adopted new rules today, skipping the usual consultation."
    assert strip_page_furniture(real) == real


def test_no_stored_body_still_opens_with_navigation():
    """The corpus: 110 rows did before this ran; what remains was too short to keep."""
    import psycopg2

    dsn = next((l.split("=", 1)[1].strip() for l in pathlib.Path(_BACKEND, ".env").read_text().splitlines()
                if l.startswith("DATABASE_URL=")), None)
    if not dsn:
        pytest.skip("no DATABASE_URL")
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute("SET statement_timeout='90s'")
        for table in ("economy_items", "eu_news_items"):
            cur.execute(f"SELECT count(*) FROM {table} "
                        f"WHERE left(body_txt, 60) ~* '(skip to main content|skip to content)' "
                        f"  AND length(body_txt) >= 200")
            count = cur.fetchone()[0]
            assert count == 0, f"{count} substantial row(s) in {table} still open with navigation"
    finally:
        conn.close()
