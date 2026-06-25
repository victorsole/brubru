"""
/api/v2/eurojust — European Union Agency for Criminal Justice Cooperation (api_socjust.md).

The EU agency that coordinates investigations and prosecutions of serious
cross-border crime, its own folder. Resources under the folder prefix:
/api/v2/eurojust/{news,topics}. Drupal site (eurojust.europa.eu), scraped with
plain requests (no WAF).

Eurojust does not publish individual cases (casework is confidential and released
only as aggregate statistics), so there is no scrapeable case list; the
substantive crime-area and judicial-cooperation content is captured under topics.

Reads from economy_items (body row seeded); 5 mandatory datapoints.
Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="eurojust", prefix="/eurojust",
    body_name="European Union Agency for Criminal Justice Cooperation",
    acronym="Eurojust", tag="v2-eurojust",
    resources=[
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the Eurojust press releases and news listing.",
         "extra": "News from Eurojust on joint investigation teams, coordinated "
                  "actions against terrorism, cybercrime, drug trafficking, migrant "
                  "smuggling and other serious cross-border crime."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of Eurojust crime-type and judicial-cooperation "
                   "instrument pages.",
         "extra": "Snapshots of Eurojust's crime-area pages (terrorism, cybercrime, "
                  "drug trafficking, economic crime, migrant smuggling, trafficking in "
                  "human beings, core international crimes, crimes against children, "
                  "PIF crimes, CBRN-E) and judicial-cooperation instruments (European "
                  "Arrest Warrant, European Investigation Order, joint investigation "
                  "teams, asset recovery, extradition, electronic evidence)."},
    ],
)
