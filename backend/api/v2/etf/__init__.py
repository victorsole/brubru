"""
/api/v2/etf — European Training Foundation (api_socjust.md).

The EU agency for human-capital development in partner countries, its own folder.
Resources under the folder prefix: /api/v2/etf/{news,events,topics}. Drupal site
(etf.europa.eu), scraped with plain requests (no WAF).

Reads from economy_items (body row seeded); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="etf", prefix="/etf",
    body_name="European Training Foundation",
    acronym="ETF", tag="v2-etf",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ETF news listing.",
         "extra": "News from the European Training Foundation on vocational education "
                  "and training, skills, lifelong learning and human-capital "
                  "development in the EU's partner countries."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the ETF events listing.",
         "extra": "Conferences, policy labs, symposia and other events organised by "
                  "the European Training Foundation."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of ETF 'what we do' thematic pages.",
         "extra": "Snapshots of ETF's thematic pages: career guidance, digital skills "
                  "and learning, green skills, qualifications systems, quality "
                  "assurance, skills analysis and vocational excellence."},
    ],
)
