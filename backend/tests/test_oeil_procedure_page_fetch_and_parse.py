"""OEIL procedure pages: parse the real tables, and never turn "fetched nothing"
into "nothing changed".

Regression tests for the 15 Sep 2026 fix. `update_carriage_statuses_from_oeil.py
--refs '2026/0074(COD)'` ran and changed nothing while OEIL showed a rapporteur,
two opinion committees, two key events and a forecast. The page was reachable
all along (oeil.secure.* 307s to oeil.europarl.europa.eu, which serves the full
server-rendered page); the parser read one guessed event, no forecast, no
opinion committee, and every MEP link on the page as a shadow of the lead.

Fixtures are real OEIL pages fetched 15 Sep 2026, trimmed to the <title> and
the main content column (site chrome and scripts dropped). No network.
"""
import asyncio
import pathlib
import sys
from datetime import date

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from services.scrapers.oeil_scraper import (  # noqa: E402
    OEILFetchError, OEILScraper, classify_oeil_response, looks_like_procedure_page,
)
from services.scrapers.oeil_procedure_parser import (  # noqa: E402
    advance_status, carriage_fields_from_procedure, infer_carriage_status,
)
from services.scrapers.waf_browser_fetcher import FetchResult  # noqa: E402

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "oeil"


def _page(name: str) -> str:
    return (FIX / f"procedure_{name}.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def scraper():
    return OEILScraper(use_coordinator=False)


# ---------------------------------------------------------------------------
# Parsing a fetched page
# ---------------------------------------------------------------------------

def test_eu_inc_page_parses_into_expected_fields(scraper):
    p = scraper.parse_procedure_html(_page("2026_0074_cod"), "2026/0074(COD)", "u")

    assert p.basic_info.title == "28th regime corporate legal framework – EU Inc."
    assert p.basic_info.status == "Awaiting committee decision"

    cr = p.key_players.committee_responsible
    assert cr.code == "JURI"
    assert cr.rapporteur.name == "REPASI René"
    assert cr.rapporteur.political_group == "S&D"
    assert cr.date_announced == date(2026, 4, 23)
    # 8 shadows, and the opinion rapporteurs are NOT among them
    shadows = [m.name for m in cr.shadow_rapporteurs]
    assert len(shadows) == 8
    assert "VOSS Axel" in shadows and "SYPNIEWSKI Marcin" in shadows
    assert "LALUCQ Aurore" not in shadows and "DANIELSSON Johan" not in shadows
    groups = {m.name: m.political_group for m in cr.shadow_rapporteurs}
    assert groups["CANFIN Pascal"] == "Renew"
    assert groups["LAGODINSKY Sergey"] == "Greens/EFA"
    assert groups["SAEIDI Arash"] == "The Left"

    ops = {c.code: c for c in p.key_players.committees_opinion}
    assert ops["ECON"].rapporteur.name == "LALUCQ Aurore"
    assert ops["ECON"].date_announced == date(2026, 5, 18)
    assert ops["EMPL"].rapporteur.name == "DANIELSSON Johan"
    assert ops["EMPL"].date_announced == date(2026, 5, 13)
    assert ops["BUDG"].role.endswith("_declined")

    events = [(e.date, e.event_type) for e in p.key_events.events]
    assert events == [
        (date(2026, 3, 18), "Legislative proposal published"),
        (date(2026, 5, 18), "Committee referral announced in Parliament, 1st reading"),
    ]
    assert p.key_events.events[0].description == "COM(2026)0321"

    fcs = [(f.forecast_date, f.event_type, f.location) for f in p.forecasts.forecasts]
    assert fcs == [(date(2026, 10, 19), "Indicative plenary sitting date, 1st reading", "Plenary")]

    assert p.key_players.commission_dg == "Justice and Consumers"
    assert p.key_players.commissioner == "MCGRATH Michael"


def test_carriage_fields_for_eu_inc(scraper):
    p = scraper.parse_procedure_html(_page("2026_0074_cod"), "2026/0074(COD)", "u")
    f = carriage_fields_from_procedure(p)
    assert f["lead_committee"] == "JURI"
    assert f["rapporteur_name"] == "REPASI René"
    assert f["rapporteur_appointed"] == date(2026, 4, 23)
    assert f["opinion_committees"] == ["ECON", "EMPL"]      # BUDG declined
    assert f["committees"] == ["JURI", "ECON", "EMPL"]
    assert len(f["oeil_key_events"]) == 2
    assert f["oeil_forecasts"] == [
        {"date": "2026-10-19", "event_type": "Indicative plenary sitting date, 1st reading"}]


def test_declined_opinions_are_not_opinion_committees(scraper):
    p = scraper.parse_procedure_html(_page("2025_0358_cod"), "2025/0358(COD)", "u")
    f = carriage_fields_from_procedure(p)
    assert f["lead_committee"] == "ITRE"
    assert f["rapporteur_name"] == "HEINÄLUOMA Eero"
    assert f["opinion_committees"] == ["IMCO", "JURI"]     # LIBE and BUDG declined
    assert f["oeil_forecasts"] == []                        # page has no forecast section


def test_every_key_event_row_is_kept_even_on_the_same_day(scraper):
    p = scraper.parse_procedure_html(_page("2025_0207_cod"), "2025/0207(COD)", "u")
    types = [e.event_type for e in p.key_events.events]
    assert len(types) == 8
    assert types.count("Decision by Parliament, 1st reading") == 1
    assert any(t.startswith("Matter referred back") for t in types)


# ---------------------------------------------------------------------------
# Status inference
# ---------------------------------------------------------------------------

def test_parliament_vote_referred_back_is_not_completed(scraper):
    p = scraper.parse_procedure_html(_page("2025_0207_cod"), "2025/0207(COD)", "u")
    inferred = infer_carriage_status([e.event_type for e in p.key_events.events], p.basic_info.status)
    assert inferred == "close_to_adoption"


def test_status_rules():
    assert infer_carriage_status(["Legislative proposal published"]) == "tabled"
    assert infer_carriage_status(["Vote in committee, 1st reading"]) == "close_to_adoption"
    assert infer_carriage_status(["Act adopted by Council after Parliament's 1st reading"]) == "completed"
    assert infer_carriage_status(["Decision by Parliament, 1st reading"], "Procedure completed") == "completed"
    assert infer_carriage_status(["Final act published in Official Journal"]) == "adopted"
    assert infer_carriage_status(["Resumption of business"]) is None


def test_status_only_advances():
    assert advance_status("tabled", "close_to_adoption") == "close_to_adoption"
    assert advance_status("close_to_adoption", "tabled") is None
    assert advance_status("close_to_adoption", "close_to_adoption") is None
    assert advance_status("blocked", "adopted") is None
    assert advance_status("withdrawn", "tabled") is None


# ---------------------------------------------------------------------------
# Fetch classification and the browser fallback
# ---------------------------------------------------------------------------

REF = "2026/0074(COD)"
URL = f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={REF}"
NGINX_307 = ("<html>\n<head><title>307 Temporary Redirect</title></head>\n<body>\n"
             "<center><h1>307 Temporary Redirect</h1></center>\n<hr><center>nginx</center>\n"
             "</body>\n</html>\n")


def test_classification():
    full = _page("2026_0074_cod")
    assert looks_like_procedure_page(full)
    assert classify_oeil_response(200, full) == "ok"
    assert classify_oeil_response(202, "") == "waf"
    assert classify_oeil_response(403, "denied") == "waf"
    assert classify_oeil_response(200, "") == "waf"
    assert classify_oeil_response(200, "<html><body>Please enable JavaScript</body></html>") == "waf"
    # the measured 15 Sep answer: a host move to the same procedure page
    assert classify_oeil_response(307, NGINX_307, URL) == "redirect"
    # a redirect anywhere else is a challenge / login bounce
    assert classify_oeil_response(307, NGINX_307, "https://waf.example.eu/challenge?x=1") == "waf"
    assert classify_oeil_response(302, "", None) == "waf"
    assert classify_oeil_response(404, "{}") == "not_found"
    assert classify_oeil_response(500, "") == "error"


class _FakeBrowser:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def fetch(self, url):
        self.calls.append(url)
        return self.result

    async def close(self):
        pass


def _scripted(scraper, answers):
    """Replace the raw HTTP GET with a scripted sequence of answers."""
    seq = list(answers)
    seen = []

    async def fake(url):
        seen.append(url)
        return seq.pop(0)

    scraper._http_get_no_redirect = fake
    return seen


def _fresh():
    return OEILScraper(use_coordinator=False, allow_browser_fallback=True)


@pytest.mark.parametrize("answer", [
    (307, NGINX_307, "https://challenge.example.eu/verify"),
    (202, "", None),
    (403, "Forbidden", None),
    (200, "", None),
    (200, "<html><body>loading...</body></html>", None),
])
def test_walled_or_empty_answers_fall_back_to_the_browser(answer):
    s = _fresh()
    _scripted(s, [answer])
    fake = _FakeBrowser(FetchResult(url=URL, nav_status=200, text="x" * 500, html=_page("2026_0074_cod")))
    s._browser = fake
    proc, page = asyncio.run(s.get_procedure_with_page(REF))
    assert fake.calls == [URL]
    assert page.route == "browser"
    assert proc.key_players.committee_responsible.rapporteur.name == "REPASI René"
    assert s.fetch_stats["ok_browser"] == 1


def test_host_move_is_followed_without_the_browser():
    s = _fresh()
    secure = URL.replace("oeil.europarl", "oeil.secure.europarl")
    s.PROCEDURE_URL = secure.split("?")[0]
    seen = _scripted(s, [(307, NGINX_307, URL), (200, _page("2026_0074_cod"), None)])
    fake = _FakeBrowser(FetchResult(url=URL, error="must not be called"))
    s._browser = fake
    proc, page = asyncio.run(s.get_procedure_with_page(REF))
    assert seen == [secure, URL]
    assert fake.calls == []
    assert page.route == "http"
    assert len(proc.key_events.events) == 2


def test_browser_that_also_gets_nothing_is_a_counted_error():
    s = _fresh()
    _scripted(s, [(202, "", None)])
    s._browser = _FakeBrowser(FetchResult(url=URL, nav_status=202, text="", html="<html></html>"))
    with pytest.raises(OEILFetchError) as exc:
        asyncio.run(s.get_procedure_with_page(REF))
    assert exc.value.route == "browser"
    assert s.fetch_stats["failed"] == 1


def test_not_found_does_not_launch_a_browser():
    s = _fresh()
    _scripted(s, [(404, '{"status":404}', None)])
    fake = _FakeBrowser(FetchResult(url=URL, error="must not be called"))
    s._browser = fake
    with pytest.raises(OEILFetchError):
        asyncio.run(s.get_procedure_with_page(REF))
    assert fake.calls == []


def test_disabled_fallback_raises_instead_of_returning_empty():
    s = OEILScraper(use_coordinator=False)      # the default: request paths never launch Chromium
    _scripted(s, [(202, "", None)])
    with pytest.raises(OEILFetchError):
        asyncio.run(s.get_procedure_with_page(REF))
