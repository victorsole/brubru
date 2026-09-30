"""EFCA procurement: procedures table with EFCA's own status, calls for interest,
no job vacancies, one row per reference.

API audit, 30 Sep 2026 ("Walk · EFCA"). Fixtures are the live pages saved that day.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "efca"
NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def _procedures():
    return ap._efca_rows((FIX / "procedures.html").read_text(), ref_field="field-number",
                         deadline_field="field-deadline", status_field="field-opencall-status")


def test_procedures_table_has_references_deadlines_and_status():
    rows = _procedures()
    assert len(rows) == 34
    assert all(r["reference"] for r in rows)
    # One joint procedure led by EU-OSHA has no deadline in EFCA's table (30 Sep 2026).
    assert [r["reference"] for r in rows if not r["deadline"]] == ["OSHA/2024/OP/0023"]
    assert {r["status_raw"] for r in rows} <= {"Open", "Closed", "Cancelled", "Unsuccessful"}
    assert len({r["reference"] for r in rows}) == 34


def test_calls_table_reads_the_call_number_column():
    rows = ap._efca_rows((FIX / "calls.html").read_text(), ref_field="field-expression-interest-number",
                         deadline_field="field-deadline-for-applications", status_field=None)
    assert len(rows) == 6 and all("/CEI/" in r["reference"] for r in rows)


def test_the_vacancies_page_is_not_a_source():
    """/en/content/open-calls-tender lists job vacancies since 2026; no EFCA reader reads it."""
    src = (Path(__file__).resolve().parents[1] / "services" / "scrapers" / "agency_procurement.py").read_text()
    assert "open-calls-tender" not in src.split("# EFCA")[1].split("# --- EFSA")[0].replace("# ", "").split("_EFCA =")[1]


def test_status_follows_efca_and_the_deadline():
    base = {"title": "t", "url": "u", "reference": "R"}
    ahead = datetime(2026, 10, 30, tzinfo=timezone.utc)
    assert ap._efca_item({**base, "deadline": ahead, "status_raw": "Open"}, None, item_type="tender", now=NOW).extras["status"] == "open"
    assert ap._efca_item({**base, "deadline": ahead, "status_raw": "Closed"}, None, item_type="tender", now=NOW).extras["status"] == "closed"
    assert ap._efca_item({**base, "deadline": datetime(2025, 9, 15, tzinfo=timezone.utc), "status_raw": "Open"}, None, item_type="tender", now=NOW).extras["status"] == "closed"


def test_detail_links_the_notice_and_dates_the_item(monkeypatch):
    monkeypatch.setattr(ap, "_get_ok", lambda url: (FIX / "detail_op0005.html").read_text())
    monkeypatch.setattr(ap, "_ft_notice_date", lambda n: datetime(2025, 7, 23, tzinfo=timezone.utc)
                        if n == "d33f3a8c-b6a8-4000-a7d6-7984c3d1b630-CN" else None)
    row = next(r for r in _procedures() if r["reference"] == "EFCA/2025/OP/0005")
    item = ap._efca_item(row, ap._efca_detail(row["url"]), item_type="tender", now=NOW)
    assert item.document_date == datetime(2025, 7, 23, tzinfo=timezone.utc)
    assert item.body_txt.splitlines()[1].startswith("Type ")   # breadcrumb trimmed
