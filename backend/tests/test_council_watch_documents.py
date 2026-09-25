"""Council Watch shows Council texts from eMeeting, through the interest lens.

25 Sep 2026: 204 `council_document` rows (118 distinct Council texts) reached
tracked-file detail only; Council Watch now lists them by the user's interests.
Real database.
"""
from types import SimpleNamespace

from core.database import SessionLocal
from api.council_watch import _document_items


def _user(pi):
    return SimpleNamespace(policy_interests_list=pi, subscription_tier="blue", id="t")


def test_lens_keeps_only_the_interest_committees_or_keywords():
    db = SessionLocal()
    try:
        items = _document_items(db, _user(["Culture"]), True, None)
        assert items, "Culture has Council documents tabled in CULT"
        assert all(i["kind"] == "document" for i in items)
        assert {i["committee"] for i in items} <= {"CULT"} or any(
            "cultur" in (i["title"] + (i["summary"] or "")).lower() for i in items)
        everyone = _document_items(db, _user(["Culture"]), False, None)
        assert len(everyone) > len(items)
    finally:
        db.close()


def test_one_row_per_council_document_newest_first():
    db = SessionLocal()
    try:
        items = _document_items(db, _user([]), False, None)
        refs = [i["reference"] for i in items if i["reference"]]
        assert len(refs) == len(set(refs))
        dates = [i["date"] for i in items if i["date"]]
        assert dates == sorted(dates, reverse=True)
        assert all(i["url"] for i in items)
    finally:
        db.close()
