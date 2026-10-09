"""scripts/sync_oeil_procedures.py, the only writer of oeil_procedures (migration 288)."""
import json
import pathlib

import pytest

from scripts import sync_oeil_procedures as s

BACKEND = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("status,finished", [
    ("Procedure completed", True),
    ("Procedure completed - delegated act enters into force", True),
    ("Procedure completed - delegated act rejected", True),
    ("Procedure rejected", True),
    ("Procedure lapsed or withdrawn", True),
    ("Procedure completed, awaiting publication in Official Journal", False),
    ("Awaiting committee decision", False),
    ("Awaiting plenary debate/vote", False),
    ("Preparatory phase in Parliament", False),
    (None, False),
])
def test_a_finished_status_is_one_after_which_parliament_does_nothing(status, finished):
    assert s.is_finished(status) is finished


def test_row_params_take_the_type_from_the_reference_and_build_the_url():
    p = s.row_params("2026/2565(RSP)", {"title": "T", "status": "Procedure completed",
                                         "key_events": [{"date": "2026-01-22", "event": "Decision by Parliament", "reference": "T10-0023/2026"}],
                                         "motion_refs": ["B10-0069/2026"], "text_refs": ["T10-0023/2026"]})
    assert (p["year"], p["number"], p["ptype"]) == (2026, 2565, "RSP")
    assert p["url"].endswith("reference=2026/2565(RSP)")
    assert json.loads(p["key_events"])[0]["reference"] == "T10-0023/2026"
    assert p["motion_refs"] == ["B10-0069/2026"]


def test_an_empty_field_is_null_so_the_upsert_keeps_the_stored_value():
    p = s.row_params("2026/2561(RSP)", {"title": "", "status": ""})
    assert p["title"] is None and p["status"] is None


def test_a_malformed_reference_is_refused():
    with pytest.raises(ValueError):
        s.row_params("2026/2561", {})


def test_the_upsert_never_blanks_a_title_or_status_and_never_deletes():
    sql = str(s.UPSERT)
    assert "COALESCE(EXCLUDED.title, oeil_procedures.title)" in sql
    assert "COALESCE(EXCLUDED.oeil_status, oeil_procedures.oeil_status)" in sql
    src = (BACKEND / "scripts" / "sync_oeil_procedures.py").read_text()
    assert "DELETE" not in src.upper().replace("NEVER A DELETE", "")


def test_discovery_covers_last_year_only_until_march():
    from datetime import date
    assert s.discovery_years(date(2027, 1, 15)) == [2026, 2027]
    assert s.discovery_years(date(2027, 2, 28)) == [2026, 2027]
    assert s.discovery_years(date(2027, 3, 1)) == [2027]


def test_a_feed_record_that_is_not_served_is_refused(tmp_path):
    f = tmp_path / "feed.json"
    f.write_text(json.dumps([{"procedure_ref": "2026/2561(RSP)", "state": "unserved"}]))
    with pytest.raises(SystemExit):
        s.load_feed([str(f)], s.Writer(apply=False))


def test_an_empty_feed_is_refused(tmp_path):
    f = tmp_path / "feed.json"
    f.write_text("[]")
    with pytest.raises(SystemExit):
        s.load_feed([str(f)], s.Writer(apply=False))


def test_migration_288_has_rls_policy_grants_and_touch_trigger():
    sql = (BACKEND / "migrations" / "288_oeil_procedures.sql").read_text()
    for needle in ("ENABLE ROW LEVEL SECURITY", "CREATE POLICY", "GRANT SELECT ON public.oeil_procedures TO anon, authenticated",
                   "GRANT ALL ON public.oeil_procedures TO service_role", "brubru_touch_if_changed('last_updated', 'scraped_at,last_served_at', 'first_seen')",
                   "procedure_ref    TEXT        NOT NULL UNIQUE"):
        assert needle in sql, needle


@pytest.mark.live
def test_stored_rows_match_their_reference_and_none_was_deleted_as_absent():
    from sqlalchemy import text
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        bad = db.execute(text("""SELECT count(*) FROM oeil_procedures
            WHERE public_url <> 'https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=' || procedure_ref
               OR (served AND unserved_since IS NOT NULL) OR (NOT served AND unserved_since IS NULL)""")).scalar()
        assert bad == 0
    finally:
        db.close()


# --- the page itself (migration 289) ---------------------------------------------------

def _fixture(name):
    import gzip
    return gzip.decompress((BACKEND / "tests" / "fixtures" / "oeil_probe" / name).read_bytes()).decode("utf-8")


def test_a_page_read_now_is_kept_as_the_body_cleaned_like_the_carriage_copy():
    from services.scrapers.oeil_body_scraper import parse_body
    html = _fixture("rsp_debate_only_2026_2561.html.gz")
    p = s.row_params("2026/2561(RSP)", {"title": "T"}, html=html)
    expected = parse_body(html)
    assert p["body_txt"] == expected.text_body and len(p["body_txt"]) > 500
    assert p["body_html"] == expected.html_body
    assert "Debate in Parliament" in p["body_txt"]


def test_a_feed_record_has_no_page_and_the_upsert_keeps_the_stored_body():
    p = s.row_params("2026/2561(RSP)", {"title": "T"})
    assert p["body_txt"] is None and p["body_html"] is None
    sql = str(s.UPSERT)
    assert "COALESCE(EXCLUDED.body_txt, oeil_procedures.body_txt)" in sql
    assert "COALESCE(EXCLUDED.body_html, oeil_procedures.body_html)" in sql


def test_the_hook_hands_over_only_the_page_of_the_reference_asked_for():
    import httpx
    html = "<html>page</html>"
    url = s.PROCEDURE_URL + "2026/2561(RSP)"
    resp = httpx.Response(200, text=html, request=httpx.Request("GET", url))
    page = s.LastPage()
    page(resp)
    assert page.html_for("2026/2561(RSP)") == html
    assert page.html_for("2026/2562(RSP)") is None
    page(httpx.Response(404, text="does not exist", request=httpx.Request("GET", url)))
    assert page.html_for("2026/2561(RSP)") is None


def test_pages_never_kept_are_read_first():
    src = (BACKEND / "scripts" / "sync_oeil_procedures.py").read_text()
    assert "return (no_page + open_ + stale_done)[:limit]" in src
