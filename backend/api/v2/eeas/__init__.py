"""
/api/v2/eeas — European External Action Service (api_eeas.md).

The EU's diplomatic service, in its own folder. Resources under the folder
prefix: /api/v2/eeas/{news,publications,events,tenders,topics}. The eeas.europa.eu
site is behind a JS / bot wall, so the feeds are rendered with Playwright
(services/scrapers/economy_eeas.py) and refreshed locally, not on the Railway
cron (same constraint as FRA / EUIPO).

EEAS PEOPLE are not here: the 352 EEAS officials live in the EU Who-is-Who and
are served by /api/v2/who-is-who/officials (filter by the EEAS organisation).

Reads from economy_items (body row in migration 144); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eeas", prefix="/eeas",
    body_name="European External Action Service",
    acronym="EEAS", tag="v2-eeas",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "press material",
         "source": "the EEAS press-material listing (press releases, statements, "
                   "speeches and op-eds), rendered from eeas.europa.eu.",
         "extra": "Press releases, statements by the Spokesperson, declarations on "
                  "behalf of the EU, speeches and op-eds from the European External "
                  "Action Service and the EU delegations. Filter with q (e.g. a "
                  "country or theme such as 'Ukraine' or 'sanctions')."},
        {"item_type": "publication", "slug": "publications", "noun": "publications",
         "source": "the EEAS publications listing (documents, research and reports).",
         "extra": "Reports, fact-sheets, infographics, strategy papers and annual "
                  "reports published by the EEAS, including the activities reports on "
                  "countering foreign information manipulation."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the EEAS events / agenda listing.",
         "extra": "Summits, dialogues, ministerial meetings, conferences and other "
                  "events hosted or attended by the EEAS and the EU delegations."},
        {"item_type": "tender", "slug": "tenders", "noun": "tenders",
         "source": "the EEAS calls-for-tenders listing (ongoing procurement and grants).",
         "extra": "Ongoing EEAS calls for tenders and grants — procurement contracts "
                  "for services, supplies or works at headquarters and in the EU "
                  "delegations worldwide."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of EEAS thematic and geographic reference pages.",
         "extra": "Snapshots of the EEAS reference pages — its structure and "
                  "organisation, the High Representative / Vice-President, missions and "
                  "operations, the regional desks (Africa, Asia, the neighbourhood, the "
                  "Western Balkans and more) and the thematic priorities (security and "
                  "defence, sanctions, Global Gateway, digital diplomacy, crisis "
                  "response). Each item is the standing text of one page."},
    ],
)
