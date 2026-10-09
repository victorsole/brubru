"""The told-ledger: what a client has been sent decides what is NEW in the DPP watch.

All texts here are synthetic. The real mails are client correspondence and never enter a
public repository.
"""
import importlib.util
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.clients import told_ledger as tl  # noqa: E402

SENT = date(2026, 10, 5)
WRAPPED = ("https://www.google.com/url?q=https://ec.europa.eu/info/law/better-regulation/have-your-say/"
           "initiatives/14460-minimum-values-for-the-electrochemical-performance-and-durab_en"
           "&source=gmail&ust=1791268524157000&sa=E")


# -- identifiers ---------------------------------------------------------------------------------

def test_gmail_wrapper_is_unwrapped_and_the_initiative_id_is_found():
    ids = tl.identifiers_from(f"vegeu la fitxa <{WRAPPED}> de Have Your Say")
    assert "hys:14460" in ids
    assert any(k.startswith("url:ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14460") for k in ids)
    assert not any("google.com" in k for k in ids)


def test_references_are_found_in_text_and_in_encoded_links():
    text = ("TRIS 2026/0266/ES i 2026/0485/CZ; "
            "https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference%3D2025/0395(COD) "
            "pregunta E-10-2026-003207 i E-002909/2026; EPRS_BRI(2026)791501")
    ids = tl.identifiers_from(text)
    assert {"tris:2026/0266/ES", "tris:2026/0485/CZ", "oeil:2025/0395(COD)", "epq:003207/2026",
            "epq:002909/2026", "eprs:2026/791501"} <= ids


def test_the_same_question_written_two_ways_is_one_key():
    assert tl.identifiers_from("E-10-2026-003207") == tl.identifiers_from("E-003207/2026")


def test_eli_and_celex_forms_meet_on_one_key():
    from_mail = tl.identifiers_from("https://eur-lex.europa.eu/eli/reg/2023/1542/oj/eng")
    from_item = tl.identifiers_from("https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1542")
    assert "celex:32023R1542" in from_mail and "celex:32023R1542" in from_item


def test_a_link_with_parentheses_survives_but_prose_brackets_do_not():
    ids = tl.identifiers_from("nota <https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2026)791501> "
                              "(vegeu https://example.org/page/one).")
    assert "url:europarl.europa.eu/thinktank/en/document/eprs_bri(2026)791501" in ids
    assert "url:example.org/page/one" in ids


def test_a_bare_homepage_is_not_an_identifier():
    assert tl.identifiers_from("https://ec.europa.eu/") == set()


def test_youtube_keeps_the_video_id():
    assert "url:youtube.com/watch?v=XjVjmSvAQno" in tl.identifiers_from("https://www.youtube.com/watch?v=XjVjmSvAQno&t=3")


# -- dates in six languages ----------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("el divendres 23 d'octubre, de 9:00 a 13:00", date(2026, 10, 23)),          # Catalan
    ("el dimecres 4 de novembre", date(2026, 11, 4)),                             # Catalan
    ("el lunes 26 de octubre", date(2026, 10, 26)),                               # Spanish
    ("le lundi 26 octobre", date(2026, 10, 26)),                                  # French
    ("il 23 ottobre", date(2026, 10, 23)),                                        # Italian
    ("op 4 november", date(2026, 11, 4)),                                         # Dutch
    ("closes on 27 October", date(2026, 10, 27)),                                 # English
    ("closes on October 27", date(2026, 10, 27)),                                 # English, month first
    ("deadline 2026-11-04", date(2026, 11, 4)),                                   # ISO
    ("4 de novembre de 2027", date(2027, 11, 4)),                                 # explicit year wins
])
def test_dates_in_six_languages(text, expected):
    assert expected in tl.extract_dates(text, SENT)


def test_a_december_mail_that_says_january_means_next_year():
    assert date(2027, 1, 5) in tl.extract_dates("el 5 de gener", date(2026, 12, 18))


def test_an_october_mail_that_says_august_means_this_year():
    assert date(2026, 8, 5) in tl.extract_dates("va registrar el dimecres 5 d'agost", SENT)


def test_a_reference_number_is_not_a_date():
    assert tl.extract_dates("Reglament 2023/1542 i 2024/1781", SENT) == []


# -- matching ------------------------------------------------------------------------------------

def _mail(ids, dates=(), days_ago=0, channel="email", subject="Resum", today=date(2026, 10, 9)):
    return {"sent_at": datetime(today.year, today.month, today.day, 8, 0, tzinfo=timezone.utc) - timedelta(days=days_ago),
            "identifiers": set(ids), "mentioned_dates": set(dates), "channel": channel, "subject": subject,
            "thread_ref": "t1"}


def _item(**kw):
    base = {"urgent": True, "scope": "B", "source": "consultations", "body": "European Commission",
            "title": "Minimum values", "url": WRAPPED.split("q=")[1].split("&")[0], "item_type": "consultation",
            "d": date(2026, 10, 27)}
    base.update(kw)
    return base


def test_a_deadline_is_told_only_when_its_date_was_in_the_mail():
    mail = _mail({"hys:14460"}, {date(2026, 10, 26), date(2026, 10, 27)})
    assert tl.match_told(_item(), [mail]) is not None
    extended = _item(d=date(2026, 11, 10))              # the deadline moved after the mail
    assert tl.match_told(extended, [mail]) is None


