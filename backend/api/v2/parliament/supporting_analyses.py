"""European Parliament database — committee supporting analyses (Policy Department
studies). /api/v2/parliament/supporting-analyses.

Backed by economy_items (body_code 'parliament', item_type 'supporting_analysis').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="parliament", item_type="supporting_analysis",
    slug="supporting-analyses", noun="committee supporting analyses",
    body_name="the European Parliament", acronym="the EP",
    tag="v2-parliament",
    source="the EP Think Tank — the Parliament's Policy Departments, which produce the "
           "in-house expertise (studies, in-depth analyses, briefings, at-a-glance notes) "
           "that committees commission to support their legislative work.",
    extra="One entry per Policy Department document: title, publication type, the committee "
          "it was prepared for (when stated), date and reference, with the abstract, linking "
          "to the Think Tank document page. Filter with q (e.g. a committee acronym such as "
          "ECON or LIBE, a topic, or a document reference).",
)
