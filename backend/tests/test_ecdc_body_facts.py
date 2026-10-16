"""An ECDC body states the vetted publication date and plain links (16 Oct 2026).

API audit, step 2 (ECDC, 174 tenders read in full): 28 bodies said
"Published: 2017-07-27" (the site-migration day the date field already rejects) and
3 bodies carried Funding & Tenders links with "&amp;" copied from the HTML.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "ecdc"
NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


def _row(**kw):
    row = {"title": "Interior Design consultancy", "url": "https://www.ecdc.europa.eu/x",
           "reference": "NP/2016/RMC/7913", "kind": "ex-ante publicity",
           "deadline": datetime(2016, 8, 3, 14, 0, tzinfo=timezone.utc)}
    row.update(kw)
    return row


def test_body_never_states_a_rejected_publication_date(monkeypatch):
    monkeypatch.setattr(ap, "_ecdc_get", lambda url: (FIX / "detail_np2016_migrated.html").read_text())
    detail = ap._ecdc_detail("https://www.ecdc.europa.eu/x")
    assert detail["published"] is not None and detail["published"].year == 2017   # the stamp is on the page
    item = ap._ecdc_item(_row(), detail, NOW)
    assert item.document_date is None
    assert "Published:" not in item.body_txt and "2017-07-27" not in item.body_txt
    assert "Deadline: 2016-08-03" in item.body_txt


def test_the_migration_day_is_never_a_date_even_before_a_deadline(monkeypatch):
    """5778517 closed on 12 Aug 2017, after the 27 Jul 2017 stamp, and kept the stamp."""
    monkeypatch.setattr(ap, "_ecdc_get", lambda url: (FIX / "detail_np2016_migrated.html").read_text())
    detail = ap._ecdc_detail("https://www.ecdc.europa.eu/x")
    item = ap._ecdc_item(_row(deadline=datetime(2017, 8, 12, 14, 0, tzinfo=timezone.utc)), detail, NOW)
    assert item.document_date is None and "Published:" not in item.body_txt


def test_body_states_the_date_it_serves(monkeypatch):
    monkeypatch.setattr(ap, "_ecdc_get", lambda url: (FIX / "detail_op0018_no_last_updated.html").read_text())
    detail = ap._ecdc_detail("https://www.ecdc.europa.eu/x")
    item = ap._ecdc_item(_row(deadline=datetime(2027, 1, 1, tzinfo=timezone.utc)), detail, NOW)
    assert item.document_date == detail["published"]
    assert f"Published: {detail['published'].date().isoformat()}" in item.body_txt


def test_links_are_unescaped(monkeypatch):
    # The reader's region: from <h1> to </article>, description after the meta <ul>.
    page = ('<html><head><meta property="article:published_time" content="2026-09-18T08:41:43+02:00"/>'
            '</head><body><article><h1>Support to AMR surveillance</h1><ul><li>Reference</li></ul>'
            '<p>Support to AMR surveillance.</p>'
            '<p><a href="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/'
            'tender-details/abc-CN?isExactMatch=true&amp;order=DESC&amp;pageNumber=1">Portal</a></p>'
            '</article></body></html>')
    monkeypatch.setattr(ap, "_ecdc_get", lambda url: page)
    detail = ap._ecdc_detail("https://www.ecdc.europa.eu/x")
    assert any("isExactMatch=true&order=DESC&pageNumber=1" in u for u in detail["links"])
    assert not any("&amp;" in u for u in detail["links"])
    item = ap._ecdc_item(_row(deadline=datetime(2026, 10, 26, tzinfo=timezone.utc)), detail, NOW)
    assert "&amp;" not in item.body_txt
    assert "&amp;amp;" not in item.body_html          # escaped once, for HTML
