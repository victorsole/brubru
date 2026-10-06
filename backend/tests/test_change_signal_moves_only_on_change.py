"""?updated_from= is only useful if the column it filters on tells the truth.

A partner syncing every morning asks "what changed since yesterday". That answer is
worth having only when a re-sync finding identical content leaves the column alone.
Three separate ways of getting this wrong were live at once on 28 Sep 2026:

* an unconditional BEFORE UPDATE trigger (public_consultations, eu_laws), which also
  silently overrode a guard written into the upsert's ON CONFLICT clause;
* a second scheduled writer nobody had guarded (ep_resolutions had four writers, and
  fixing one left backfill_ep_resolutions_corpus.py stamping all 351 rows per run);
* a generated column (eu_laws.search_vector), which a BEFORE trigger sees as NULL on
  NEW and populated on OLD, so a content comparison reports every row as changed.

The first two made /commission/consultations and /parliament/resolutions answer
"changed since yesterday" with the entire corpus, which is exactly what incremental
sync exists to avoid. The third made the fix for the first look like it had worked.

Every write below happens inside a transaction that is rolled back.
"""
import os
import pytest
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")
pytestmark = [*(pytestmark if isinstance(pytestmark, list) else [pytestmark]), pytest.mark.live]

# Columns that are bookkeeping, not content. An ingestion anchor such as scraped_at
# MUST keep moving every run -- it is what answers "is this feed still alive".
BOOKKEEPING = {"created_at", "updated_at", "last_updated", "scraped_at", "first_seen",
               "first_seen_at", "content_updated_at", "synced_at", "ingested_at",
               "fetched_at", "last_checked", "followup_checked_at", "body_fetched_at",
               "last_synced_at", "enriched_at", "oeil_body_fetched_at",
               "legislative_train_updated_at", "oeil_roles_parsed_at"}

# (table, the column its endpoint filters ?updated_from= on). Derived by resolving
# every `X >= updated_from` filter under api/ to its model's __tablename__; when a new
# endpoint offers the window, its table belongs here.
TABLES = [
    ("public_consultations", "last_updated"),
    ("ep_resolutions", "updated_at"),
    ("eu_laws", "updated_at"),
    ("ft_calls_for_proposals", "content_updated_at"),
    ("ft_calls_for_tenders", "content_updated_at"),
    ("infringement_cases", "content_updated_at"),
    ("infringement_decisions", "content_updated_at"),
    ("who_is_who_officials", "content_updated_at"),
    ("eu_calendar_events", "last_updated"),
    ("catalan_translations", "updated_at"),
    ("commission_documents", "last_updated"),
    ("eprs_publications", "last_updated"),
    ("legislative_carriages", "last_updated"),
    ("texts_adopted", "last_updated"),
    ("parliamentary_questions", "last_updated"),
    ("committee_meeting_transcripts", "last_updated"),
    ("mep_amendments", "updated_at"),
    ("amendment_documents", "updated_at"),
    ("committee_work_items", "last_updated"),
    ("ep_votes", "updated_at"),
    ("eu_officials", "last_updated"),
    ("rsb_opinions", "last_updated"),
    ("secondary_acts", "last_updated"),
    ("tenders", "updated_at"),
    ("transparency_meetings", "last_updated"),
    ("tris_notifications", "last_updated"),
]


@pytest.fixture(scope="module")
def conn():
    engine = create_engine(DB_URL)
    with engine.connect() as c:
        yield c


def _columns(conn, table):
    return [r[0] for r in conn.execute(text(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name=:t "
        "and is_generated='NEVER' and is_updatable='YES'"), {"t": table})]


def _key_column(conn, table):
    return conn.execute(text(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name=:t "
        "and column_name in ('id','initiative_id','procedure_ref') limit 1"),
        {"t": table}).scalar()


def _sample(conn, table):
    cols = _columns(conn, table)
    if not cols:
        pytest.skip(f"{table} does not exist here")
    key = _key_column(conn, table)
    assert key, f"{table} has no recognised key column"
    value = conn.execute(text(f'select "{key}" from "{table}" order by "{key}" limit 1')).scalar()
    if value is None:
        pytest.skip(f"{table} is empty")
    return cols, key, value


def _signal(conn, table, signal, key, value):
    return conn.execute(text(
        f'select "{signal}" from "{table}" where "{key}" = :k'), {"k": value}).scalar()


@pytest.mark.parametrize("table,signal", TABLES)
def test_a_no_op_rewrite_does_not_move_the_change_signal(conn, table, signal):
    """What a nightly re-sync does on an unchanged row: every content column written
    back with the value already stored. The change signal must not move."""
    cols, key, value = _sample(conn, table)
    content = [c for c in cols if c not in BOOKKEEPING]
    before = _signal(conn, table, signal, key, value)
    try:
        sets = ", ".join(f'"{c}" = "{c}"' for c in content)
        conn.execute(text(f'update "{table}" set {sets} where "{key}" = :k'), {"k": value})
        after = _signal(conn, table, signal, key, value)
        assert after == before, (
            f"{table}.{signal} moved on a rewrite that changed nothing, so "
            f"?updated_from= answers with the whole corpus every sync")
    finally:
        conn.rollback()


@pytest.mark.parametrize("table,signal", TABLES)
def test_a_real_change_moves_the_change_signal(conn, table, signal):
    """The other half: a guard that never fires is worse than no guard."""
    cols, key, value = _sample(conn, table)
    target = conn.execute(text(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name=:t and data_type='text' "
        "and column_name not in ('id') order by ordinal_position"), {"t": table}).scalars().all()
    target = [c for c in target if c not in BOOKKEEPING and c in cols]
    if not target:
        pytest.skip(f"{table} has no unbounded text column to mutate")
    col = target[0]
    before = _signal(conn, table, signal, key, value)
    try:
        conn.execute(text(
            f'update "{table}" set "{col}" = coalesce("{col}", \'\') || \' CHANGED\' '
            f'where "{key}" = :k'), {"k": value})
        after = _signal(conn, table, signal, key, value)
        if before is None:
            assert after is not None, f"{table}.{signal} stayed NULL through a real change"
        else:
            assert after > before, (
                f"{table}.{signal} did not move on a real content change, so an "
                f"incremental caller would never see the update")
    finally:
        conn.rollback()
