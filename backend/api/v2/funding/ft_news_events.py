"""EU Funding & Tenders Portal news + events — /api/v2/funding/ft-{news,events}.

The portal's Support -> News and Support -> Events feeds, ingested from the
dedicated SEDIA indexes (SEDIA-NEWS-PROD / SEDIA-EVENTS-PROD) into economy_items
(body_code 'ftportal'). Each is one register_resource() call → list (bodies
nulled) + detail /{item_id} (full body), with the 5-datapoint contract.

Legacy routes since 29 Oct 2026 (funding standard Phase 3, proposal of 23 Oct 2026 §2): the portal's
news and events are served in the News and Events folders, /api/v2/news/ft-portal and
/api/v2/events/ft-portal (typed by the calendar there). These two keep answering, unchanged, until the
date Victor sets for legacy routes (§8: routes kept 12 months).
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="ftportal", item_type="news",
    slug="ft-news", noun="news items", body_name="the EU Funding & Tenders Portal",
    acronym="F&T Portal", tag="v2-funding",
    source="the EU Funding & Tenders Portal news feed (SEDIA-NEWS-PROD); refreshed daily.",
    extra=("**Legacy route:** the portal's news are served at `/api/v2/news/ft-portal` (the News folder's shape, "
           "`self` on `/api/v2/news/{id}`); this route keeps answering, unchanged, until the date set for legacy "
           "routes. Portal announcements: new calls, info sessions, programme updates and deadlines across all EU "
           "funding programmes."),
    funding_standard=True, deprecated=True,
)
register_resource(
    router, body_code="ftportal", item_type="event",
    slug="ft-events", noun="events", body_name="the EU Funding & Tenders Portal",
    acronym="F&T Portal", tag="v2-funding",
    source="the EU Funding & Tenders Portal events feed (SEDIA-EVENTS-PROD); refreshed daily.",
    extra=("**Legacy route:** the portal's events are served at `/api/v2/events/ft-portal` (the Events folder's "
           "shape, each typed by Brubru's calendar, other ids); this route keeps answering, unchanged, until the date "
           "set for legacy routes. Info days, webinars and programme events; `document_date` is the event start "
           "date, so order=recent surfaces the next events first."),
    funding_standard=True, deprecated=True,
)
