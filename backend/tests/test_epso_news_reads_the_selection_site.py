"""EPSO news is read from the selection site (15 Oct 2026).

eu-careers.europa.eu became a Europa-platform careers site in October 2026: its /en/news
listing answers 404, so the job ran six times storing nothing while EPSO published. The
listing (same Drupal rows) now lives on selection.eu-careers.europa.eu, and the old item
paths redirect there."""
from __future__ import annotations

from types import SimpleNamespace

from services.scrapers import economy_epso as epso

LISTING = """<div class="view-content">
<div class="views-row"><div class="views-field-title"><a href="/en/news/clarification-education-requirement/20909">Clarification of education requirement</a></div>
<time datetime="2026-10-14T15:39:00Z">14/10/2026</time></div>
<div class="views-row"><div class="views-field-title"><a href="/en/about-epso/who-we-are">Not news</a></div></div>
</div>"""


def test_the_listing_is_read_from_the_selection_host(monkeypatch):
    asked = []
    monkeypatch.setattr(epso, "http_get", lambda url, *a, **k: asked.append(url) or SimpleNamespace(text=LISTING))
    items = epso.ingest_epso_news(fetch_bodies=False)
    assert asked == ["https://selection.eu-careers.europa.eu/en/news"]
    assert [i.public_url for i in items] == [
        "https://selection.eu-careers.europa.eu/en/news/clarification-education-requirement/20909"]
    assert items[0].document_date.date().isoformat() == "2026-10-14"
