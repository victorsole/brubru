"""
/api/v2/extract — the input-first EU extraction surface (Phase 1, step 1.5).

Give it any EU institutional URL; it classifies the platform (one of the 8 in the
EU web-estate taxonomy), fetches it through the right anti-bot path, and returns
structured 5-datapoint items. The same engine that powers the per-body folders,
exposed input-first: "Tavily for the EU". Scope: read:economy.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from models.user import User
from api.v1._deps import api_user_with_rate_limit
from services.extract import extract as _extract

router = APIRouter(prefix="/extract", tags=["v2-extract"])

_ITEM_TYPES = {"news", "event", "publication", "topic", "consultation", "tender"}


class ExtractedItem(BaseModel):
    title: str
    item_type: Optional[str] = Field(None, description="news | event | publication | topic | consultation | tender (caller-supplied page-level hint).")
    public_url: Optional[str] = None
    summary: Optional[str] = None
    document_date: Optional[datetime] = None
    creation_date: Optional[datetime] = None
    body_txt: Optional[str] = Field(None, description="Article body — populated only with deep=true.")
    body_html: Optional[str] = Field(None, description="Article HTML — populated only with deep=true.")
    body_code: Optional[str] = None
    guid: Optional[str] = None
    source_kind: Optional[str] = Field(None, description="The platform handler that parsed it.")
    eurovoc_descriptors: List[dict] = Field(default_factory=list, description="EuroVoc subject descriptors (when classify=true).")


class ExtractResult(BaseModel):
    url: str
    platform: str = Field(..., description="Detected platform: ecl | drupal | wordpress | dynamics | jcms | sharepoint | spa | bespoke.")
    body_code: str
    fetched_via: str = Field(..., description="requests | browser | failed.")
    item_count: int
    items: List[ExtractedItem]


@router.get("", response_model=ExtractResult, tags=["v2-extract"],
            summary="Extract structured items from any EU URL",
            description=(
                "**What it does**\nGive it any EU institutional listing URL (news, events, publications, "
                "consultations). It detects which of the 8 EU web platforms the page is built on, fetches "
                "it through the matching anti-bot path (plain request, or a headless browser for "
                "JS-rendered / walled sites), and returns structured 5-datapoint items.\n\n**When to use "
                "it**\nWhen you want the structured data behind an EU page without writing a scraper for "
                "it. One endpoint covers the whole EU estate.\n\n**Input**\n`url` (required), `item_type` "
                "(news | event | publication | topic | consultation | tender; default news), `limit` (max "
                "100).\n\n**Try it**\n```\nGET /api/v2/extract?url=https://cinea.ec.europa.eu/news-events/news_en\n```\n\n"
                "**You get back**\nThe detected platform, how it was fetched, and the extracted items "
                "(title, public_url, document_date, summary, the 5-datapoint shape).\n\n**Data freshness**\n"
                "Live — fetched at request time."))
async def extract_url(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    url: str = Query(..., description="The EU URL to extract."),
    item_type: str = Query("news", description="news | event | publication | topic | consultation | tender."),
    limit: int = Query(30, ge=1, le=60, description="Max items (<=60 so every returned item is fully enriched in the default full-contract mode)."),
    classify: bool = Query(False, description="Also tag each item with EuroVoc subject descriptors (slower)."),
    shallow: bool = Query(False, description="Fast listing-only: skip the per-item detail fetches, so body_txt/body_html and some dates are left empty. Default is the full contract (each item's body + date filled from its detail page)."),
    lang: str = Query("en", description="Language for EuroVoc classification (en|es|fr|it|nl; ca->es)."),
):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "url must be an absolute http(s) URL")
    if item_type not in _ITEM_TYPES:
        raise HTTPException(400, f"item_type must be one of {sorted(_ITEM_TYPES)}")
    # The engine is fully synchronous (requests + sync Playwright). Run it off the event
    # loop so one slow render can't block every other coroutine on the worker.
    res = await run_in_threadpool(_extract, url, item_type=item_type, limit=limit,
                                  classify_eurovoc=classify, lang=lang, shallow=shallow)
    if res.get("error") == "fetch_failed" or res.get("fetched_via") in ("failed", "blocked"):
        # surface as 502 so the metered-call refund path (5xx) triggers and the caller
        # can tell "fetch failed / blocked" apart from "page genuinely empty".
        raise HTTPException(502, f"could not fetch the URL ({res.get('fetched_via', 'failed')})")
    items = [ExtractedItem(title=it.title, item_type=it.item_type, public_url=it.public_url,
                           summary=it.summary, document_date=it.document_date, creation_date=it.creation_date,
                           body_txt=it.body_txt, body_html=it.body_html, body_code=it.body_code,
                           guid=it.guid, source_kind=it.source_kind,
                           eurovoc_descriptors=it.extras.get("eurovoc", []))
             for it in res.get("items", [])]
    return ExtractResult(url=res["url"], platform=res["platform"], body_code=res["body_code"],
                         fetched_via=res["fetched_via"], item_count=res["item_count"], items=items)
