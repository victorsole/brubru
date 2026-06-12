"""
/api/v2/echa — European Chemicals Agency.

EU chemicals agency (api_health.md), its own folder. Resources under the folder
prefix: /api/v2/echa/{candidate-list}.

Reads from economy_items (migration 127); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from ..economy_endpoints import make_single_body_folder

router = make_single_body_folder(
    body_code="echa", prefix="/echa",
    body_name="European Chemicals Agency",
    acronym="ECHA", tag="v2-echa",
    resources=[
        {"item_type": "svhc_substance", "slug": "candidate-list",
         "noun": "Candidate List substances",
         "source": "the ECHA REACH Candidate List of substances of very high concern (SVHC).",
         "extra": "The REACH Candidate List of substances of very high concern that may be placed "
                  "on the Authorisation List. Each entry carries the substance name, EC and CAS "
                  "numbers, the date of inclusion, the reason for inclusion (the SVHC property, e.g. "
                  "carcinogenic, toxic for reproduction, endocrine disrupting) and the ECHA "
                  "substance-information link. Filter with q (e.g. a substance name, a CAS number, "
                  "or an SVHC property)."},
        {"item_type": "news", "slug": "news", "noun": "news items",
         "source": "the ECHA news archive.",
         "extra": "News alerts from the European Chemicals Agency on REACH, CLP, biocides and "
                  "the agency's regulatory work."},
    ],
)
