"""The kind an item is served under is decided once and then frozen (migration 254).

GovClipping keys its search documents on the kind we serve (`eu:press_release:<id>`
vs `eu:publication:<id>`). When an item moved between kinds they got a second
document that nothing deleted, their write was refused as an identity collision, and
the feed's sync window stopped advancing. The ask, 29 Sep 2026: no reclassifications.

The scraper-side cause was fixed first, but item_type has TEN writers, and this is
what stops the eleventh. The internal taxonomy stays free to improve: eu_news_items
has 13 item_types feeding 3 kinds, so 'statement' -> 'speech' still happens and still
never reaches a client.
"""
import pytest
from sqlalchemy import text

# Reads production data: runs locally, never in CI (6 Oct 2026).
pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


def _one(db, table, kind):
    row = db.execute(text(
        f"SELECT id FROM {table} WHERE news_kind = :k LIMIT 1"), {"k": kind}).fetchone()
    if row is None:
        pytest.skip(f"no {table} row with news_kind={kind}")
    return row[0]


class TestThePinHolds:
    def test_changing_item_type_does_not_move_the_kind(self, db):
        rid = _one(db, "eu_news_items", "news")
        try:
            got = db.execute(text(
                "UPDATE eu_news_items SET item_type = 'press' WHERE id = :i "
                "RETURNING item_type, news_kind"), {"i": rid}).fetchone()
            assert got[0] == "press", "the internal type is still free to change"
            assert got[1] == "news", "but the published kind must not move"
        finally:
            db.rollback()

    def test_writing_the_kind_directly_is_refused(self, db):
        rid = _one(db, "eu_news_items", "news")
        try:
            got = db.execute(text(
                "UPDATE eu_news_items SET news_kind = 'publication' WHERE id = :i "
                "RETURNING news_kind"), {"i": rid}).scalar()
            assert got == "news"
        finally:
            db.rollback()

    def test_an_economy_row_is_pinned_too(self, db):
        rid = _one(db, "economy_items", "news")
        try:
            got = db.execute(text(
                "UPDATE economy_items SET item_type = 'press_release' WHERE id = :i "
                "RETURNING news_kind"), {"i": rid}).scalar()
            assert got == "news"
        finally:
            db.rollback()


class TestADeliberateChangeIsStillPossible:
    def test_but_it_has_to_say_so(self, db):
        rid = _one(db, "eu_news_items", "news")
        try:
            db.execute(text("SET LOCAL brubru.allow_kind_change = 'on'"))
            got = db.execute(text(
                "UPDATE eu_news_items SET news_kind = 'publication' WHERE id = :i "
                "RETURNING news_kind"), {"i": rid}).scalar()
            assert got == "publication"
        finally:
            db.rollback()


class TestNewRowsGetTheirKind:
    def test_derived_from_item_type_on_insert(self, db):
        try:
            got = db.execute(text(
                "INSERT INTO eu_news_items (entry_key, title, institution, item_type, "
                "source_url) VALUES ('pin-test-press', 't', 'COMMISSION', 'press', "
                "'http://example.invalid/a') RETURNING news_kind")).scalar()
            assert got == "press_release"
        finally:
            db.rollback()

    def test_a_row_outside_the_feed_gets_no_kind(self, db):
        try:
            got = db.execute(text(
                "INSERT INTO eu_news_items (entry_key, title, institution, item_type, "
                "source_url) VALUES ('pin-test-other', 't', 'COMMISSION', 'tender', "
                "'http://example.invalid/b') RETURNING news_kind")).scalar()
            assert got is None, "not a news item, so it carries no kind"
        finally:
            db.rollback()


class TestTheMappingIsComplete:
    def test_every_feed_item_type_has_a_kind(self, db):
        """A row in the feed's vocabulary with no kind would vanish from the API,
        which a client reads as a deletion."""
        from api.v2.news import _EU_NEWS_SOURCE_TYPES
        n = db.execute(text(
            "SELECT count(*) FROM eu_news_items WHERE item_type = ANY(:t) "
            "AND news_kind IS NULL"), {"t": _EU_NEWS_SOURCE_TYPES}).scalar()
        assert n == 0, f"{n} feed rows carry no kind"

    def test_no_kind_outside_the_three(self, db):
        for table in ("eu_news_items", "economy_items"):
            bad = db.execute(text(
                f"SELECT count(*) FROM {table} WHERE news_kind IS NOT NULL "
                "AND news_kind NOT IN ('news', 'press_release', 'publication')")).scalar()
            assert bad == 0, f"{table} has {bad} rows with an unknown kind"
