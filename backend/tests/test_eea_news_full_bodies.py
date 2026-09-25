"""EEA news served a 375-character teaser and an address nobody could open.

GovClipping need the whole text in body_txt and the whole HTML in body_html, especially
on news and publications (Victor, 25 September 2026).

Three faults, found together:

1. The EEA's RSS feed published its internal load-balancer address in <link>
   (`http://10.140.139.135:3000/en/newsroom/news/...`), and a different IP each run. Every
   public_url we served for EEA news was unopenable.
2. Identity is per URL, so each run inserted the same article again: 534 rows held 60
   articles, 19 copies of some. (`same_story.py`, 15 Sep, already closes this by title and
   date; the newest duplicate predates it by a week.)
3. The bodies were composed from the title and the RSS summary, averaging 540 characters.
   /api/v2/news/all unions economy_items with eu_news_items and PREFERS economy_items, so
   fixing the institutional table alone changed nothing a caller could see.

Now: 348 EEA rows carry the fetched article, averaging 7,417 characters against 540.

Needs the database.
"""
from __future__ import annotations

import pathlib
import sys

import pytest
from sqlalchemy import text

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.database import SessionLocal  # noqa: E402


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_no_eea_news_url_points_at_a_private_address(db):
    """A public_url on 10.x resolves for nobody outside the EEA's own network."""
    for table, col in (("eu_news_items", "source_url"), ("economy_items", "public_url")):
        n = db.execute(text(
            f"SELECT count(*) FROM {table} WHERE {col} ~ "
            f"'^https?://(10\\.|192\\.168\\.|127\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.)'")).scalar()
        assert n == 0, f"{n} row(s) in {table} still serve a private address"


def test_one_row_per_eea_article(db):
    n, distinct = db.execute(text(
        "SELECT count(*), count(DISTINCT source_url) FROM eu_news_items "
        "WHERE institution = 'EEA'")).fetchone()
    assert n == distinct, f"{n} EEA rows for {distinct} distinct articles"


def test_eea_news_carries_the_whole_article(db):
    """The table /api/v2/news/all actually serves. 490 characters was the teaser."""
    n, avg, whole = db.execute(text(
        "SELECT count(*), coalesce(round(avg(nullif(length(body_txt),0))),0), "
        "       count(*) FILTER (WHERE length(body_txt) >= 1200) "
        "FROM economy_items WHERE body_code = 'eea' "
        "  AND item_type IN ('news','environmental_indicator','event')")).fetchone()
    assert n > 300, f"only {n} EEA rows"
    assert avg > 3000, f"average body is {avg} characters: still a teaser"
    assert whole / n > 0.9, f"only {whole} of {n} are of document length"


def test_eea_news_carries_the_whole_html(db):
    """body_html was null or a 410-character fragment; GovClipping need the HTML too."""
    n = db.execute(text(
        "SELECT count(*) FROM economy_items WHERE body_code = 'eea' "
        "  AND item_type = 'news' AND coalesce(length(body_html),0) >= 2000")).scalar()
    assert n > 150, f"only {n} EEA news rows carry substantial body_html"


# ------------------------------------------------------------------ the guard
@pytest.mark.parametrize("url,institution,expected", [
    ("http://10.140.139.135:3000/en/newsroom/news/x", "EEA",
     "https://www.eea.europa.eu/en/newsroom/news/x"),
    ("http://192.168.0.9/en/a", "EEA", "https://www.eea.europa.eu/en/a"),
    ("https://www.eea.europa.eu/en/b", "EEA", "https://www.eea.europa.eu/en/b"),
    ("https://ec.europa.eu/c", "COMMISSION", "https://ec.europa.eu/c"),
])
def test_a_private_address_is_rewritten_before_it_becomes_an_identity(url, institution, expected):
    from services.news.public_url import canonical_public_url

    assert canonical_public_url(url, institution) == expected


def test_an_unknown_publisher_is_left_alone_rather_than_guessed():
    """We only rewrite to a host we know the publisher serves on."""
    from services.news.public_url import canonical_public_url

    assert canonical_public_url("http://10.1.2.3:3000/a", "SOMEBODY") == "http://10.1.2.3:3000/a"


def test_the_ingest_normalises_before_it_looks_the_row_up():
    """Normalising after the lookup would still create the duplicate row."""
    src = (BACKEND / "scripts" / "sync_dg_news.py").read_text(encoding="utf-8")
    assert "canonical_public_url" in src
    assert src.index("canonical_public_url(it[field]") < src.index("EuNewsItem.entry_key == it")


def test_localhost_is_a_private_host_too():
    """The first regex matched only numeric addresses.

    25 EEA rows read `http://localhost:3000/...` and sailed through as public URLs: the
    same leak in a different spelling. One entity must not become two because a host was
    written by name instead of by number.
    """
    from services.news.public_url import canonical_public_url, is_private

    for url in ("http://localhost:3000/en/newsroom/news/x",
                "http://localhost/en/newsroom/news/x",
                "http://[::1]:3000/en/a",
                "http://0.0.0.0:3000/en/a"):
        assert is_private(url), f"{url} must be recognised as private"

    assert canonical_public_url("http://localhost:3000/en/newsroom/news/x", "EEA") == \
        "https://www.eea.europa.eu/en/newsroom/news/x"


def test_a_public_host_that_merely_starts_with_localhost_is_left_alone():
    """`localhost-services.europa.eu` is a real host. Matching on a word boundary rewrote it."""
    from services.news.public_url import canonical_public_url, is_private

    for url in ("https://localhost-services.europa.eu/a", "https://localhostel.eu/a"):
        assert not is_private(url), f"{url} is public and must not be rewritten"
        assert canonical_public_url(url, "EEA") == url
