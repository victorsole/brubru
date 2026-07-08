"""
/api/v2/geographical-indications — EU geographical indications, one thematic
domain spanning two source systems:

    /eu-register     eAmbrosia, the official DG AGRI GI register (PDO/PGI/GI/TSG)
    /third-country   eAmbrosia, third-country GIs protected via EU trade agreements
    /giview          EUIPO GIView, the cross-domain GI search portal

eAmbrosia endpoints read from economy_items (body_code 'commission', item_types
'geographical_indication' and 'third_country_gi'); GIView reads the EUIPO
register slice (body_code 'euipo'). Same v2 contract as every other domain.
Scope: read:economy.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource
from .details import register_gi_details

router = APIRouter(prefix="/geographical-indications")

# gi_details layer: harvested area text, competent authority, and the resolved GEOMETRY
# (GeoJSON) — the only place the mapped polygons are served.
register_gi_details(router)

register_resource(
    router, body_code="commission", item_type="geographical_indication",
    slug="eu-register", noun="EU geographical indications",
    body_name="the EU geographical-indications register (eAmbrosia)", acronym="DG AGRI",
    tag="v2-geographical-indications",
    source="eAmbrosia, the official EU GI register maintained by DG AGRI (the full register).",
    extra="Every EU geographical indication for wine, spirits, agricultural products and foodstuffs "
          "(PDO, PGI, GI and TSG) — protected name, type, product type, country, status, file number, "
          "EU protection date, legal instrument, CN classification, producer-group contact (where "
          "published) and Official Journal publications. ~3,997 entries. Filter with q (e.g. a name, "
          "country or product such as 'Champagne', 'cheese' or 'ES').",
)

register_resource(
    router, body_code="commission", item_type="third_country_gi",
    slug="third-country", noun="third-country geographical indications",
    body_name="eAmbrosia (third-country GIs)", acronym="DG AGRI / DG TRADE",
    tag="v2-geographical-indications",
    source="eAmbrosia, the third-country GIs protected in the EU under international trade agreements.",
    extra="Geographical indications from non-EU countries protected in the EU via bilateral or "
          "multilateral trade agreements (e.g. EU-Mercosur) — protected name, third country, product "
          "category, protection type, status and the agreement under which it is protected. ~2,044 "
          "entries. Filter with q (e.g. a country or product).",
)

register_resource(
    router, body_code="euipo", item_type="geographical_indication",
    slug="giview", noun="geographical indications",
    body_name="GIView (EUIPO)", acronym="EUIPO",
    tag="v2-geographical-indications",
    source="the GIView EU geographical-indications register (the full union register).",
    extra="Every EU geographical indication (PDO, PGI and GI for spirits/wines) as held in EUIPO's "
          "GIView portal — protected name, type, product type, country, EU protection date, file number "
          "and status. ~3,960 entries from the agri and craft/industrial union registers. Filter with q "
          "(e.g. a name, country or product).",
)
