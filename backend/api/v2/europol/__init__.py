"""
/api/v2/europol — European Union Agency for Law Enforcement Cooperation (api_socjust.md).

The EU police agency, its own folder. Resources under the folder prefix:
/api/v2/europol/{news,topics}. europol.europa.eu is a JS-rendered Drupal site, so
it is fed through Playwright on the local refresh (not the Railway cron).

Reads from economy_items (body row seeded by migration 155); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="europol", prefix="/europol",
    body_name="European Union Agency for Law Enforcement Cooperation",
    acronym="Europol", tag="v2-europol",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the Europol newsroom listing.",
         "extra": "News from Europol on cross-border operations against drug "
                  "trafficking, cybercrime, terrorism, money laundering and organised "
                  "crime, plus partnership and threat-assessment announcements."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of Europol crime-area, specialist-centre and "
                   "flagship-report pages.",
         "extra": "Snapshots of Europol's crime areas (child sexual exploitation, "
                  "corruption, criminal finances and money laundering, currency "
                  "counterfeiting, cyber attacks, illicit drugs), its specialist "
                  "centres (ESOCC, EC3, ECTC, EFECC, the operational and analysis "
                  "centre), how-we-work hubs (operations, SIRIUS, innovation lab, "
                  "analysis projects, EMPACT) and its flagship reports (SOCTA, IOCTA)."},
    ],
)
