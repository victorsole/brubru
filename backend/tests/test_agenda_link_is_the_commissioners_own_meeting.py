"""A Commissioner's meeting is linked to its own page, never to a colleague's.

18 Oct 2026: four of Commissioner Albuquerque's meetings of 20 Oct carried the page of
"Commissioner Šuica meets with Ms Fabienne Keller, Member of the European Parliament", and
three older events had the same fault (Albuquerque -> Várhelyi, Albuquerque -> Šuica,
Brunner -> Lahbib). The live fallback reads the Commission's GLOBAL feed and matched on
word overlap; two "meets ... member of the European Parliament" titles share 6 of 10 words,
all boilerplate, which is exactly the 0.6 threshold.

Now the score counts distinctive words only (names, subjects), and the global feed only
offers entries that name the Commissioner. The RSS below is the feed's own shape.
"""
import importlib
import pathlib
import sys
from datetime import date

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
mod = importlib.import_module("services.api_clients.commissioner_agenda_client")
C = mod.CommissionerAgendaClient
Item = mod.AgendaItem

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>2026-10-19 - Commissioner Šuica meets with Ms Fabienne Keller, Member of the European Parliament</title>
<link>https://commission.europa.eu/calendar/commissioner-suica-meets-ms-fabienne-keller-member-european-parliament_en</link></item>
<item><title>2026-10-19 - Commissioner Albuquerque meets Mr Markus Ferber, member of the European Parliament</title>
<link>https://commission.europa.eu/calendar/commissioner-albuquerque-meets-mr-markus-ferber-member-european-parliament_en</link></item>
<item><title>2026-10-20 - Executive Vice-President Fitto attends the informal meeting of ministers responsible for cohesion policy and</title>
<link>https://commission.europa.eu/calendar/executive-vice-president-fitto-attends-informal-meeting-ministers-cohesion_en</link></item>
</channel></rss>"""


def _item(day, title):
    return Item(date=date(2026, 10, day), title=title, location=None, detail_url="")


def test_a_colleagues_meeting_with_the_same_boilerplate_is_not_matched():
    entries = C._build_rss_url_entries(RSS)
    it = _item(20, "Commissioner Albuquerque meets Ms Stephanie Yon-Courtin, member of the European Parliament")
    assert C._lookup_rss_url(entries, it, surname="albuquerque") == ""
    # Even without the surname filter, boilerplate alone no longer scores.
    assert C._lookup_rss_url(entries, it) == ""


def test_the_commissioners_own_meeting_is_matched():
    entries = C._build_rss_url_entries(RSS)
    it = _item(20, "Commissioner Albuquerque meets Mr Markus Ferber, member of the European Parliament")
    assert C._lookup_rss_url(entries, it, surname="albuquerque").endswith("markus-ferber-member-european-parliament_en")


def test_a_truncated_feed_title_still_matches():
    entries = C._build_rss_url_entries(RSS)
    it = _item(21, "Executive Vice-President Fitto attends the informal meeting of ministers responsible for "
                   "cohesion policy and urban development")
    assert C._lookup_rss_url(entries, it, surname="fitto").endswith("ministers-cohesion_en")


def test_the_global_feed_only_offers_the_commissioners_entries():
    entries = C._build_rss_url_entries(RSS)
    it = _item(19, "Commissioner Šuica meets with Ms Fabienne Keller, Member of the European Parliament")
    assert C._lookup_rss_url(entries, it, surname="albuquerque") == ""
    assert C._lookup_rss_url(entries, it, surname="suica").endswith("fabienne-keller-member-european-parliament_en")


def test_fetch_agenda_passes_the_surname():
    import inspect
    assert "surname=" in inspect.getsource(C.fetch_agenda)
