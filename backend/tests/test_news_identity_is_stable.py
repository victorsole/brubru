"""A story keeps the id we first served it under (29 Sep 2026).

The feed unions two stores and dedups by URL, with economy_items winning. Identity was
therefore decided at READ time by whichever store happened to hold the row: an
institutional story served under its UUID for weeks disappeared the moment an agency
twin arrived, and came back under an integer id, sometimes under a different kind.

Measured before the fix: 1,815 institutional stories suppressed by a twin, 1,599 of
which existed FIRST, and 1,113 of those visible for more than a day -- the longest for
99 days. Their ids return 404. A client that stored one reads that as a deletion, which
is exactly what GovClipping reported for `kind`, one level down.

This file is the whole acceptance set for that work, written before the fix so that no
part of it is discovered afterwards.
"""
import pytest
from sqlalchemy import text

from api.v2.news import _INSTITUTIONAL_NEWS, _NEWS_TYPES


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _clean(db):
    """One failing statement aborts the session, and every later test in the module
    then fails with "current transaction is aborted" -- which reads as seven defects
    when there is one. Roll back between tests so each result is its own."""
    yield
    db.rollback()


INSTS = list(_INSTITUTIONAL_NEWS.values())

# Institutional rows a twin now hides, which existed before that twin: we served them.
_SERVED_THEN_HIDDEN = """
SELECT n.id::text AS id, n.news_kind AS ours, e.news_kind AS theirs, e.id AS twin_id
  FROM eu_news_items n
  JOIN economy_items e
    ON public.news_url_key(e.public_url) = public.news_url_key(n.source_url)
   AND public.news_url_key_exact(e.public_url) = public.news_url_key_exact(n.source_url)
   AND e.news_kind IS NOT NULL
 WHERE n.institution = ANY(:i) AND n.news_kind IS NOT NULL
   AND n.created_at < e.creation_date
"""


class TestAnIdWeServedStillResolves:
    def test_every_hidden_id_resolves_somewhere(self, db):
        """The core promise. An id the API once handed out must still answer."""
        rows = db.execute(text(
            f"SELECT count(*) FROM ({_SERVED_THEN_HIDDEN}) s "
            "WHERE NOT EXISTS (SELECT 1 FROM news_id_alias a WHERE a.alias_id = s.id)"
        ), {"i": INSTS}).scalar()
        assert rows == 0, f"{rows} ids we served resolve to nothing"

    def test_an_alias_points_at_an_item_that_exists(self, db):
        orphan = db.execute(text(
            "SELECT count(*) FROM news_id_alias a "
            "WHERE NOT EXISTS (SELECT 1 FROM economy_items e "
            "  WHERE e.id::text = a.canonical_id AND e.news_kind = ANY(:t)) "
            "  AND NOT EXISTS (SELECT 1 FROM eu_news_items n WHERE n.id::text = a.canonical_id)"
        ), {"t": _NEWS_TYPES}).scalar()
        assert orphan == 0, f"{orphan} aliases point at nothing"

    def test_no_alias_shadows_a_live_id(self, db):
        """An alias must never capture an id the list still hands out itself."""
        clash = db.execute(text(
            "SELECT count(*) FROM news_id_alias a JOIN economy_items e "
            "ON e.id::text = a.alias_id AND e.news_kind = ANY(:t)"), {"t": _NEWS_TYPES}).scalar()
        assert clash == 0, f"{clash} aliases shadow a live agency id"


class TestTheKindSurvivesTheHandover:
    """Forward only. The 200 stories that already disagree are left where they are:
    moving them to their older kind would itself be a reclassification, on the day we
    told a client there would be none. What must not happen is the NEXT one."""

    def test_a_new_agency_twin_adopts_the_kind_the_story_already_has(self, db):
        body = db.execute(text(
            "SELECT body_code FROM economy_items WHERE news_kind IS NOT NULL LIMIT 1")).scalar()
        row = db.execute(text(
            "SELECT n.source_url, n.news_kind FROM eu_news_items n "
            "WHERE n.news_kind = 'press_release' LIMIT 1")).fetchone()
        if row is None:
            pytest.skip("no institutional press release to shadow")
        try:
            got = db.execute(text(
                "INSERT INTO economy_items (body_code, item_type, title, public_url, news_kind) "
                "VALUES (:b, 'news', 'twin arriving later', :u, NULL) "
                "RETURNING news_kind"), {"b": body, "u": row[0]}).scalar()
            assert got == row[1], (
                f"a twin arriving for a story already served as {row[1]} "
                f"would have moved it to {got}")
        finally:
            db.rollback()

    def test_a_twin_for_an_unknown_story_keeps_its_own_kind(self, db):
        body = db.execute(text(
            "SELECT body_code FROM economy_items WHERE news_kind IS NOT NULL LIMIT 1")).scalar()
        try:
            got = db.execute(text(
                "INSERT INTO economy_items (body_code, item_type, title, public_url, news_kind) "
                "VALUES (:b, 'press_release', 'no twin', "
                "'https://example.invalid/unshadowed', NULL) RETURNING news_kind"),
                {"b": body}).scalar()
            assert got == "press_release"
        finally:
            db.rollback()


