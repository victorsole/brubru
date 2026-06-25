"""
/api/v2/cjeu — Court of Justice of the European Union (api_ecj.md).

The EU judicial institution, its own folder. Resources under the folder prefix:
/api/v2/cjeu/{press-releases,case-law,events,topics}. curia.europa.eu is a JCMS
site reachable with plain requests; the case-law is read from the Publications
Office Cellar SPARQL endpoint that backs InfoCuria/EUR-Lex.

Reads from economy_items (body row seeded by migration 167); 5 mandatory
datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="cjeu", prefix="/cjeu",
    body_name="Court of Justice of the European Union",
    acronym="CJEU", tag="v2-cjeu",
    resources=[
        {"item_type": "press_release", "slug": "press-releases", "noun": "press releases",
         "source": "the CJEU press-releases archive (current year); bodies are extracted "
                   "from the source PDFs.",
         "extra": "Court of Justice and General Court press releases, each on a judgment, "
                  "Advocate General opinion or order, with its PR number, the case "
                  "reference (e.g. Case C-277/25) and the date. Filter with q (e.g. a "
                  "case number or a party name)."},
        {"item_type": "case_law", "slug": "case-law", "noun": "case-law documents",
         "source": "the EU case-law corpus (sector-6 CELEX) via the Publications Office "
                   "Cellar SPARQL endpoint that backs InfoCuria and EUR-Lex.",
         "extra": "Current-year CJEU case-law: every judgment, Advocate General opinion "
                  "and order of the Court of Justice and the General Court, with its "
                  "CELEX number, ECLI, date and title, linking to the EUR-Lex page. "
                  "Filter with q (e.g. an ECLI, a CELEX number or a case title)."},
        {"item_type": "event", "slug": "events", "noun": "events",
         "source": "the CJEU events listing.",
         "extra": "Conferences, anniversaries and other events at the Court."},
        {"item_type": "topic", "slug": "topics", "noun": "topic pages",
         "source": "a curated set of CJEU about and documents-and-research pages.",
         "extra": "Snapshots of the CJEU's about pages (the institution, history, the "
                  "Court of Justice and the General Court, the Court in numbers, how the "
                  "procedure works, e-Curia) and its documents-and-research pages (the "
                  "case-law database, fact-sheets, the case-law digest, the EU judicial "
                  "network, research notes, the annual report)."},
    ],
)
