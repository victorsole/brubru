"""/resolution-procedures holds EVERY INI/RSP/INL procedure OEIL serves (Victor, 9 Oct 2026).

Until then the table gained only adopted texts plus a one-off batch of 34 rows on 6 Mar 2026,
so a topical debate with no resolution (2026/2561(RSP)) or a report still in committee was
missing or, when present, frozen."""
import pathlib
from types import SimpleNamespace

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _row(**kw):
    base = dict(current_status=None, has_adopted_text=False, current_date_=None,
                carriage_status=None, oeil_page_status=None, oeil_page_decided=False)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture(scope="module")
def status():
    from scripts.backfill_resolution_dates import _status
    return _status


def test_a_debate_with_no_decision_is_closed_without_resolution_even_with_no_carriage(status):
    assert status(_row(oeil_page_status="Procedure completed"), None) == "closed_without_resolution"


def test_a_decision_whose_text_is_not_fetched_yet_is_pending_not_closed(status):
    r = _row(oeil_page_status="Procedure completed", oeil_page_decided=True)
    assert status(r, None) == "pending"
    r = _row(carriage_status="COMPLETED", oeil_page_decided=True)
    assert status(r, None) == "pending"


def test_a_report_in_committee_is_pending(status):
    assert status(_row(oeil_page_status="Awaiting committee decision"), None) == "pending"
    assert status(_row(oeil_page_status="Procedure completed, awaiting publication in Official Journal"), None) == "pending"


def test_an_adopted_text_wins_and_a_lost_vote_stays_rejected(status):
    assert status(_row(oeil_page_status="Procedure completed", has_adopted_text=True), None) == "adopted"
    assert status(_row(current_status="rejected", oeil_page_status="Procedure completed",
                       oeil_page_decided=True), None) == "rejected"


def test_oeil_says_rejected_and_oeil_lists_the_adopted_text(status):
    from datetime import date
    assert status(_row(oeil_page_status="Procedure rejected", oeil_page_decided=True), None) == "rejected"
    # A 9th-term text Brubru never fetches: the page lists T9-... and the decision date.
    assert status(_row(oeil_page_status="Procedure completed", oeil_page_decided=True),
                  date(2024, 2, 8)) == "adopted"


def test_the_carriage_rule_still_holds_without_an_oeil_page(status):
    assert status(_row(carriage_status="COMPLETED"), None) == "closed_without_resolution"
    assert status(_row(carriage_status="AWAITING_COMMITTEE"), None) == "pending"


def test_the_corpus_adds_oeil_procedures_without_touching_existing_rows():
    from scripts import backfill_ep_resolutions_corpus as c
    cand, ins = c._OEIL_CANDIDATES, c._OEIL_INSERT
    assert "o.served" in cand and "('INI', 'RSP', 'INL')" in cand
    assert "NOT EXISTS (SELECT 1 FROM ep_resolutions r" in cand
    assert "ON CONFLICT (procedure_ref) DO NOTHING" in ins     # an existing row keeps its id
    assert ":oeil, NULL, now(), now()" in ins                  # status is left to its owner


def test_the_tier_reads_oeil_then_grows_the_corpus_then_sets_status():
    from services.sync.source_registry import MEUB_SOURCES
    keys = [s.key for s in MEUB_SOURCES]
    assert keys.index("oeil_procedures") < keys.index("resolutions_corpus") < keys.index("resolution_dates") < keys.index("ep_enrich")


def test_one_rule_says_what_a_finished_oeil_status_is():
    for f in ("scripts/backfill_resolution_dates.py", "scripts/sync_oeil_procedures.py"):
        src = (BACKEND / f).read_text()
        assert "from services.matching.oeil_status import is_finished" in src, f
        assert 'startswith("procedure completed")' not in src, f"{f} keeps its own copy of the rule"


@pytest.mark.live
def test_every_inl_ini_rsp_procedure_oeil_serves_has_a_row_with_a_status():
    from sqlalchemy import text
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        missing = db.execute(text("""SELECT count(*) FROM oeil_procedures o WHERE o.served
            AND o.procedure_type IN ('INI','RSP','INL') AND btrim(coalesce(o.title,'')) <> ''
            AND NOT EXISTS (SELECT 1 FROM ep_resolutions r WHERE r.procedure_ref = o.procedure_ref)""")).scalar()
        no_status = db.execute(text("SELECT count(*) FROM ep_resolutions WHERE status IS NULL")).scalar()
        assert missing == 0, f"{missing} procedure(s) OEIL serves have no row"
        assert no_status == 0, f"{no_status} row(s) have no status"
    finally:
        db.close()


@pytest.mark.live
def test_a_debate_only_procedure_is_served_with_its_oeil_events():
    """2026/2561(RSP): no carriage holds it; its events come from oeil_procedures."""
    from sqlalchemy import text
    from core.database import SessionLocal
    from api.v1.resolutions import _items_for
    from models.ep_resolutions import EPResolution
    db = SessionLocal()
    try:
        row = db.query(EPResolution).filter(EPResolution.procedure_ref == "2026/2561(RSP)").one()
        item = _items_for(db, [row])[0]
        assert item.status == "closed_without_resolution"
        assert any(e["event_type"] == "debate_in_parliament" for e in item.key_events), item.key_events
        # The OEIL page itself, not a summary of our own columns (was 142 characters).
        assert "Debate in Parliament" in item.body_txt and len(item.body_txt) > 500, len(item.body_txt)
    finally:
        db.close()
