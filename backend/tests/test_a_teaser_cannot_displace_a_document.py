"""A feed summary must never overwrite the article it summarises.

The backfill fetched 348 EEA articles in full on 25 September 2026. `sync_economy.py` ran at
15:01 the same day and put the 490-character RSS teaser back over every one of them: the
upsert asked only whether the incoming body was non-empty. Every scheduled writer into
economy_items now has to prove it brought MORE text.

These tests run the REAL upsert SQL against the REAL table inside a transaction that is
rolled back, so the constraint and the SQL under test are the production ones, and nothing
is left behind in a table the API serves.
"""
import os
import pathlib
import sys
import uuid

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import psycopg2
import psycopg2.extras
import pytest

# These modules import their siblings the way a script does, so they load with scripts/ on
# the path rather than as backend.scripts.*.
_SCRIPTS = str(pathlib.Path(_REPO_ROOT, "backend", "scripts"))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from sync_economy import _UPSERT, _UPSERT_BATCH  # noqa: E402
from ingest_ft_news_events import UPSERT as FT_NEWS_UPSERT  # noqa: E402
from ingest_ft_programme_calls import UPSERT_SQL as FT_CALLS_UPSERT  # noqa: E402

DOCUMENT = ("The whole article. " * 400).strip()  # ~7,600 chars; the SQL btrims, so we do too
TEASER = "A short RSS summary of that article."  # ~36


def _dsn():
    for line in pathlib.Path(_REPO_ROOT, "backend", ".env").read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    pytest.skip("no DATABASE_URL")


@pytest.fixture()
def cur():
    """A cursor whose work is always rolled back."""
    conn = psycopg2.connect(_dsn())
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield c
    finally:
        conn.rollback()
        conn.close()


# A real body_code: economy_items.body_code is a foreign key, and the point of running
# against the real table is that its real constraints apply. The transaction is rolled back.
BODY = "eea"

_COLS = ("body_code", "item_type", "title", "summary", "public_url", "body_txt",
         "body_html", "document_date", "creation_date", "source_kind", "guid")


def _row(url, body_txt, body_html="<p>x</p>", item_type="news"):
    return {
        "body_code": BODY, "item_type": item_type, "title": "t", "summary": "s",
        "public_url": url, "body_txt": body_txt, "body_html": body_html,
        "document_date": None, "creation_date": None, "source_kind": "rss", "guid": url,
    }


def _run(cur, sql, row):
    """_UPSERT takes named params; _UPSERT_BATCH takes `VALUES %s` via execute_values."""
    if "VALUES %s" in sql:
        psycopg2.extras.execute_values(cur, sql, [tuple(row[c] for c in _COLS)])
    else:
        cur.execute(sql, row)


def _stored(cur, url):
    cur.execute("SELECT body_txt, body_html FROM economy_items WHERE public_url = %s", (url,))
    return cur.fetchone()


@pytest.mark.parametrize("sql", [_UPSERT, _UPSERT_BATCH], ids=["upsert", "upsert_batch"])
def test_sync_economy_keeps_the_longer_body(cur, sql):
    url = f"https://example.europa.eu/{uuid.uuid4()}"
    _run(cur, sql, _row(url, DOCUMENT, "<p>" + "x" * 5000 + "</p>"))
    _run(cur, sql, _row(url, TEASER, "<p>short</p>"))
    got = _stored(cur, url)
    assert got["body_txt"] == DOCUMENT, "the teaser displaced the fetched article"
    assert len(got["body_html"]) > 1000, "the teaser's HTML displaced the article's HTML"


@pytest.mark.parametrize("sql", [_UPSERT, _UPSERT_BATCH], ids=["upsert", "upsert_batch"])
def test_a_genuinely_longer_body_still_wins(cur, sql):
    """The guard must not freeze the column: a better scrape has to get through."""
    url = f"https://example.europa.eu/{uuid.uuid4()}"
    _run(cur, sql, _row(url, TEASER))
    _run(cur, sql, _row(url, DOCUMENT))
    assert _stored(cur, url)["body_txt"] == DOCUMENT, "a fuller body must replace a teaser"


def test_ft_news_upsert_keeps_the_longer_body(cur):
    url = f"https://example.europa.eu/{uuid.uuid4()}"
    for body in (DOCUMENT, TEASER):
        cur.execute(FT_NEWS_UPSERT, {"item_type": "news", "title": "t", "summary": "s",
                                     "public_url": url, "body_txt": body,
                                     "body_html": "<p>x</p>", "document_date": None,
                                     "guid": url})
    assert _stored(cur, url)["body_txt"] == DOCUMENT


def test_ft_calls_upsert_keeps_the_longer_body(cur):
    url = f"https://example.europa.eu/{uuid.uuid4()}"
    for body in (DOCUMENT, TEASER):
        cur.execute(FT_CALLS_UPSERT, {"body_code": "ftportal", "title": "t", "summary": "s",
                                      "public_url": url, "body_txt": body,
                                      "body_html": "<p>x</p>", "document_date": None,
                                      "guid": url})
    assert _stored(cur, url)["body_txt"] == DOCUMENT


def test_nothing_was_left_behind():
    """The fixture rolls back; prove it, because a test row in a served table is a defect."""
    conn = psycopg2.connect(_dsn())
    try:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM economy_items WHERE public_url LIKE 'https://example.europa.eu/%'")
        assert c.fetchone()[0] == 0, "a test row survived into a table the API serves"
    finally:
        conn.close()
