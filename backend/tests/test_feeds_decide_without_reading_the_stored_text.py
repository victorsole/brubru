"""O245 (27 Nov 2026): the feeds read every stored article back from disk to change nothing.

Supabase warned that the project was depleting its Disk IO budget. In the two weeks since the
statistics were reset the agency-feed job was 42% of all disk reads (138 GB) while adding about
160 items a day. Four statements did it:

- the "write only if changed" guard of 9 Nov (O237) compared each stored body with the incoming
  one by value, and its "longer text wins" rule counted the stored text's characters: both open
  the whole stored article, for every item, on every run;
- the per-feed read of what is stored asked for `length(body_txt)` of every item;
- a lookup by `public_url` alone, which no index serves, read the whole table each call;
- the daily freshness count read the whole table for `max(fetched_at)`.

Now a body changes only when the incoming one is non-empty and larger in bytes, a size
PostgreSQL keeps in the row; the lookup names the body and the type so the unique index
answers; the stored length is counted only for short texts; the freshness script reads the
feed's own read row.
"""
import importlib
import re
from types import SimpleNamespace

import pytest

from services.sql_upsert_guard import only_if_changed

eco = importlib.import_module("scripts.sync_economy")
health = importlib.import_module("scripts.scraper_health")
stats = importlib.import_module("services.mcp.stats")


def _flat(sql):
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", sql))


# ---- the guard builder -----------------------------------------------------------------

SET = "title = COALESCE(EXCLUDED.title, t.title), body = CASE WHEN big THEN EXCLUDED.body ELSE t.body END, seen = now()"


def test_a_column_with_its_own_change_test_is_not_compared_by_value():
    guard = _flat(only_if_changed(SET, "t", skip=("seen",), changed_when={"body": "big"}))
    assert guard == " WHERE ((t.title) IS DISTINCT FROM (COALESCE(EXCLUDED.title, t.title)) OR (big))"
    assert "t.body" not in guard                                   # the stored text is never named


def test_without_a_change_test_the_guard_is_exactly_what_it_was():
    assert _flat(only_if_changed(SET, "t", skip=("seen",))) == (
        " WHERE (t.title, t.body) IS DISTINCT FROM "
        "(COALESCE(EXCLUDED.title, t.title), CASE WHEN big THEN EXCLUDED.body ELSE t.body END)")
    assert only_if_changed(SET, "t", skip=("seen",)) == only_if_changed(SET, "t", skip=("seen",), changed_when={})


def test_two_change_tests_are_both_or_ed_and_the_whole_condition_is_one_group():
    guard = _flat(only_if_changed("a = x, b = y, c = z", "t", skip=(), changed_when={"b": "b_big", "c": "c_big"}))
    assert guard == " WHERE ((t.a) IS DISTINCT FROM (x) OR (b_big) OR (c_big))"


def test_a_change_test_for_a_column_the_update_does_not_set_is_refused():
    with pytest.raises(ValueError, match="does not set"):
        only_if_changed(SET, "t", skip=("seen",), changed_when={"summary": "x"})
    with pytest.raises(ValueError, match="nothing left"):
        only_if_changed("body = x", "t", skip=(), changed_when={"body": "big"})


# ---- the feed's own statements ----------------------------------------------------------

def test_longer_is_measured_in_bytes_and_an_empty_incoming_text_never_looks_at_the_stored_one():
    test = eco._longer("body_txt")
    assert test == ("CASE WHEN NULLIF(btrim(EXCLUDED.body_txt), '') IS NULL THEN false "
                    "ELSE octet_length(btrim(EXCLUDED.body_txt)) > COALESCE(octet_length(economy_items.body_txt), 0) END")
    assert test.index("IS NULL THEN false") < test.index("economy_items.body_txt")   # the empty case answers first


def test_no_statement_counts_the_characters_of_a_stored_text():
    for sql in (eco._SET_CLAUSE, eco._GUARD, eco._UPSERT, eco._UPSERT_BATCH):
        flat = _flat(sql)
        assert "length(COALESCE(economy_items." not in flat and "length(economy_items." not in flat.replace("octet_length(economy_items.", "")
        assert " length(" not in flat.replace("octet_length(", "")


def test_the_two_bodies_and_the_source_kind_follow_the_same_test():
    flat = _flat(eco._SET_CLAUSE)
    for col in ("body_txt", "body_html"):
        assert f"{col} = CASE WHEN {eco._longer(col)} THEN btrim(EXCLUDED.{col}) ELSE economy_items.{col} END" in flat
    assert f"source_kind = CASE WHEN {eco._longer('body_txt')} THEN EXCLUDED.source_kind ELSE economy_items.source_kind END" in flat


def test_the_guard_never_compares_a_stored_body_and_still_compares_everything_else():
    guard = _flat(eco._GUARD)
    compared = [c.strip() for c in re.search(r"WHERE \(\((.*?)\) IS DISTINCT FROM", guard).group(1).split(",")]
    assert compared == [f"economy_items.{c}" for c in (
        "title", "summary", "document_date", "source_kind", "guid", "tender_reference", "status", "deadline", "creation_date")]
    assert guard.endswith(f"OR ({eco._longer('body_txt')}) OR ({eco._longer('body_html')}))")
    for sql in (eco._UPSERT, eco._UPSERT_BATCH):
        assert eco._GUARD in sql and sql.index("DO UPDATE SET") < sql.index(eco._GUARD)


