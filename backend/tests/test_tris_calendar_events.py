"""TRIS standstill deadlines in My EU Calendar (24 Sep 2026)."""
from datetime import date

from services.scrapers.eu_calendar_sync_service import tris_event

ROW = {
    "notification_number": "2026/0266/ES", "notifying_country": "ES",
    "title": "Draft Royal Decree regulating textile and footwear products and the management of their waste.",
    "products_or_services": "Textile and non-textile products, footwear.",
    "standstill_until": date(2026, 9, 28), "source_url": "https://technical-regulation-information-system.ec.europa.eu/en/notification/27983",
    "policy_areas": [], "opinions": 1, "comments": 1,
}


def test_event_is_keyed_on_the_notification_so_an_extension_moves_it():
    e = tris_event(ROW, date(2026, 9, 24))
    assert e["external_id"] == "tris_2026/0266/ES" and e["source"] == "tris"
    later = tris_event({**ROW, "standstill_until": date(2026, 10, 28)}, date(2026, 9, 24))
    assert later["external_id"] == e["external_id"] and later["start_date"] == date(2026, 10, 28)


def test_content_is_plain_and_complete():
    e = tris_event(ROW, date(2026, 9, 24))
    assert e["event_type"] == "tris_standstill" and e["institution"] == "COMMISSION"
    assert e["title"].startswith("TRIS standstill ends: Spain, Draft Royal Decree")
    assert "28 September 2026" in e["description"] and "Directive (EU) 2015/1535" in e["description"]
    assert ".." not in e["description"] and "—" not in e["description"] + e["title"]
    assert "Detailed opinion(s) received: 1" in e["description"]
    assert e["policy_areas"] == ["Single Market"] and e["status"] == "scheduled"


def test_a_passed_standstill_is_completed_never_adopted():
    e = tris_event(ROW, date(2026, 10, 5))
    assert e["status"] == "completed" and "adopted" not in e["description"].lower()