class TestTheUnionStaysHonest:
    def test_no_url_is_served_by_both_stores(self, db):
        # Grouped by the EXACT key, the same one the dedup decides on. Grouping by
        # the lossy news_url_key() reported two defects that were two pairs of
        # genuinely different articles sharing a query-stripped key.
        from api.v2.news import _news_source_sql
        src, params = _news_source_sql(None, _NEWS_TYPES, None, None, None)
        both = db.execute(text(
            f"SELECT count(*) FROM (SELECT public.news_url_key_exact(public_url) k, "
            "bool_or(id ~ '^[0-9]+$') AS agency, bool_or(id !~ '^[0-9]+$') AS inst "
            f"FROM {src} u GROUP BY 1) s WHERE agency AND inst"), params).scalar()
        assert both == 0, f"{both} URLs served by both stores"

    def test_all_is_the_sum_of_the_three_kinds(self, db):
        from api.v2.news import _news_source_sql
        def total(kinds):
            src, params = _news_source_sql(None, kinds, None, None, None)
            return db.execute(text(f"SELECT count(*) FROM {src} u"), params).scalar()
        parts = sum(total([k]) for k in ("news", "press_release", "publication"))
        assert parts == total(list(_NEWS_TYPES))

    def test_nothing_eligible_is_lost_or_double_served(self, db):
        """Growth-tolerant version of "the totals have not moved".

        Pinning the feed to the 15,012 / 1,888 / 6,853 measured this morning looked
        like a regression test and was really a clock: the corpus grows, publication
        was 6,856 two hours later, and the test would have failed every day while
        teaching nothing. The invariant that actually holds is conservation --
        everything eligible is served exactly once, either by the agency half or by
        the institutional half that the dedup did not suppress.
        """
        from api.v2.news import _news_source_sql, _DEDUP_SQL
        src, params = _news_source_sql(None, list(_NEWS_TYPES), None, None, None)
        served = db.execute(text(f"SELECT count(*) FROM {src} u"), params).scalar()
        agency = db.execute(text(
            "SELECT count(*) FROM economy_items WHERE news_kind IS NOT NULL")).scalar()
        inst = db.execute(text(
            "SELECT count(*) FROM eu_news_items n WHERE n.institution = ANY(:i) "
            f"AND n.news_kind IS NOT NULL AND {_DEDUP_SQL}"), {"i": INSTS}).scalar()
        assert served == agency + inst, (
            f"served {served} but eligible is {agency} agency + {inst} institutional")


class TestTheInvariantIsMaintainedNotBackfilled:
    """A one-off backfill is not an invariant. Forty minutes after the first backfill a
    verification run already found newly hidden ids with no alias, because twins keep
    arriving. The alias is written when the handover happens."""

    def test_a_twin_arriving_now_records_the_alias_it_hides(self, db):
        row = db.execute(text(
            "SELECT n.id::text, n.source_url FROM eu_news_items n "
            "WHERE n.news_kind IS NOT NULL "
            "  AND NOT EXISTS (SELECT 1 FROM news_id_alias a WHERE a.alias_id = n.id::text) "
            f"  AND {'TRUE'} LIMIT 1")).fetchone()
        if row is None:
            pytest.skip("every institutional row already has an alias")
        body = db.execute(text(
            "SELECT body_code FROM economy_items WHERE news_kind IS NOT NULL LIMIT 1")).scalar()
        try:
            new_id = db.execute(text(
                "INSERT INTO economy_items (body_code, item_type, title, public_url, news_kind) "
                "VALUES (:b, 'news', 'a twin arriving now', :u, NULL) RETURNING id"),
                {"b": body, "u": row[1]}).scalar()
            got = db.execute(text(
                "SELECT canonical_id FROM news_id_alias WHERE alias_id = :a"),
                {"a": row[0]}).scalar()
            assert got == str(new_id), (
                "the id this twin just hid was not recorded, so it would 404")
        finally:
            db.rollback()