def test_the_stored_length_is_counted_only_for_a_short_text():
    sql = eco._KNOWN_ROWS_SQL
    assert "CASE WHEN octet_length(body_txt) >= 800 THEN octet_length(body_txt) ELSE coalesce(length(body_txt), 0) END" in sql
    assert sql.endswith("FROM economy_items WHERE body_code = %s AND item_type = %s")
    seen = []
    db = SimpleNamespace(execute=lambda q, p: seen.append((q, p)), fetchall=lambda: [("u", "t", None, 900, "g")],
                         rollback=lambda: seen.append("rollback"))
    assert eco._known_rows(db, "eea", "news") == [("u", "t", None, 900, "g")]
    assert seen == [(eco._KNOWN_ROWS_SQL, ("eea", "news")), "rollback"]


def test_800_bytes_is_at_least_the_200_characters_the_rule_asks_for():
    from services.scrapers import economy_common as ec
    assert ec._FULL_BODY_CHARS * 4 == 800                          # no character is more than 4 bytes in UTF-8
    assert len(("\U0001F600" * 200).encode("utf-8")) == 800


def test_the_lookup_of_stored_addresses_names_the_body_and_the_type(monkeypatch):
    asked = {}

    class _Session:
        def execute(self, statement, params):
            asked.update(sql=str(statement), params=params)
            return SimpleNamespace(all=lambda: [("eea", "news", "https://x/1")])

        def close(self):
            asked["closed"] = True
    monkeypatch.setattr("core.database.SessionLocal", lambda: _Session())
    keys = [("eea", "news", "https://x/2"), ("eea", "news", "https://x/1"), ("echa", "press_release", "https://y/1")]
    assert eco._existing_urls(keys) == {("eea", "news", "https://x/1")}
    assert "body_code = ANY(:b) AND item_type = ANY(:t) AND public_url = ANY(:u)" in asked["sql"]
    assert asked["params"] == {"b": ["echa", "eea"], "t": ["news", "press_release"],
                               "u": ["https://x/1", "https://x/2", "https://y/1"]}
    assert asked["closed"] is True


# ---- the freshness script ---------------------------------------------------------------

class _Db:
    def __init__(self, counts, reads, newest):
        self.counts, self.reads, self.newest, self.asked = counts, reads, newest, []

    def execute(self, statement, params=None):
        sql = _flat(str(statement))
        self.asked.append((sql, params))
        if "count(*)" in sql:
            return list(self.counts)
        if "FROM economy_feed_reads" in sql:
            return list(self.reads)
        return SimpleNamespace(scalar=lambda: self.newest[(params["b"], params["t"])])


def test_a_feeds_last_read_is_its_own_read_row_and_only_a_feed_without_one_is_looked_up():
    db = _Db(counts=[("eea", "news", 264), ("old", "news", 12)], reads=[("eea", "news", "2026-11-27")],
             newest={("old", "news"): "2026-08-01"})
    assert health._db_state(db) == {("eea", "news"): (264, "2026-11-27"), ("old", "news"): (12, "2026-08-01")}
    looked_up = [p for s, p in db.asked if "max(fetched_at)" in s]
    assert looked_up == [{"b": "old", "t": "news"}]                # one feed, never the whole table
    count_sql = db.asked[0][0]
    assert count_sql == "SELECT body_code, item_type, count(*) FROM economy_items GROUP BY body_code, item_type"
    assert "fetched_at" not in count_sql                           # a column in no index made it read every row


# ---- the hourly law count ---------------------------------------------------------------

def test_the_corpus_counts_are_kept_for_a_day(monkeypatch):
    assert stats.TTL_SECONDS == 24 * 3600
    calls = []
    monkeypatch.setattr(stats, "_compute", lambda: calls.append(1) or {"laws": 1})
    monkeypatch.setattr(stats, "_cache", {})
    monkeypatch.setattr(stats, "_cache_at", 0.0)
    clock = [1_000_000.0]
    monkeypatch.setattr(stats.time, "time", lambda: clock[0])
    stats.get_corpus_stats(); clock[0] += 23 * 3600; stats.get_corpus_stats()
    assert len(calls) == 1
    clock[0] += 2 * 3600; stats.get_corpus_stats()
    assert len(calls) == 2


# ---- the lookup every inserted row triggers ----------------------------------------------

def test_the_news_table_has_the_index_the_insert_trigger_looks_up():
    import pathlib
    migrations = pathlib.Path(eco.__file__).resolve().parents[1] / "migrations"
    sql = _flat((migrations / "326_eu_news_items_news_url_key_index.sql").read_text(encoding="utf-8"))
    assert ("CREATE INDEX IF NOT EXISTS ix_eu_news_items_news_url_key ON public.eu_news_items "
            "(public.news_url_key(source_url)) WHERE news_kind IS NOT NULL;") in sql
    assert "CONCURRENTLY" not in sql                               # the runner wraps a migration in a transaction
    assert "ANALYZE public.eu_news_items;" in sql
    # the trigger's own lookup, as migration 255 wrote it: the index must match its expression and filter
    trigger = "".join(p.read_text(encoding="utf-8") for p in migrations.glob("*.sql") if "brubru_carry_news_kind" in p.read_text(encoding="utf-8"))
    flat = _flat(trigger)
    assert "n.news_kind IS NOT NULL" in flat and "news_url_key(n.source_url) = public.news_url_key(NEW.public_url)" in flat.replace("public.news_url_key(n.source_url)", "news_url_key(n.source_url)")
