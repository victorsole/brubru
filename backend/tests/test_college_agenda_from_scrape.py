"""College meetings take their planned items from the newest scraped tentative
agenda, not a hand-kept copy (24 Sep 2026: the copy had the Enlargement package
under 20 October; SEC(2026)2578 lists it for 28 October)."""
from datetime import date

from services.scrapers.ec_college_scraper import agenda_from_items, describe_meeting

ITEMS = [
    {"meeting_date_provisional": "20/10/2026", "item": "2027 Commission work programme", "responsible": "PRESIDENT", "sub_items": []},
    {"meeting_date_provisional": "28/10/2026", "item": "Enlargement package", "responsible": "PRESIDENT", "sub_items": []},
    {"meeting_date_provisional": "28/10/2026", "item": "Border and migration package", "responsible": "VIRKKUNEN",
     "sub_items": ["Strengthening Frontex", "Digitalisation of the return process"]},
    {"meeting_date_provisional": "6/10/2026", "item": "European product package", "responsible": "SÉJOURNÉ", "sub_items": []},
    {"meeting_date_provisional": "tbc", "item": "Undated item", "responsible": "X", "sub_items": []},
]


def test_items_land_on_their_own_meeting():
    a = agenda_from_items(ITEMS, "SEC(2026)2578", "14 September 2026")
    assert [i["item"] for i in a["meetings"]["2026-10-28"]][0] == "Enlargement package"
    assert [i["item"] for i in a["meetings"]["2026-10-20"]] == ["2027 Commission work programme"]
    assert a["meetings"]["2026-10-06"][0]["responsible"] == "Séjourné"
    assert "tbc" not in str(a["meetings"])  # an undated item is dropped, never guessed


def test_sub_items_and_source_reach_the_description():
    a = agenda_from_items(ITEMS, "SEC(2026)2578", "14 September 2026")
    d = describe_meeting(date(2026, 10, 28), a)
    assert "Border and migration package: Strengthening Frontex; Digitalisation of the return process (Virkkunen)" in d
    assert "SEC(2026)2578 of 14 September 2026" in d and "tentative" in d
