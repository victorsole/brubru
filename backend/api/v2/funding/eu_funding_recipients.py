"""Funding & Tenders database — EU Financial Transparency System (FTS).
/api/v2/funding/eu-funding-recipients — grouped under "Funded Projects".

Who actually received EU money under direct management (the recipient side of
funded projects). Backed by economy_items (body_code 'commission' — FTS is a
Commission system — item_type 'funding_recipient').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="funding_recipient",
    slug="eu-funding-recipients", noun="EU funding recipients",
    body_name="the EU Financial Transparency System", acronym="the EC",
    tag="v2-funding",
    source="the EU Financial Transparency System (FTS) annual dataset (most recent complete year).",
    extra="Who received EU money under direct management — beneficiary name, EU commitment amount, "
          "funding type (grant, procurement contract, prize, etc.), programme, subject, responsible "
          "department, budget line, management type and country, for the most recent complete year. "
          "The recipient side of EU funded projects. Filter with q (e.g. a beneficiary, programme or country).",
)
