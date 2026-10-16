"""A TRIS notification's title is its own English title, never a section heading (16 Oct 2026).

43 notifications were titled "Stakeholders Contributions" and 129 kept the notifying
country's language after TRIS published the English title."""
from __future__ import annotations

from bs4 import BeautifulSoup

from scripts.refresh_tris_titles import needs_title
from services.scrapers.dg_grow.tris_scraper import TRISScraper

PAGE = """<html><body>
<h1 class="ecl-page-header__title">Notification Detail</h1>
<h2 class="ecl-u-type-color-primary">{title}</h2>
<div class="ecl-row"><div class="ecl-col-3">Notification Number:</div><div class="ecl-col-9">2026/0552/AT (Austria)</div></div>
<div class="ecl-row"><div class="ecl-col-3">Date received:</div><div class="ecl-col-9">12/10/2026</div></div>
<h3>Message</h3><h3>Disclosed messages</h3>
<h2 class="ecl-u-type-heading-2">Stakeholders Contributions</h2>
<h2 class="ecl-site-footer__title">Internal Market, Industry, Entrepreneurship and SMEs</h2>
</body></html>"""


def _parse(title):
    return TRISScraper()._parse_notification_detail(BeautifulSoup(PAGE.format(title=title), "html.parser"), 29401)


def test_the_page_title_heading_is_the_title():
    got = _parse("Airworthiness Notice No. 40B – Inspection of On-Board Equipment")
    assert got["title"] == "Airworthiness Notice No. 40B – Inspection of On-Board Equipment"
    assert got["reference"] == "2026/0552/AT"


def test_a_missing_title_heading_never_falls_to_a_section_heading():
    got = _parse("")
    assert got["title"] != "Stakeholders Contributions"
    assert "Internal Market" not in got["title"]


def test_which_stored_titles_are_re_read():
    assert needs_title("Stakeholders Contributions")
    assert needs_title("Lufttüchtigkeitshinweis Nr. 40B - Überprüfung der Bordausrüstung")
    assert needs_title("TRIS Notification 2026/0552/AT")
    assert not needs_title("Airworthiness Notice No. 40B – Inspection of On-Board Equipment")
    assert not needs_title("Draft Order prohibiting the export of certain medicinal products")
