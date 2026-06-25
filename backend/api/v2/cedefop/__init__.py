"""
/api/v2/cedefop — European Centre for the Development of Vocational Training.

EU skills/VET agency (api_socjust.md), its own folder. Resources under the folder
prefix: /api/v2/cedefop/{news,events,publications}.

Reads from economy_items (migration 130); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="cedefop", prefix="/cedefop",
    body_name="European Centre for the Development of Vocational Training",
    acronym="Cedefop", tag="v2-cedefop",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the Cedefop news feed.",
         "extra": "News from Cedefop on vocational education and training, skills and the "
                  "labour market."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the Cedefop events listing.",
         "extra": "Conferences, webinars and meetings hosted or co-hosted by Cedefop."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the Cedefop publications and reports.",
         "extra": "Cedefop reports, briefing notes, country reports and research on skills and "
                  "vocational training. Filter with q (e.g. a topic such as 'apprenticeship' or "
                  "'skills forecast')."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of Cedefop about, theme and tool pages.",
         "extra": "Snapshots of Cedefop's who-we-are and what-we-do pages, its themes "
                  "(skills and labour market, VET knowledge centre, delivering VET and "
                  "qualifications, statistics) and its flagship tools (European Skills "
                  "Index, VET policy dashboard, skills forecast and intelligence, "
                  "matching skills, skills and jobs survey, apprenticeship schemes, "
                  "validation of non-formal learning, mobility scoreboard, VET "
                  "glossary, key indicators on VET, online job vacancies)."},
    ],
)
