"""/news reads EPSO from its selection site and no longer asks EBA's blocked feed (15 Oct 2026).

EPSO's old feed stayed empty after its site moved, so /news showed no EPSO item while EPSO
published on 12-14 October; EBA answers 403 to scripts and browsers alike and reaches /news
through Brubru's own store."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.argv = sys.argv[:1]
import scrape_eu_news as news  # noqa: E402


def test_epso_is_read_from_the_selection_listing():
    epso = [p for p in news.PORTALS if p["source"] == "EPSO"]
    assert [p["url"] for p in epso] == ["https://selection.eu-careers.europa.eu/en/news"]
    assert epso[0].get("type", "html") == "html"


def test_no_portal_asks_a_dead_or_blocked_feed():
    urls = {p["url"] for p in news.PORTALS}
    assert "https://eu-careers.europa.eu/node/2/rss_en" not in urls
    assert "https://www.eba.europa.eu/rss.xml" not in urls