def test_a_deadline_one_day_off_is_the_same_deadline_but_a_week_off_is_new():
    mail = _mail({"hys:14460"}, {date(2026, 10, 26)})
    assert tl.match_told(_item(d=date(2026, 10, 27)), [mail]) is not None      # portal says 27, mail said 26
    assert tl.match_told(_item(d=date(2026, 11, 3)), [mail]) is None           # extended by a week


def test_an_undated_item_is_told_by_identifier_alone():
    mail = _mail({"url:europarl.europa.eu/news/en/press-room/20261002ipr47884/meps-support"})
    item = _item(item_type="news", source="eu_news_items", d=date(2026, 10, 2),
                 url="https://www.europarl.europa.eu/news/en/press-room/20261002IPR47884/meps-support")
    assert tl.match_told(item, [mail]) is not None


def test_a_tris_notification_is_told_by_its_number():
    mail = _mail({"tris:2026/0485/CZ"})
    item = _item(item_type="tris_notification", source="tris", url="https://x.example/n/28566",
                 title="[2026/0485/CZ] Draft Act amending Act No 542/2020 (standstill to 2026-12-04)",
                 d=date(2026, 12, 4))
    assert tl.match_told(item, [mail]) is not None


def test_nothing_matches_when_no_identifier_overlaps():
    assert tl.match_told(_item(), [_mail({"hys:99999"}, {date(2026, 10, 27)})]) is None


def test_the_most_recent_entry_is_reported():
    old = _mail({"hys:14460"}, {date(2026, 10, 27)}, days_ago=30, subject="old")
    new = _mail({"hys:14460"}, {date(2026, 10, 27)}, days_ago=1, subject="new")
    assert tl.match_told(_item(), [old, new])["subject"] == "new"


# -- annotation ----------------------------------------------------------------------------------

def test_a_told_urgent_item_stops_being_urgent_and_an_untold_one_stays():
    told = _item()
    fresh = _item(title="Another", url="https://ec.europa.eu/other/initiatives/777-x_en", d=date(2026, 11, 3))
    results = {"B": [told, fresh]}
    out = tl.annotate(results, [_mail({"hys:14460"}, {date(2026, 10, 27)})], today=date(2026, 10, 9))
    assert out == {"told": 1, "cleared": 1, "remind": 0}
    assert told["urgent"] is False and told["was_urgent"] is True and told["told"]["subject"] == "Resum"
    assert fresh["urgent"] is True and "told" not in fresh


def test_a_reminder_is_due_close_to_an_old_deadline_only():
    today = date(2026, 10, 24)
    mails = [_mail({"hys:14460"}, {date(2026, 10, 27)}, days_ago=14, today=today)]
    close = _item(d=date(2026, 10, 27))
    assert tl.annotate({"B": [close]}, mails, today=today)["remind"] == 1
    assert close["remind"] is True
    far = _item(d=date(2026, 10, 27))
    far_day = date(2026, 10, 12)                                                         # 15 days before the deadline
    far_mails = [_mail({"hys:14460"}, {date(2026, 10, 27)}, days_ago=14, today=far_day)]
    assert tl.annotate({"B": [far]}, far_mails, today=far_day)["remind"] == 0
    recent = _item(d=date(2026, 10, 27))
    fresh_mail = [_mail({"hys:14460"}, {date(2026, 10, 27)}, days_ago=2, today=today)]   # told 2 days ago
    assert tl.annotate({"B": [recent]}, fresh_mail, today=today)["remind"] == 0


def test_a_dismissed_item_is_cleared_and_never_reminded():
    mail = _mail({"hys:14460"}, {date(2026, 10, 27)}, days_ago=30, channel="dismissed")
    item = _item(d=date(2026, 10, 27))
    out = tl.annotate({"B": [item]}, [mail], today=date(2026, 10, 25))
    assert out["cleared"] == 1 and out["remind"] == 0 and item["urgent"] is False


# -- the verdict says what the ledger could not do -----------------------------------------------

@pytest.fixture(scope="module")
def watch():
    spec = importlib.util.spec_from_file_location("dpp_watch_under_test", BACKEND / "scripts" / "dpp_watch.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.disable(logging.NOTSET)       # the script silences logging at import; do not leak that into other tests
    return mod


def _hit(urgent):
    return {"urgent": urgent, "scope": "A", "title": "t", "d": date(2026, 10, 20)}


def test_verdict_counts_only_new_urgent_items_and_names_the_sent_ones(watch):
    v, why = watch.verdict({"A": [_hit(False)]}, [], {"mails": 3, "told": 4, "cleared": 3, "remind": 0, "error": None})
    assert v == "ROUTINE" and "4 item(s) already sent" in why and "3 of them were urgent" in why
    v, why = watch.verdict({"A": [_hit(True)]}, [], {"mails": 3, "told": 4, "cleared": 3, "remind": 0, "error": None})
    assert v == "URGENT" and "NEW" in why


def test_verdict_is_loud_when_the_ledger_is_unreadable_or_empty(watch):
    _, why = watch.verdict({"A": [_hit(True)]}, [], {"mails": None, "error": "ProgrammingError: relation missing"})
    assert "told-ledger unreadable" in why and "may include items the client already has" in why
    _, why = watch.verdict({"A": [_hit(True)]}, [], {"mails": 0, "error": None})
    assert "holds no entries" in why


def test_verdict_announces_a_due_reminder(watch):
    _, why = watch.verdict({"A": [_hit(False)]}, [], {"mails": 2, "told": 1, "cleared": 0, "remind": 2, "error": None})
    assert "REMINDER due: 2" in why
