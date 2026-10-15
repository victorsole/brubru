"""The Commission's press corner reaches /api/v2/news/all (15 Oct 2026).

Only items a DG's RSS feed repeated were held (about 190 from the press corner, 285
Commission press releases since 15 July 2024) while the press corner published 5,208."""
from datetime import date

from scripts import sync_presscorner as job


def test_the_reference_gives_the_detail_page():
    assert job.slug_of("IP/26/2165") == "ip_26_2165"
    assert job.slug_of("SPEECH/26/2173") == "speech_26_2173"
    assert job.slug_of("STATEMENT/26/2116") == "statement_26_2116"
    assert job.slug_of("") is None and job.slug_of("IP/26") is None and job.slug_of("IP/xx/1") is None


def test_a_press_release_is_kind_press_release_and_the_rest_news():
    ip = job.to_row({"refCode": "IP/26/2165", "eventDate": "2026-10-15", "title": "Main  messages",
                     "leadText": "EU leaders met.", "docutype": {"code": "IP"}})
    assert ip["key"] == "https://ec.europa.eu/commission/presscorner/detail/en/ip_26_2165"
    assert (ip["kind"], ip["item_type"], ip["day"], ip["title"]) == ("press_release", "press", date(2026, 10, 15), "Main messages")
    assert ip["src"] == "composed:title+summary" and "EU leaders met." in ip["txt"]
    sp = job.to_row({"refCode": "SPEECH/26/2173", "eventDate": "2026-10-15", "title": "Keynote",
                     "leadText": None, "docutype": {"code": "SPEECH"}})
    assert (sp["kind"], sp["item_type"], sp["summary"]) == ("news", "speech", None)
    assert job.to_row({"refCode": "IP/26/1", "eventDate": "2026-10-15", "title": ""}) is None


def test_an_item_held_under_any_address_is_not_added_twice():
    sql = str(job.INSERT)
    assert "ON CONFLICT (entry_key) DO NOTHING" in sql
    assert "lower(btrim(e.title)) = lower(:title)" in sql and "e.news_date = :day" in sql


def test_it_stops_at_the_window_and_never_writes_on_a_dry_run(monkeypatch, capsys):
    pages = {1: [{"refCode": "IP/26/5", "eventDate": "2026-10-15", "title": "A", "docutype": {"code": "IP"}}],
             2: [{"refCode": "IP/26/4", "eventDate": "2026-10-01", "title": "B", "docutype": {"code": "IP"}}]}
    asked = []
    monkeypatch.setattr(job, "fetch_page", lambda page, size: asked.append(page) or pages.get(page, []))
    monkeypatch.setattr(job.time, "sleep", lambda s: None)
    assert job.main(["--since", "2026-10-10"]) == 0
    assert asked == [1, 2] and "1 item(s)" in capsys.readouterr().out
