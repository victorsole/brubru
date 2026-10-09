"""GovClipping identifies every document by its `id` ("it lets me know whether I already
have the document", 8 Oct 2026). An id is only an identity if the table behind the
endpoint holds ONE row per record: transparency_meetings held 475,782 rows for 30,155
meetings because its only unique key was a random uuid. Every table behind an endpoint
GovClipping syncs must carry a unique key on the record itself and no content
duplicates (rows identical except for id and bookkeeping timestamps).
"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.live

# Tables behind the endpoints GovClipping syncs (its Postman collection, 8 Oct 2026).
# MEPs (EP id), OJ daily (OJ reference), commissioners (slug), Access2Markets (live)
# carry no Brubru row id.
TABLES = ["eu_calendar_events", "commission_documents", "public_consultations", "infringement_cases",
          "transparency_meetings", "rsb_opinions", "tris_notifications", "institutional_publications",
          "ft_calls_for_proposals", "ft_calls_for_tenders", "tenders", "secondary_acts", "eu_laws",
          "legislative_carriages", "eu_news_items", "mep_amendments", "amendment_documents",
          "committee_work_items", "eprs_publications", "parliamentary_questions", "texts_adopted",
          "ep_resolutions", "ep_roll_call_votes", "committee_meeting_transcripts", "who_is_who_officials",
          "eurovoc_concepts"]
BOOKKEEPING = {"id", "first_seen", "last_updated", "scraped_at", "search_vector", "meeting_key", "ref_ta", "ref_procedure"}


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    s.execute(text("SET statement_timeout = '180s'"))
    yield s
    s.close()


@pytest.mark.parametrize("table", TABLES + ["economy_items"])
def test_the_table_has_a_unique_key_on_the_record(db, table):
    n = db.execute(text("""SELECT count(*) FROM pg_index WHERE indrelid = CAST(:t AS regclass)
                           AND indisunique AND NOT indisprimary"""), {"t": table}).scalar()
    assert n >= 1, f"{table}: only the primary key is unique, so a re-ingest can duplicate every record"


@pytest.mark.parametrize("table", TABLES)
def test_no_record_is_held_twice(db, table):
    cols = [r[0] for r in db.execute(text("""SELECT column_name FROM information_schema.columns
        WHERE table_name = :t AND table_schema = 'public' AND is_generated = 'NEVER'"""), {"t": table})]
    excl = [c for c in cols if c in BOOKKEEPING or (c.endswith("_at") and c != "published_at")]
    expr = " - ".join(["to_jsonb(x)"] + [f"'{c}'" for c in excl])
    rows, distinct = db.execute(text(f"SELECT count(*), count(DISTINCT md5(({expr})::text)) FROM {table} x")).one()
    assert rows == distinct, f"{table}: {rows - distinct} row(s) duplicate another except for id/timestamps"


def test_news_items_are_held_once(db):
    """economy_items is too large for the full-row check: its identifying fields instead."""
    rows, distinct = db.execute(text("""SELECT count(*), count(DISTINCT md5(coalesce(body_code,'')||'|'||
        coalesce(item_type,'')||'|'||coalesce(title,'')||'|'||coalesce(public_url,'')||'|'||
        coalesce(document_date::text,''))) FROM economy_items""")).one()
    assert rows == distinct, f"economy_items: {rows - distinct} duplicate item(s)"
