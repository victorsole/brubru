"""
Public Analytics API.

Powers public-facing analytics widgets (e.g. the "Topic spikes this week" panel
on the My EU Bubble Analytics tab). Pulls from already-populated tables
(daily_briefs, eprs_publications, legislative_carriages) — no new data layer.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from core.database import SessionLocal


router = APIRouter(prefix="/api/analytics/public", tags=["Public Analytics"])


class TopicSpike(BaseModel):
    topic: str
    weight: int                  # composite score: brief_count + eprs_count*2 + carriage_count*3
    brief_count: int
    eprs_count: int
    carriage_count: int
    sample_titles: List[str]


class TopicSpikesResponse(BaseModel):
    period_start: str
    period_end: str
    items: List[TopicSpike]


# Simple keyword groups — each group rolls up into a topic label
TOPIC_KEYWORDS = {
    "MFF 2028-2034 (long-term budget)": ["mff", "multiannual financial framework", "2028-2034", "long-term budget"],
    "Middle East crisis & energy": ["middle east", "iran", "hormuz", "metsaf", "accelerateeu", "fossil energy"],
    "Better Regulation & simplification": ["better regulation", "deep cleaning", "simplification", "rulebook", "com(2026) 380"],
    "DSA enforcement & age verification": ["digital services act", "dsa", "age verification", "meta", "instagram", "facebook", "minors"],
    "AI Act, sustainability & deployment": ["ai act", "ai continent", "apply ai", "ai sustainability", "gpai"],
    "Cohesion & cohesion policy": ["cohesion", "regio", "cohesion policy"],
    "Fisheries & maritime": ["fisheries", "aquaculture", "pech"],
    "Defence & security": ["defence", "edip", "edf", "safe", "european defence union"],
    "Migration & asylum": ["migration", "asylum", "amnr", "frontex"],
    "Trade & external relations": ["mercosur", "trade agreement", "cbam", "wto", "ita"],
    "Single market & competitiveness": ["competitiveness", "single market", "one europe", "industrial accelerator"],
    "Climate, energy & green deal": ["climate", "energy", "ets", "renewable", "decarbonisation"],
    "Waste & circular economy": ["waste shipment", "diwass", "circular economy", "recycling"],
    "Justice, rights & rule of law": ["rule of law", "fundamental rights", "rape", "gender", "violence against women"],
    "Ukraine support & accountability": ["ukraine", "russia", "iccu", "war"],
}


def _classify(title: str) -> str | None:
    title_low = title.lower()
    best = None
    best_hits = 0
    for topic, keys in TOPIC_KEYWORDS.items():
        hits = sum(1 for k in keys if k in title_low)
        if hits > best_hits:
            best = topic
            best_hits = hits
    return best


@router.get("/topic-spikes", response_model=TopicSpikesResponse)
def topic_spikes(days: int = Query(7, ge=1, le=30), top: int = Query(5, ge=1, le=15)):
    """Aggregate the last N days of news + EPRS + carriage activity into topic clusters."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    period_end = datetime.now(timezone.utc)

    counts_brief: Counter[str] = Counter()
    counts_eprs: Counter[str] = Counter()
    counts_carriage: Counter[str] = Counter()
    samples: dict[str, list[str]] = {t: [] for t in TOPIC_KEYWORDS}

    db = SessionLocal()
    try:
        # 1. daily_briefs (today's headlines) — column is `headline`
        for row in db.execute(text(
            "SELECT headline FROM daily_briefs WHERE created_at >= :cutoff"
        ), {"cutoff": cutoff}).fetchall():
            t = _classify(row[0])
            if t:
                counts_brief[t] += 1
                if len(samples[t]) < 3:
                    samples[t].append(row[0])

        # 2. eprs_publications
        for row in db.execute(text(
            "SELECT title FROM eprs_publications WHERE first_seen >= :cutoff"
        ), {"cutoff": cutoff}).fetchall():
            t = _classify(row[0])
            if t:
                counts_eprs[t] += 1
                if len(samples[t]) < 3:
                    samples[t].append(row[0])

        # 3. legislative_carriages with recent activity
        for row in db.execute(text(
            "SELECT title FROM legislative_carriages "
            "WHERE last_updated >= :cutoff OR is_recently_updated = TRUE"
        ), {"cutoff": cutoff}).fetchall():
            t = _classify(row[0])
            if t:
                counts_carriage[t] += 1
                if len(samples[t]) < 3:
                    samples[t].append(row[0])
    finally:
        db.close()

    items: list[TopicSpike] = []
    for topic in TOPIC_KEYWORDS:
        b = counts_brief.get(topic, 0)
        e = counts_eprs.get(topic, 0)
        c = counts_carriage.get(topic, 0)
        weight = b + e * 2 + c * 3
        if weight == 0:
            continue
        items.append(TopicSpike(
            topic=topic, weight=weight,
            brief_count=b, eprs_count=e, carriage_count=c,
            sample_titles=samples[topic][:3],
        ))

    items.sort(key=lambda x: x.weight, reverse=True)
    return TopicSpikesResponse(
        period_start=cutoff.isoformat(),
        period_end=period_end.isoformat(),
        items=items[:top],
    )
