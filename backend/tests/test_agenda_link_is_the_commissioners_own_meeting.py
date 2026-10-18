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


# 18 Oct 2026, afternoon rerun: two more faults behind the same field.
# (1) The persisted links carry the feed's category code ("0001"), never the COM_... leader
#     id, so the stored-link lookup filtered by leader id found nothing.
# (2) Scored on distinctive words but counting the Commissioner's own surname, "Visegrad
#     energy ministers meeting" matched "Energy Solutions event"; scored against the longer
#     title, a truncated feed title found nothing.
class _Rows:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return self.rows


class _DB:
    def __init__(self, rows): self.rows = rows; self.params = None
    def execute(self, sql, params): self.params = params; return _Rows(self.rows)


STORED = [
    (date(2026, 10, 18), "commissioner jørgensen participates in the energy solutions event with green power denmark",
     "https://commission.europa.eu/calendar/commissioner-jorgensen-participates-energy-solutions-event-green-power-denmark_en"),
    (date(2026, 10, 18), "commissioner jørgensen participates in the visegrad energy ministers meeting",
     "https://commission.europa.eu/calendar/commissioner-jorgensen-participates-visegrad-energy-ministers-meeting_en"),
    (date(2026, 10, 18), "commissioner jørgensen meets with the buildings for future a",
     "https://commission.europa.eu/calendar/commissioner-jorgensen-meets-buildings-future-association_en"),
]


def test_stored_links_are_found_by_surname_and_each_event_gets_its_own():
    db = _DB(STORED)
    items = [_item(19, "Commissioner Jørgensen participates in the Visegrad Energy Ministers meeting"),
             _item(19, "Commissioner Jørgensen meets with the Buildings for Future association")]
    out = C._lookup_db_urls(items, "COM_00006AAAF26A", db, surname="jørgensen")
    assert db.params["surname_like"] == "% jørgensen %"
    got = {k[1]: v for k, v in out.items()}
    assert got[mod._norm(items[0].title)].endswith("visegrad-energy-ministers-meeting_en")
    assert got[mod._norm(items[1].title)].endswith("buildings-future-association_en")


def test_the_surname_alone_does_not_make_two_events_match():
    assert mod._title_score(
        mod._norm("Commissioner Jørgensen participates in the Visegrad Energy Ministers meeting"),
        "commissioner jørgensen participates in the energy solutions event with green power denmark",
        frozenset({"jørgensen"})) == 0.0
