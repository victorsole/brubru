"""EU-OSHA calls for tender: any heading level, status from the tab, date = publication (15 Oct 2026).

The title moved from an <h2> to an <h4> and eleven runs parsed nothing; every call was
stored "Open" though the page splits open, ongoing and archived calls into tabs; and the
<time> before each title, the publication date, was written into the body as the deadline."""
from __future__ import annotations

from services.scrapers.agency_procurement import _parse_eu_osha_views


def _row(href: str, title: str, day: str) -> str:
    return (f'<div class="revamp-row no-flex"><div class="views-field views-field-field-publication-date">'
            f'<div class="field-content"><time datetime="{day}T19:00:00Z" class="datetime">x</time></div></div>'
            f'<div class="views-field views-field-title"><h4 class="field-content">'
            f'<a href="/en/about-eu-osha/procurement/call-tender/{href}" hreflang="en">{title}</a></h4></div></div>')


PAGE = ('<div class="view view-calls view-display-id-block_open_calls">' + _row("a-open", "OSHA/2026/MVP/0034", "2026-10-09")
        + '</div><div class="view view-calls view-display-id-block_ongoing_calls">' + _row("b-ongoing", "OSHA/2026/OP/0018", "2026-08-04")
        + "</div>")


def test_each_call_takes_its_tab_status_and_publication_date():
    items = _parse_eu_osha_views(PAGE, "https://osha.europa.eu", body_code="eu_osha",
                                 item_type="tender", source_kind="eu_osha_procurement")
    assert [i.summary for i in items] == ["Open", "Closed for submissions (ongoing)"]
    assert [i.document_date.date().isoformat() for i in items] == ["2026-10-09", "2026-08-04"]
    assert "Published: 2026-10-09" in items[0].body_txt and "Deadline" not in items[0].body_txt
