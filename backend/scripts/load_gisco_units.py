"""
Load GISCO administrative boundaries into `gisco_units` (PostGIS) — the boundary
lookup + multilingual name gazetteer that turns a GI's geographical_area text into
real geometry.

  NUTS 0-3 (~2,010 units) + LAU municipalities (~100k) from Eurostat GISCO.

Run:  python3.12 scripts/load_gisco_units.py --nuts    # NUTS (fast)
      python3.12 scripts/load_gisco_units.py --lau     # LAU (large)

Each unit stores every published name variant (native, Latin, EN/FR/DE) normalised
into `name_search` so matching lands regardless of the document's language.
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
from shapely.geometry import MultiPolygon
from sqlalchemy import create_engine, text

from core.config import settings

NUTS_URL = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_01M_2021_4326.geojson"
LAU_URL = "https://gisco-services.ec.europa.eu/distribution/v2/lau/geojson/LAU_RG_01M_2021_4326.geojson"


def norm(s) -> str:
    """Lowercase + strip accents for language-agnostic matching."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def _as_multi(geom):
    if geom is None:
        return None
    return geom if geom.geom_type == "MultiPolygon" else MultiPolygon([geom])


def _engine():
    # geopandas needs a SQLAlchemy engine; DATABASE_URL is a plain postgres URL
    url = settings.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
    return create_engine(url)


def load_nuts(engine, src: str):
    g = gpd.read_file(src).to_crs(4326)
    # NUTS_NAME (native) + NAME_LATN (Latin transliteration) ONLY. GISCO's
    # NAME_ENGL/FREN/GERM hold the COUNTRY name for sub-national units (Modena->"Italy"),
    # NOT a regional translation — including them poisons every unit's index with its
    # country name, so any text mentioning the country matches a random unit.
    name_cols = ["NUTS_NAME", "NAME_LATN"]

    def search_blob(row):
        vals = {norm(row.get(c)) for c in name_cols if row.get(c)}
        return " | ".join(sorted(v for v in vals if v))

    g["unit_code"] = g["NUTS_ID"]
    g["level"] = "NUTS" + g["LEVL_CODE"].astype(str)
    g["country"] = g["CNTR_CODE"]
    g["name"] = g["NUTS_NAME"]
    g["name_norm"] = g["NUTS_NAME"].map(norm)
    g["name_search"] = g.apply(search_blob, axis=1)
    g["nuts_parent"] = g.apply(lambda r: r["NUTS_ID"][:-1] if r["LEVL_CODE"] > 0 else None, axis=1)
    g["geometry"] = g["geometry"].map(_as_multi)

    out = g[["unit_code", "level", "country", "name", "name_norm", "name_search", "nuts_parent", "geometry"]]
    out = out.set_geometry("geometry")
    out.to_postgis("gisco_units", engine, if_exists="replace", index=False)
    print(f"[gisco] NUTS loaded: {len(out)} units", dict(g["level"].value_counts()))


def load_lau(engine, src: str):
    g = gpd.read_file(src).to_crs(4326)
    cols = {c.upper(): c for c in g.columns}
    code_c = cols.get("GISCO_ID") or cols.get("LAU_ID")
    name_c = cols.get("LAU_NAME") or cols.get("LAU_NAME_L") or cols.get("NAME")
    cntr_c = cols.get("CNTR_CODE")
    nuts_c = cols.get("NUTS3_CODE") or cols.get("NUTS3")

    g["unit_code"] = g[code_c].astype(str)
    g["level"] = "LAU"
    g["country"] = g[cntr_c] if cntr_c else g["unit_code"].str[:2]
    g["name"] = g[name_c] if name_c else None
    g["name_norm"] = g["name"].map(norm)
    g["name_search"] = g["name"].map(norm)
    g["nuts_parent"] = g[nuts_c] if nuts_c else None
    g["geometry"] = g["geometry"].map(_as_multi)

    out = g[["unit_code", "level", "country", "name", "name_norm", "name_search", "nuts_parent", "geometry"]].set_geometry("geometry")
    out.to_postgis("gisco_units", engine, if_exists="append", index=False)
    print(f"[gisco] LAU appended: {len(out)} units")


def add_indexes(engine):
    with engine.begin() as cx:
        cx.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_gisco_geom ON gisco_units USING gist (geometry)"))
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_gisco_search ON gisco_units USING gin (name_search gin_trgm_ops)"))
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_gisco_code ON gisco_units (unit_code)"))
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_gisco_ctry_lvl ON gisco_units (country, level)"))
    print("[gisco] indexes ready")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nuts", action="store_true")
    ap.add_argument("--lau", action="store_true")
    ap.add_argument("--src", help="local geojson path (skip download)")
    a = ap.parse_args()
    engine = _engine()
    if a.nuts:
        load_nuts(engine, a.src or NUTS_URL)
        add_indexes(engine)
    if a.lau:
        load_lau(engine, a.src or LAU_URL)
        add_indexes(engine)


if __name__ == "__main__":
    main()
