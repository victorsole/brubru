"""
EU news item model — Commission/DG/agency news aggregated for MEUB "News".

Public reference data (migration 101). Populated by scripts/sync_dg_news.py via
services/scrapers/dg_news_scraper.py (browser-UA HTTP + ECL parsing; no Anthropic).
Tagged commission_dg so it's filterable by department + the user's Policy Interests.
Also the structured store the /news skill reads.
"""

from datetime import datetime

from sqlalchemy import Column, String, Date, DateTime, Text, event
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid

from core.database import Base


class EuNewsItem(Base):
    __tablename__ = "eu_news_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_key = Column(Text, nullable=False, unique=True)

    title = Column(Text, nullable=False)
    summary = Column(Text)
    news_date = Column(Date)

    institution = Column(String)
    commission_dg = Column(String)
    item_type = Column(String)        # news | publication | story | press | other
    source_key = Column(String)
    policy_areas = Column(ARRAY(String), default=list)

    image_url = Column(Text)
    source_url = Column(Text)

    # Migration 228. The v2 five-datapoint contract requires body_txt + body_html on
    # every item; this table held neither, so /api/v2/news/all served
    # `summary AS body_txt` and a hardcoded NULL body_html for its whole
    # institutional half (body_html NULL on 100% of rows, body_txt empty on 29%).
    # Composed, never scraped -- body_source says which shape was produced.
    body_txt = Column(Text)
    body_html = Column(Text)
    body_source = Column(Text)

    # FIRST-SEEN, both of them: `default=` fires on INSERT and never again. Neither
    # is an ingestion anchor, and reading one as such is what invented 17 dead
    # fetchers on 8 Sep 2026 (feedback_two_date_anchors_diagnose_scrapers).
    scraped_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    # LAST-FETCH anchor (migration 229). Stamped on every sighting, including rows a
    # sync leaves otherwise unchanged, because a sighting is a fetch even when
    # nothing changed. This is what lets /api/v2/news/latest tell `not_fetched`
    # (ours) from `publisher_quiet` (not a defect) for the institutional half; before
    # it existed the endpoint could only say `fetch_time_unknown`, which is how
    # Council news went 70 days dead without the instrument being able to say whose
    # fault it was.
    #
    # Stamp it through services.news.fetch_anchor.stamp_fetched, never by hand: the
    # "unchanged" path in every writer returns early without touching the object, so
    # an ORM listener cannot see it.
    fetched_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<EuNewsItem {self.commission_dg or self.institution} {self.title[:40]}>"


# ---------------------------------------------------------------------------
# Compose the body datapoints on every write, for every writer
# ---------------------------------------------------------------------------
# There are FOUR ORM writers (sync_dg_news, sync_ep_news, sync_bespoke_news,
# sync_ft_news -- this list said THREE and omitted sync_ep_news until 9 Sep 2026) and a
# raw-SQL insert in publish_dpp_to_meub. Composing in each would guarantee the fourth
# writer forgets -- the failure in feedback_cli_wrapper_parity. A model-level listener
# means an author who has never heard of body_source still produces a compliant row.
#
# Proved necessary the day it was written: the 10,143-row backfill finished against a
# table that had grown to 10,149, because the live ingest added 6 uncomposed rows
# while it ran. The backfill correctly refused to report success. This listener is
# what stops that gap reopening every day.
#
# Raw-SQL inserts bypass the ORM and so bypass this. Re-running
# scripts/backfill_eu_news_bodies.py --apply is the sweep for those; it only touches
# rows where body_source IS NULL, so it is cheap and idempotent.
def _compose_body(mapper, connection, target):  # noqa: ANN001
    from services.news.body_composer import compose_news_body
    txt, htm, src = compose_news_body(
        target.title, target.summary, target.institution,
        target.news_date, target.source_url,
    )
    target.body_txt, target.body_html, target.body_source = txt, htm, src


event.listen(EuNewsItem, "before_insert", _compose_body)
event.listen(EuNewsItem, "before_update", _compose_body)
