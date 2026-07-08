"""
/api/v2/geographical-indications/details + /geometry — the harvested GI DETAIL layer
(table gi_details): the delimited geographical-area text, the competent authority, and the
RESOLVED GEOMETRY (GeoJSON) of each EU geographical indication. This is the only place the
mapped polygons are served; the metadata resources in this router read economy_items and
carry no geometry.

Sync-ORM reads only, so the endpoints are `def` (Starlette threadpools them) per the
single-worker event-loop rule.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Path as PathParam, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit

_DETAIL_COLS = """
    file_number, protected_name, gi_type, product_type, countries, status,
    eu_protection_date, competent_authority, geographical_area, geo_geom_confidence,
    geo_refine_track, round(geo_area_km2::numeric) AS area_km2,
    (geo_shape IS NOT NULL) AS has_geometry
"""


def _filters(country, gi_type, product_type, q, only_geo):
    where, params = ["1=1"], {}
    if country:
        where.append(":country = ANY(countries)"); params["country"] = country.upper()
    if gi_type:
        where.append("gi_type = :gi_type"); params["gi_type"] = gi_type.upper()
    if product_type:
        where.append("product_type ILIKE :pt"); params["pt"] = f"%{product_type}%"
    if q:
        where.append("(protected_name ILIKE :q OR geographical_area ILIKE :q)"); params["q"] = f"%{q}%"
    if only_geo:
        where.append("geo_shape IS NOT NULL")
    return " AND ".join(where), params


def register_gi_details(router):
    @router.get(
        "/details",
        tags=["v2-geographical-indications"],
        summary="Search EU GI records with their production-area text, control body and geometry status",
        description=(
            "**What it does** — Lists EU geographical indications from the harvested detail table, "
            "each with the plain-language description of its delimited production area, the competent "
            "authority / control body (where known), and whether a mapped boundary exists.\n\n"
            "**When to use it** — To find GIs by country, type or product and see which have a resolved "
            "map boundary before fetching the geometry.\n\n"
            "**Input** — Optional filters: `country` (2-letter, e.g. ES), `gi_type` (PDO/PGI/GI), "
            "`product_type` (e.g. wine, cheese), `q` (free text over name and area), `has_geometry`. "
            "Paginated with `page` and `limit`.\n\n"
            "**Try it** — `/api/v2/geographical-indications/details?country=ES&has_geometry=true`\n\n"
            "**You get back** — A page of records: protected name, type, product, countries, status, "
            "competent authority, the area description, area in km2, and a `has_geometry` flag."
        ),
    )
    def list_details(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
        country: Optional[str] = Query(None, min_length=2, max_length=2),
        gi_type: Optional[str] = Query(None),
        product_type: Optional[str] = Query(None),
        q: Optional[str] = Query(None),
        has_geometry: Optional[bool] = Query(None),
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=200),
    ):
        where, params = _filters(country, gi_type, product_type, q, bool(has_geometry))
        total = db.execute(text(f"SELECT count(*) FROM gi_details WHERE {where}"), params).scalar()
        params.update(limit=limit, offset=(page - 1) * limit)
        rows = db.execute(text(
            f"SELECT {_DETAIL_COLS} FROM gi_details WHERE {where} "
            "ORDER BY protected_name LIMIT :limit OFFSET :offset"), params).mappings().all()
        return {"total": total, "page": page, "limit": limit,
                "items": [dict(r) for r in rows]}

    @router.get(
        "/details/{file_number}",
        tags=["v2-geographical-indications"],
        summary="Get one EU GI record with its full production-area text and control body",
        description=(
            "**What it does** — Returns a single GI's full detail record.\n\n"
            "**When to use it** — When you have a file number (e.g. from the list) and want the "
            "complete area description and metadata.\n\n"
            "**Input** — `file_number` in the path (e.g. PDO-ES-A1560).\n\n"
            "**Try it** — `/api/v2/geographical-indications/details/PDO-ES-A1560`\n\n"
            "**You get back** — The record: name, type, product, countries, status, EU protection date, "
            "competent authority, full geographical-area text, area km2 and geometry status."
        ),
    )
    def get_detail(
        file_number: str = PathParam(...),
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
    ):
        row = db.execute(text(
            f"SELECT {_DETAIL_COLS} FROM gi_details WHERE file_number = :fn"),
            {"fn": file_number}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="GI not found")
        return dict(row)

    @router.get(
        "/geometry",
        tags=["v2-geographical-indications"],
        summary="Get the mapped boundaries of EU GIs as GeoJSON (for maps)",
        description=(
            "**What it does** — Returns the resolved delimited areas of EU geographical indications as "
            "a standard GeoJSON FeatureCollection, ready to render on a map.\n\n"
            "**When to use it** — To draw GI production areas. Each feature's `confidence` says whether "
            "the boundary is municipality-precise or a province-level approximation.\n\n"
            "**Input** — Optional `country` (2-letter), `q` (name/area text), `precise_only` (only "
            "municipality-precise boundaries), `limit` (default 500, max 4000).\n\n"
            "**Try it** — `/api/v2/geographical-indications/geometry?country=ES&limit=200`\n\n"
            "**You get back** — `{type:'FeatureCollection', features:[...]}` in EPSG:4326; each feature's "
            "properties include name, gi_type, product_type, competent_authority, area_km2 and confidence."
        ),
    )
    def geometry(
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
        country: Optional[str] = Query(None, min_length=2, max_length=2),
        q: Optional[str] = Query(None),
        precise_only: bool = Query(False),
        limit: int = Query(500, ge=1, le=4000),
    ):
        where, params = ["geo_shape IS NOT NULL"], {"limit": limit}
        if country:
            where.append(":country = ANY(countries)"); params["country"] = country.upper()
        if q:
            where.append("protected_name ILIKE :q"); params["q"] = f"%{q}%"
        if precise_only:
            where.append("geo_geom_confidence IN ('name_lau','annex_lau','text_lau','exact_nuts')")
        rows = db.execute(text(
            "SELECT protected_name, gi_type, product_type, countries, competent_authority, "
            "round(geo_area_km2::numeric) AS area_km2, geo_geom_confidence, geo_geometry "
            f"FROM gi_details WHERE {' AND '.join(where)} ORDER BY protected_name LIMIT :limit"),
            params).mappings().all()
        feats = []
        for r in rows:
            f = dict(r["geo_geometry"] or {"type": "Feature", "geometry": None, "properties": {}})
            props = f.get("properties") or {}
            props.update(name=r["protected_name"], gi_type=r["gi_type"],
                         product_type=r["product_type"], countries=r["countries"],
                         competent_authority=r["competent_authority"], area_km2=r["area_km2"],
                         confidence=r["geo_geom_confidence"])
            f["properties"] = props
            feats.append(f)
        return {"type": "FeatureCollection", "features": feats}

    @router.get(
        "/geometry/{file_number}",
        tags=["v2-geographical-indications"],
        summary="Get one EU GI's mapped boundary as a GeoJSON Feature",
        description=(
            "**What it does** — Returns a single GI's resolved boundary as a GeoJSON Feature.\n\n"
            "**When to use it** — To draw or inspect one GI's production area.\n\n"
            "**Input** — `file_number` in the path.\n\n"
            "**Try it** — `/api/v2/geographical-indications/geometry/PDO-ES-A1560`\n\n"
            "**You get back** — A GeoJSON Feature (EPSG:4326) with name, type, product, competent "
            "authority, area km2 and confidence in its properties; 404 if the GI has no geometry yet."
        ),
    )
    def geometry_one(
        file_number: str = PathParam(...),
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
    ):
        r = db.execute(text(
            "SELECT protected_name, gi_type, product_type, countries, competent_authority, "
            "round(geo_area_km2::numeric) AS area_km2, geo_geom_confidence, geo_geometry "
            "FROM gi_details WHERE file_number = :fn AND geo_shape IS NOT NULL"),
            {"fn": file_number}).mappings().first()
        if not r:
            raise HTTPException(status_code=404, detail="GI geometry not found")
        f = dict(r["geo_geometry"] or {"type": "Feature", "geometry": None, "properties": {}})
        props = f.get("properties") or {}
        props.update(name=r["protected_name"], gi_type=r["gi_type"], product_type=r["product_type"],
                     countries=r["countries"], competent_authority=r["competent_authority"],
                     area_km2=r["area_km2"], confidence=r["geo_geom_confidence"])
        f["properties"] = props
        return f
