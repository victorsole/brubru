"""O237 (9 Nov 2026): three scheduled feeds rewrote every row they read, changed or not.

- sync_economy.py stamped fetched_at = now() on every agency item every run: a new version in 14 indexes,
  the touch and tsvector triggers over the full text, about half of the database's write log over the
  weekend of 7-8 Nov (1,079 batches, ~16.7 GB).
- ingest_cordis_projects.py and ingest_ft_projects_nonh2020.py rewrote every project (560,344 updates on
  115,437 rows since 18 Oct). Rewrites keep the visibility map stale, so the awards total's index-only
  counts fetched 70,462 + 26,383 heap rows: 42.9 s on 9 Nov, past the sandbox's 20 s limit.

Each upsert now carries a WHERE built from its own SET list (services/sql_upsert_guard.py), and the agency
sync records "this feed was read" once per feed in economy_feed_reads (migration 325), which the two
freshness readers take beside max(fetched_at).

Proven on scratch copies of the production tables (old SQL on one, new on the other, same input):
identical final tables in every column but the stamps; agency replay 3,154 items 0 written (39.3 vs
5.0 MB WAL); every SET rule exercised: the same 91 items changed; projects replay 2,000 to 0 written,
every rule: the same 60 projects changed. The readers were run in process in four states.
These tests hold the shape that proof depends on; Postgres is not available in CI.
"""
import os
import pathlib
import re
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND / "scripts"), str(BACKEND)]
os.environ.setdefault("TESTING", "1")

from services.sql_upsert_guard import only_if_changed  # noqa: E402
import sync_economy as eco  # noqa: E402
import ingest_cordis_projects as cordis  # noqa: E402
import ingest_ft_projects_nonh2020 as other  # noqa: E402


def _targets(set_sql: str) -> list:
    """SET targets read independently of the guard: a column name, '=', at the start of an item."""
    flat = re.sub(r"--[^\n]*", "", set_sql)
    return [m for m in re.findall(r"(?:^|,)\s*([a-z_]+)\s*=(?!=)", flat, re.M)]


GUARDED = {
    "economy": (eco._SET_CLAUSE, "economy_items", ("fetched_at",), [eco._UPSERT, eco._UPSERT_BATCH]),
    "cordis": (cordis._PROJECT_SET, "ft_funded_projects", ("scraped_at", "last_updated"), [cordis._UPSERT_SQL]),
    "other": (other._PROJECT_SET, "ft_funded_projects", ("scraped_at", "last_updated"), [other.UPSERT]),
}


@pytest.mark.parametrize("name", GUARDED)
def test_each_guard_compares_every_column_its_update_writes_except_the_stamps(name):
    set_sql, table, skip, _ = GUARDED[name]
    guard = only_if_changed(set_sql, table, skip=skip)
    compared = [c.strip().removeprefix(f"{table}.") for c in
                re.search(r"WHERE \((.*?)\)\s+IS DISTINCT FROM", guard, re.S).group(1).split(",")]
    targets = _targets(set_sql)
    assert compared == [c for c in targets if c not in skip]
    assert set(skip) <= set(targets), "a skipped stamp must be one the SET writes"
    assert len(compared) == {"economy": 11, "cordis": 18, "other": 11}[name]


@pytest.mark.parametrize("name", GUARDED)
def test_every_statement_carries_its_guard_between_set_and_the_end(name):
    set_sql, table, skip, statements = GUARDED[name]
    guard = only_if_changed(set_sql, table, skip=skip)
    for sql in statements:
        assert set_sql in sql and guard in sql
        assert sql.index("DO UPDATE SET") < sql.index(guard)
        assert "ON CONFLICT" in sql.split(guard)[0]


def test_the_economy_upserts_return_what_they_wrote_so_the_run_can_count_it():
    for sql in (eco._UPSERT, eco._UPSERT_BATCH):
        assert sql.rstrip().endswith("RETURNING (xmax = 0) AS inserted;")
    src = (BACKEND / "scripts" / "sync_economy.py").read_text(encoding="utf-8")
    assert "execute_values(db.cur, _UPSERT_BATCH, chunk, page_size=batch, fetch=True)" in src
    assert "written, {n - written} unchanged" in src


class _Db:
    def __init__(self):
        self.cur, self.commits, self.rollbacks = object(), 0, 0

    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def _row(body, itype):
    return (body, itype, "t", None, f"https://x/{body}/{itype}", None, None, None, None, "rss", None, None, None, None)


def _capture(monkeypatch, fail=False):
    seen = {}

    def fake(cur, sql, rows, *a, **k):
        if fail:
            import psycopg2
            raise psycopg2.errors.UndefinedTable('relation "economy_feed_reads" does not exist\nLINE 1: ...')
        seen["sql"], seen["rows"] = sql, rows
    monkeypatch.setattr(eco, "execute_values", fake)
    return seen


