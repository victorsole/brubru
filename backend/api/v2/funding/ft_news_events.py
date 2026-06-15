"""EU Funding & Tenders Portal news + events — /api/v2/funding/ft-{news,events}.

The portal's Support -> News and Support -> Events feeds, ingested from the
dedicated SEDIA indexes (SEDIA-NEWS-PROD / SEDIA-EVENTS-PROD) into economy_items
(body_code 'ftportal'). Each is one register_resource() call → list (bodies
nulled) + detail /{item_id} (full body), with the 5-datapoint contract.
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
    extra="Portal announcements: new calls, info sessions, programme updates and deadlines across all EU funding programmes.",
)
register_resource(
    router, body_code="ftportal", item_type="event",
    slug="ft-events", noun="events", body_name="the EU Funding & Tenders Portal",
    acronym="F&T Portal", tag="v2-funding",
    source="the EU Funding & Tenders Portal events feed (SEDIA-EVENTS-PROD); refreshed daily.",
    extra="Info days, webinars and programme events; `document_date` is the event start date, so order=recent surfaces the next events first.",
)
