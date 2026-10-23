"""EU External Action calls for proposals are ingested with the other calls (23 Oct 2026).

The portal lists PROSPECT calls (EuropeAid/...) under "EU External Actions" in its calls for
proposals; matched by identifier on 23 Oct, 21 were open and none was in Brubru: the ingester's
first pass fetched types 1 and 8 only. They carry no description, so the body is composed from
the same fields the portal's own page shows. The fixture is the portal's real record for
EuropeAid/187686/ID/ACT/MK (a twinning call for North Macedonia), read 23 Oct 2026.
"""
import datetime as dt
import importlib
import json
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

sedia = importlib.import_module("ingest_funding_sedia")
RECORD = json.loads((BACKEND / "tests" / "fixtures" / "ft" / "sedia_external_action_187686.json").read_text(encoding="utf-8"))
TODAY = dt.date(2026, 10, 23)


def _labels(monkeypatch):
    monkeypatch.setitem(sedia._PROSPECT_DIVISION_LABELS, "42921320", "Instrument for Pre-accession Assistance")
    monkeypatch.setitem(sedia._PROGRAMME_LABELS, "111111", "EU External Action - Prospect (RELEX-PROSPECT)")


def test_the_record_maps_to_a_call_with_the_portals_own_page(monkeypatch):
    _labels(monkeypatch)
    row = sedia.normalise_row(RECORD, today=TODAY)
    assert row["topic_id"] == "EuropeAid/187686/ID/ACT/MK" and row["call_id"] == "187686"
    assert not row["is_tender"] and row["status"] == "open"
    assert row["source_url"].endswith("/opportunities/prospect-details/187686PROSPECTSEN")
    assert row["programme"] == "Instrument for Pre-accession Assistance"
    assert row["type_of_action"] == "Twinning"
    assert row["indicative_budget"] == 1300000.0 and row["budget_currency"] == "EUR"
    assert row["published_at"].date() == dt.date(2026, 9, 3)          # the portal's "Published"
    assert row["deadline"].date() == dt.date(2026, 11, 5)
    for words in ("Geographical zone: MK.", "Budget: EUR 1,300,000.", "Twinning Fiche", "Deadline: 2026-11-05."):
        assert words in row["description"], words


def test_without_a_division_label_the_programme_is_the_portals_family(monkeypatch):
    monkeypatch.setitem(sedia._PROGRAMME_LABELS, "111111", "EU External Action - Prospect (RELEX-PROSPECT)")
    monkeypatch.setattr(sedia, "_PROSPECT_DIVISION_LABELS", {})
    assert sedia.normalise_row(RECORD, today=TODAY)["programme"] == "EU External Action - Prospect (RELEX-PROSPECT)"


def test_the_first_pass_asks_for_external_actions_and_keeps_them(monkeypatch, tmp_path):
    _labels(monkeypatch)
    asked = []

    def fake_iter(query, **kw):
        types = query["bool"]["must"][0]["terms"]["type"]
        asked.append(types)
        yield 1, ([RECORD] if "2" in types else [])

    monkeypatch.setattr(sedia, "iter_structured", fake_iter)
    monkeypatch.setattr(sedia, "load_programme_labels", lambda: 0)
    monkeypatch.setenv("DATABASE_URL", "postgresql://not-used/when-not-applying")
    dump = tmp_path / "rows.json"
    monkeypatch.setattr(sys, "argv", ["ingest_funding_sedia.py", "--skip-refresh", "--dump-json", str(dump)])
    sedia.main()
    assert ["1", "2"] in asked                      # topics and External Action calls; cascade calls have their own job
    rows = json.loads(dump.read_text())
    assert rows["EuropeAid/187686/ID/ACT/MK"]["source_url"].endswith("187686PROSPECTSEN")


def test_the_description_backfill_leaves_external_actions_alone():
    """They have no topicDetails page; asking would 404 every night and count them as a gap."""
    from sqlalchemy.dialects import postgresql
    backfill = importlib.import_module("backfill_ft_call_descriptions")
    for stmt in (backfill.PICK, backfill.GAP):
        sql = str(stmt.compile(dialect=postgresql.psycopg2.dialect()))
        assert "topic_id NOT LIKE 'EuropeAid/%%'" in sql      # one wildcard once the driver reads it


def test_a_refresh_corrects_the_link_and_takes_a_budget_the_record_gives(monkeypatch):
    """Links and budgets used to be written on the first insert only."""
    _labels(monkeypatch)
    seen = []

    class _Cur:
        def execute(self, sql, params=None): seen.append((sql, params))

    sedia.upsert_ft_calls(_Cur(), sedia.normalise_row(RECORD, today=TODAY))
    sql, params = seen[0]
    conflict = sql.split("ON CONFLICT", 1)[1]
    assert "source_url = EXCLUDED.source_url" in conflict
    assert "indicative_budget = COALESCE(EXCLUDED.indicative_budget, ft_calls_for_proposals.indicative_budget)" in conflict
    assert "WHEN EXCLUDED.indicative_budget IS NOT NULL THEN EXCLUDED.budget_currency" in conflict
    assert params["source_url"].endswith("prospect-details/187686PROSPECTSEN") and params["indicative_budget"] == 1300000.0
