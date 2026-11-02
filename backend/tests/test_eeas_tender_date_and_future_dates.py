"""An EEAS tender is dated by the line under its title; a call or tender is never dated ahead (2 Nov 2026,
register O136, O138)."""
import pathlib
import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from ingest_ft_news_events import normalise  # noqa: E402
from scripts.sync_economy import _reject_future_news_date  # noqa: E402
from services.scrapers.economy_eeas import tender_page_date  # noqa: E402

TODAY = date(2026, 11, 2)
TANZANIA = ("Call for expression of interest: Printer Maintenance for the EU Delegation to Tanzania\n20.10.2026\n"
            "The Delegation is launching a procurement procedure.\nThe estimated launch of procurement procedure – 03/11/2026.")


def test_the_line_under_the_title_not_a_later_date_in_the_text():
    assert tender_page_date(TANZANIA, None, TODAY) == datetime(2026, 10, 20, tzinfo=timezone.utc)
    shared = "Share\nFacebook\nLinkedIn\nPRINT\nTender for legal services\n13.10.2026\nDeadline to express your interest: 28/10/2026"
    assert tender_page_date(shared, datetime(2026, 10, 28, tzinfo=timezone.utc), TODAY) == datetime(2026, 10, 13, tzinfo=timezone.utc)


def test_a_date_ahead_or_the_deadline_on_that_line_is_no_date():
    ahead = "Provision of travel agency services\n27.11.2026\nDeadline for submission of tenders: 27/11/2026."
    assert tender_page_date(ahead, None, TODAY) is None
    same = "Provision of travel agency services\n10.10.2026\nDeadline for submission of tenders: 10/10/2026."
    assert tender_page_date(same, datetime(2026, 10, 10, tzinfo=timezone.utc), TODAY) is None


def test_no_line_no_date():
    assert tender_page_date("A tender. The deadline is 27/11/2026.", None, TODAY) is None
    assert tender_page_date(None, None, TODAY) is None


def test_the_store_nulls_a_future_date_on_a_call_or_tender_and_keeps_an_event():
    for item_type in ("call", "tender", "grant", "eoi_call", "framework"):
        it = SimpleNamespace(body_code="hadea", item_type=item_type, title="T", document_date=datetime(2027, 6, 3, tzinfo=timezone.utc))
        _reject_future_news_date(it)
        assert it.document_date is None, item_type
    event = SimpleNamespace(body_code="eeas", item_type="event", title="T", document_date=datetime(2027, 1, 27, tzinfo=timezone.utc))
    _reject_future_news_date(event)
    assert event.document_date is not None
    past = SimpleNamespace(body_code="hadea", item_type="call", title="T", document_date=datetime(2026, 10, 29, tzinfo=timezone.utc))
    _reject_future_news_date(past)
    assert past.document_date is not None


def test_a_portal_event_whose_url_field_holds_the_word_uri_takes_its_details_link():
    details = "https://research-innovation-community.ec.europa.eu/events/2VgQVkhSe14gr3SDySNP6K/overview"
    out = normalise("events", {"metadata": {"title": ["Horizon Implementation Day"], "url": ["uri"], "detailsUrl": [details]}})
    assert out["public_url"] == details
    good = "https://ec.europa.eu/events/1"
    out = normalise("events", {"metadata": {"title": ["Day"], "url": [good], "detailsUrl": [details]}})
    assert out["public_url"] == good
    assert normalise("events", {"metadata": {"title": ["Day"], "url": ["uri"]}}) is None


OUTAGE = "Server inaccessibility\nbg\nСървърът е временно недостъпен\nИзвиняваме се.\ncs\nServer je dočasně nedostupný"
SHARE = "Share\nFacebook\nLinkedIn\nX\nWhatsapp\nE-mail\nGmail\nPrint\nTypepad\nMastodon\nBlueSky\nPRINT\n"
TENDER = "Tender for legal services at the Delegation\n13.10.2026\nThe Delegation is launching a call for tenders for legal services. " * 1


def _repair(**row):
    from scripts.repair_eeas_bodies_and_dates import repaired
    return repaired({"item_type": "tender", "deadline": None, "document_date": None, **row}, TODAY)


def test_repair_an_outage_text_with_the_real_page_in_the_html_comes_back_from_it():
    html = "<main><article><h1>Tender for legal services at the Delegation</h1><p>13.10.2026</p><p>" + "The Delegation is launching a call for tenders. " * 12 + "</p></article></main>"
    out = _repair(body_txt=OUTAGE, body_html=html)
    assert "Сървърът" not in (out["body_txt"] or "") and "The Delegation is launching" in out["body_txt"]


def test_repair_both_outage_both_go_and_a_wrong_date_with_them():
    out = _repair(body_txt=OUTAGE, body_html="<h1>Server inaccessibility</h1><p>" + OUTAGE + "</p>",
                  document_date=datetime(2026, 10, 30, tzinfo=timezone.utc))
    assert out == {"body_txt": None, "body_html": None, "document_date": None}


def test_repair_real_text_with_an_outage_html_keeps_the_text():
    out = _repair(item_type="topic", body_txt="Armenia and the EU\n" + "Relations are built on partnership. " * 10,
                  body_html="<h1>Server inaccessibility</h1><p>" + OUTAGE + "</p>")
    assert out == {"body_html": None}


def test_repair_strips_the_share_menu_and_nothing_else_and_dates_from_the_line():
    html = ('<main><div class="text-end content-options"><div class="content-share"><ul class="wt-ecl-social-media-share__list">'
            '<li><a href="#"><svg><path d="M0 0"/></svg>Facebook</a></li></ul></div></div><p>The Delegation is launching a call.</p></main>')
    out = _repair(body_txt=SHARE + TENDER, body_html=html, document_date=datetime(2026, 10, 28, tzinfo=timezone.utc))
    assert out["body_txt"] == TENDER.strip()
    assert "Facebook" not in out["body_html"] and "<svg" not in out["body_html"] and "launching a call" in out["body_html"]
    assert out["document_date"] == datetime(2026, 10, 13, tzinfo=timezone.utc)


def test_repair_leaves_a_clean_right_row_alone():
    assert _repair(body_txt=TENDER, body_html="<p>The Delegation is launching a call.</p>",
                   document_date=datetime(2026, 10, 13, 9, tzinfo=timezone.utc)) == {}


def test_a_topic_titled_by_its_code_takes_the_calls_title_and_keeps_the_code():
    from ingest_funding_sedia import named_title
    call = "Call for proposals on the fight against corruption"
    assert named_title("CORRUPT", call) == f"{call} (CORRUPT)"
    assert named_title("AGRIP-SIMPLE-2026-IM-FRESH-FV", call) == f"{call} (AGRIP-SIMPLE-2026-IM-FRESH-FV)"
    assert named_title("Support for National Contact Points", call) == "Support for National Contact Points"
    assert named_title("CORRUPT", None) == "CORRUPT"
    assert named_title("CHIPS-2025-SG", "CHIPS-2025-SG") == "CHIPS-2025-SG"      # the call is titled by a code too
    assert named_title("CEEP", "Call on community engagement (CEEP)") == "Call on community engagement (CEEP)"