def test_a_feed_read_is_recorded_once_per_feed_with_its_count(monkeypatch, capsys):
    db, seen = _Db(), _capture(monkeypatch)
    eco._record_feed_reads(db, [_row("eea", "news"), _row("eea", "news"), _row("eea", "topic")])
    assert "INSERT INTO economy_feed_reads" in seen["sql"] and "ON CONFLICT (body_code, item_type)" in seen["sql"]
    assert "scraped_at = now()" in seen["sql"] and "items_read = EXCLUDED.items_read" in seen["sql"]
    assert sorted(seen["rows"]) == [("eea", "news", 2), ("eea", "topic", 1)]
    assert db.commits == 1 and capsys.readouterr().out == ""


def test_a_run_that_read_nothing_records_nothing(monkeypatch):
    db, seen = _Db(), _capture(monkeypatch)
    eco._record_feed_reads(db, [])
    assert seen == {} and db.commits == 0


def test_a_record_that_cannot_be_written_says_so_on_one_line(monkeypatch, capsys):
    db = _Db(); _capture(monkeypatch, fail=True)
    eco._record_feed_reads(db, [_row("eea", "news")])
    out = capsys.readouterr().out.strip().splitlines()
    assert db.rollbacks == 1 and len(out) == 1
    assert out[0].startswith("[SYNC_STATUS] degraded: feed read not recorded for eea/news (UndefinedTable:")


def test_both_freshness_readers_take_the_later_of_the_item_stamp_and_the_feed_read():
    news = (BACKEND / "api" / "v2" / "news" / "__init__.py").read_text(encoding="utf-8")
    flat = re.sub(r'"\s*\n\s*"', "", re.sub(r"[ \t]+", " ", news))
    assert "greatest(max(fetched_at), (SELECT max(r.scraped_at) FROM economy_feed_reads r" in flat
    assert "brubru_news_kind_of('economy_items', r.item_type) IS NOT NULL" in flat
    health = (BACKEND / "scripts" / "scraper_health.py").read_text(encoding="utf-8")
    assert "greatest(e.f, r.scraped_at)" in health and "LEFT JOIN economy_feed_reads r USING (body_code, item_type)" in health


def test_the_feed_reads_table_ships_with_rls_policies_and_grants():
    sql = (BACKEND / "migrations" / "325_economy_feed_reads.sql").read_text(encoding="utf-8")
    order = [sql.index(s) for s in ("CREATE TABLE IF NOT EXISTS public.economy_feed_reads",
                                    "ENABLE ROW LEVEL SECURITY", "CREATE POLICY", "GRANT SELECT")]
    assert order == sorted(order)
    for col in ("scraped_at", "first_seen", "last_updated", "items_read", "PRIMARY KEY (body_code, item_type)"):
        assert col in sql
    assert "GRANT ALL    ON public.economy_feed_reads TO service_role" in sql


def test_the_guard_builder_refuses_what_it_cannot_read():
    with pytest.raises(ValueError):
        only_if_changed("a = f(x", "t")
    with pytest.raises(ValueError):
        only_if_changed("NOT A COLUMN = 1", "t")
    with pytest.raises(ValueError):
        only_if_changed("fetched_at = now()", "t", skip=("fetched_at",))
    g = only_if_changed("""
        -- a comment, with a comma (and a parenthesis, and it's
        a = CASE WHEN x ~ '(a|b), c' THEN f(x, y) ELSE 'it''s, (fine' END,
        b = COALESCE(EXCLUDED.b, t.b),
        stamp = now()""", "t", skip=("stamp",))
    assert "(t.a, t.b)" in g
    assert "CASE WHEN x ~ '(a|b), c' THEN f(x, y) ELSE 'it''s, (fine' END, COALESCE(EXCLUDED.b, t.b))" in g


def test_run_one_records_the_feed_read_after_its_upserts_and_counts_unchanged_rows(monkeypatch, capsys):
    """The real _run_one, with the scraper, the database and the reference helpers stubbed: every item
    it read reaches the feed record, and the summary line says how many the guard skipped."""
    from services.scrapers.economy_common import Item
    items = [Item(body_code="eea", item_type="news", title=f"t{i}", public_url=f"https://x/{i}",
                  document_date=None) for i in range(3)]
    monkeypatch.setitem(eco.INGESTORS, ("eea", "news"), lambda fetch_bodies=True: items)
    for helper in ("_refuse_undated_new_news", "_shared_references_to_none", "_repoint_by_reference",
                   "_drop_references_held_elsewhere", "_keep_stored_type"):
        monkeypatch.setattr(eco, helper, lambda *a, **k: None)
    calls = []
    monkeypatch.setattr(eco, "execute_values", lambda cur, sql, rows, **k: calls.append(("upsert", len(rows))) or [(True,)])
    monkeypatch.setattr(eco, "_record_feed_reads", lambda db, rows: calls.append(("record", sorted({(r[0], r[1]) for r in rows}), len(rows))))
    db = _Db()
    assert eco._run_one(db, "eea", "news", fetch_bodies=False, legal_limit=0) == 3
    assert calls == [("upsert", 3), ("record", [("eea", "news")], 3)]
    assert "[OK] eea/news: upserted 3 items (1 written, 2 unchanged)" in capsys.readouterr().out
