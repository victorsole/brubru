"""A fetched news article is never replaced by a title-plus-summary composition, and a
feed sync writes each item once per run.

Measured 18 Oct 2026 with brubru_change_log (migration 297): 17 Commission and EEAS rows
of eu_news_items flipped 233 times in two days between the article that
scripts/fetch_institutional_news_bodies.py stores (raw SQL, body_source
'fetched:article') and "title + summary + Published by" (body_source
'composed:title+summary'). Each flip moved updated_at, so GovClipping's news pull got the
row again, sometimes as a placeholder: "EU delivering on COP17" was 5,442 characters on
16 Oct and 330 on 18 Oct.

Two causes, both tested here by calling the code that runs:
1. The model's before_update listener recomposed the body on EVERY ORM update, so any
   feed sync that touched a summary erased the fetched article.
2. scripts/sync_dg_news.py wrote the same item twice a run, once from the hub and once
   from the DG's newsroom, with different titles or summaries: the row changed twice a
   run, every run.
"""
import importlib
import pathlib
import sys
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import event

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from models.eu_news_item import EuNewsItem, _compose_body, _recompose_unless_fetched  # noqa: E402

ARTICLE = "COP17: EU delivering on global targets to protect nature and biodiversity\n" + "The conference opens. " * 200


def _row(**kw):
    base = dict(entry_key="https://environment.ec.europa.eu/news/cop17_en", title="EU delivering on COP17",
                summary="The 17th UN Biodiversity Conference starts next week.", institution="COMMISSION",
                news_date=date(2026, 10, 16), source_url="https://environment.ec.europa.eu/news/cop17_en",
                commission_dg="ENV")
    base.update(kw)
    return EuNewsItem(**base)


class TestTheListener:
    def test_update_keeps_a_fetched_article(self):
        r = _row(body_txt=ARTICLE, body_html="<article>...</article>", body_source="fetched:article")
        r.summary = "A different summary from the hub listing."
        _recompose_unless_fetched(None, None, r)
        assert r.body_txt == ARTICLE and r.body_source == "fetched:article"

    def test_update_recomposes_a_composed_body_from_the_new_summary(self):
        r = _row()
        _compose_body(None, None, r)
        assert r.body_source.startswith("composed")
        r.summary = "A corrected summary."
        _recompose_unless_fetched(None, None, r)
        assert "A corrected summary." in r.body_txt and r.body_source.startswith("composed")

    def test_update_composes_a_row_without_body(self):
        r = _row(body_txt=None, body_source=None)
        _recompose_unless_fetched(None, None, r)
        assert r.body_txt and r.body_source.startswith("composed")

    def test_update_composes_over_an_empty_fetched_body(self):
        # A fetch that stored nothing is not an article to protect.
        r = _row(body_txt="", body_source="fetched:article")
        _recompose_unless_fetched(None, None, r)
        assert r.body_txt and r.body_source.startswith("composed")

    def test_the_model_uses_the_guarded_listener_on_update(self):
        assert event.contains(EuNewsItem, "before_update", _recompose_unless_fetched)
        assert not event.contains(EuNewsItem, "before_update", _compose_body)
        assert event.contains(EuNewsItem, "before_insert", _compose_body)


class _Query:
    def __init__(self, store): self.store = store
    def filter(self, *a, **k): return self
    def first(self): return self.store.get("row")


class _DB:
    def __init__(self, row): self.store = {"row": row}; self.added = []
    def query(self, *a): return _Query(self.store)
    def add(self, o): self.added.append(o)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


def _run_sync(monkeypatch, row, sightings):
    mod = importlib.import_module("scripts.sync_dg_news")
    sources = [{"url": f"https://example.invalid/{i}"} for i in range(len(sightings))]
    by_url = {s["url"]: [dict(it)] for s, it in zip(sources, sightings)}
    db = _DB(row)
    monkeypatch.setattr(mod, "ALL_SOURCES", sources)
    monkeypatch.setattr(mod, "scrape_source", lambda src: by_url[src["url"]])
    monkeypatch.setattr(mod, "date_new_items", lambda db_, items: (items, []))
    monkeypatch.setattr(mod, "stamp_fetched", lambda db_, keys: None)
    monkeypatch.setattr(mod, "record_refusals", lambda *a, **k: None)
    monkeypatch.setattr(mod, "SessionLocal", lambda: db)
    mod.main()
    return db


class TestOneWritePerRun:
    def test_a_second_sighting_in_the_same_run_writes_nothing(self, monkeypatch):
        row = _row(summary="Stored summary.", body_txt=ARTICLE, body_source="fetched:article")
        hub = {"entry_key": row.entry_key, "title": "EU delivering on COP17", "summary": "Hub summary.",
               "institution": "COMMISSION", "news_date": date(2026, 10, 16), "source_url": row.source_url}
        dg = dict(hub, summary="DG newsroom summary.")
        _run_sync(monkeypatch, row, [hub, dg])
        assert row.summary == "Hub summary.", "the later sighting overwrote the first one"

    def test_the_same_two_sightings_next_run_change_nothing(self, monkeypatch):
        row = _row(summary="Hub summary.", body_txt=ARTICLE, body_source="fetched:article")
        hub = {"entry_key": row.entry_key, "title": "EU delivering on COP17", "summary": "Hub summary.",
               "institution": "COMMISSION", "news_date": date(2026, 10, 16), "source_url": row.source_url}
        dg = dict(hub, summary="DG newsroom summary.")
        _run_sync(monkeypatch, row, [hub, dg])
        assert row.summary == "Hub summary."
