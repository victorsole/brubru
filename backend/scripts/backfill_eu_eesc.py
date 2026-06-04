"""
Backfill ``eu_eesc_opinions`` from Cellar (metadata-only first pass).

Universe: every CELEX matching pattern ``5{YYYY}AE{NNNN}`` — the formal output
of the European Economic and Social Committee. Cellar coverage is 3,617
opinions as of May 2026.

This is a METADATA-ONLY pass. Cellar serves the EESC catalogue but the
opinions' actual bodies live on eesc.europa.eu (Drupal pages), not in Cellar
manifestations. A separate ``enrich_eu_eesc_bodies.py`` script handles the
body fetch from eesc.europa.eu.

Per record we:
  1. Pull title + date + work URI from one bulk SPARQL query (10k cap is
     above the 3,617 universe size — single fetch).
  2. Classify document_type from title.
  3. Set own_initiative flag.
  4. Extract Commission proposal CELEX from title (best-effort).
  5. UPSERT.

Run:
    python3.12 backend/scripts/backfill_eu_eesc.py            # dry-run, 10 rows
    python3.12 backend/scripts/backfill_eu_eesc.py --apply    # full backfill
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote as _urlquote

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

CELEX_PATTERN = re.compile(r"^5\d{4}AE[0-9R().]+$")


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


# ─────────────────────── Title classification ────────────────────────────


_TYPE_PATTERNS = [
    (re.compile(r"information report", re.I), "information_report"),
    (re.compile(r"^Resolution\b|\bResolution of\b", re.I), "resolution"),
    (re.compile(r"position paper", re.I), "position_paper"),
    (re.compile(r"plenary session.*summary|summary of plenary", re.I), "plenary_summary"),
    (re.compile(r"exploratory opinion", re.I), "exploratory_opinion"),
    (re.compile(r"\bopinion\b", re.I), "opinion"),
]


def classify_eesc(title: Optional[str]) -> str:
    if not title:
        return "opinion"
    for pat, label in _TYPE_PATTERNS:
        if pat.search(title):
            return label
    return "opinion"


_OWN_INITIATIVE = re.compile(r"own[\s\-]initiative|on its own initiative|\(initiative\)", re.I)


def is_own_initiative(title: Optional[str]) -> bool:
    return bool(title) and bool(_OWN_INITIATIVE.search(title))


_COM_REF = re.compile(r"COM\s*\((\d{4})\)\s*(\d{1,4})\s*final", re.I)


def extract_com_ref(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    m = _COM_REF.search(title)
    if not m:
        return None
    return f"COM({m.group(1)}) {int(m.group(2))} final"


def derive_celex_from_com(com_ref: Optional[str]) -> Optional[str]:
    if not com_ref:
        return None
    m = re.match(r"COM\((\d{4})\)\s*(\d+)", com_ref)
    if not m:
        return None
    return f"5{m.group(1)}PC{int(m.group(2)):04d}"


# ─────────────────────── Section extraction ──────────────────────────────


# EESC sections — most common abbreviations
_EESC_SECTIONS = ["ECO", "INT", "REX", "NAT", "SOC", "TEN", "CCMI"]
_SECTION_PATTERNS = [
    (re.compile(rf"\b{s}/[\d-]+\b"), s) for s in _EESC_SECTIONS
]


def extract_section(title: Optional[str]) -> Optional[str]:
    # Section codes rarely appear in titles; left for HTML-enrichment pass
    return None


# ─────────────────────── Cellar SPARQL universe ──────────────────────────


SPARQL_LIST = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

SELECT DISTINCT ?work ?celex ?date ?title ?resourceType WHERE {
  ?work cdm:resource_legal_id_celex ?celex .
  FILTER(REGEX(STR(?celex), "^5[0-9]{4}AE[0-9R().]+$"))
  OPTIONAL { ?work cdm:work_date_document ?date }
  OPTIONAL { ?work cdm:work_has_resource-type ?resourceType }
  OPTIONAL {
    ?expr cdm:expression_belongs_to_work ?work .
    ?expr cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
    ?expr cdm:expression_title ?title .
  }
}
ORDER BY DESC(?date)
LIMIT 10000
"""


SPARQL_EUROVOC = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

SELECT ?celex (GROUP_CONCAT(DISTINCT STR(?concept); SEPARATOR=",") AS ?concepts) WHERE {
  ?work cdm:resource_legal_id_celex ?celex .
  FILTER(REGEX(STR(?celex), "^5[0-9]{4}AE[0-9R().]+$"))
  ?work cdm:work_is_about_concept_eurovoc ?concept .
}
GROUP BY ?celex
"""


SPARQL_LANGS = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

SELECT ?celex (GROUP_CONCAT(DISTINCT STR(?lang); SEPARATOR=",") AS ?langs) WHERE {
  ?work cdm:resource_legal_id_celex ?celex .
  FILTER(REGEX(STR(?celex), "^5[0-9]{4}AE[0-9R().]+$"))
  ?expr cdm:expression_belongs_to_work ?work .
  ?expr cdm:expression_uses_language ?lang .
}
GROUP BY ?celex
"""


def _sparql_post(query: str, timeout: int = 180) -> dict:
    req = urllib_request.Request(
        "http://publications.europa.eu/webapi/rdf/sparql",
        data=("query=" + _urlquote(query)).encode("utf-8"),
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib_request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _lang_uri_to_iso3(uri: str) -> str:
    """http://publications.europa.eu/resource/authority/language/ENG → ENG"""
    return uri.rsplit("/", 1)[-1] if uri else ""


def fetch_universe() -> list[dict]:
    """Pull base list (CELEX, title, date, resource-type)."""
    data = _sparql_post(SPARQL_LIST)
    rows = data.get("results", {}).get("bindings", [])
    by_celex: dict[str, dict] = {}
    for b in rows:
        celex = b.get("celex", {}).get("value", "")
        if not CELEX_PATTERN.match(celex):
            continue
        work = b.get("work", {}).get("value", "")
        date_v = b.get("date", {}).get("value", "")
        title = b.get("title", {}).get("value", "")
        rtype = b.get("resourceType", {}).get("value", "")
        existing = by_celex.get(celex)
        if existing:
            if title and not existing.get("title"):
                by_celex[celex] = {
                    "celex": celex, "work_uri": work, "title": title,
                    "date": date_v or existing.get("date"),
                    "resource_type_uri": rtype or existing.get("resource_type_uri"),
                }
        else:
            by_celex[celex] = {
                "celex": celex, "work_uri": work, "title": title,
                "date": date_v, "resource_type_uri": rtype,
            }
    return list(by_celex.values())


def fetch_eurovoc_map() -> dict[str, list[str]]:
    """{celex: [eurovoc_uri, ...]} — one bulk query."""
    try:
        data = _sparql_post(SPARQL_EUROVOC)
    except Exception as e:
        print(f"[warn] EuroVoc bulk query failed: {e!s}", flush=True)
        return {}
    out: dict[str, list[str]] = {}
    for b in data.get("results", {}).get("bindings", []):
        celex = b.get("celex", {}).get("value", "")
        concepts = b.get("concepts", {}).get("value", "")
        if celex and concepts:
            out[celex] = [c for c in concepts.split(",") if c]
    return out


def fetch_langs_map() -> dict[str, list[str]]:
    """{celex: [ENG, FRA, ...]}"""
    try:
        data = _sparql_post(SPARQL_LANGS)
    except Exception as e:
        print(f"[warn] languages bulk query failed: {e!s}", flush=True)
        return {}
    out: dict[str, list[str]] = {}
    for b in data.get("results", {}).get("bindings", []):
        celex = b.get("celex", {}).get("value", "")
        langs = b.get("langs", {}).get("value", "")
        if celex and langs:
            out[celex] = sorted({_lang_uri_to_iso3(u) for u in langs.split(",") if u})
    return out


# ─────────────────────── DB UPSERT ───────────────────────────────────────


UPSERT_SQL = """
INSERT INTO eu_eesc_opinions (
    celex, work_uri, title, document_date, document_type,
    resource_type_uri,
    own_initiative, related_com_ref, related_celex,
    available_languages, eurovoc_concepts,
    eurlex_url,
    has_body,
    updated_at
) VALUES (
    %(celex)s, %(work_uri)s, %(title)s, %(document_date)s, %(document_type)s,
    %(resource_type_uri)s,
    %(own_initiative)s, %(related_com_ref)s, %(related_celex)s,
    %(available_languages)s, %(eurovoc_concepts)s,
    %(eurlex_url)s,
    false,
    NOW()
)
ON CONFLICT (celex) DO UPDATE SET
    work_uri = COALESCE(EXCLUDED.work_uri, eu_eesc_opinions.work_uri),
    title = COALESCE(EXCLUDED.title, eu_eesc_opinions.title),
    document_date = COALESCE(EXCLUDED.document_date, eu_eesc_opinions.document_date),
    document_type = EXCLUDED.document_type,
    resource_type_uri = COALESCE(EXCLUDED.resource_type_uri, eu_eesc_opinions.resource_type_uri),
    own_initiative = EXCLUDED.own_initiative,
    related_com_ref = COALESCE(EXCLUDED.related_com_ref, eu_eesc_opinions.related_com_ref),
    related_celex = COALESCE(EXCLUDED.related_celex, eu_eesc_opinions.related_celex),
    available_languages = EXCLUDED.available_languages,
    eurovoc_concepts = EXCLUDED.eurovoc_concepts,
    eurlex_url = EXCLUDED.eurlex_url,
    updated_at = NOW();
"""


def to_iso(value: Any) -> Optional[str]:
    if not value:
        return None
    s = str(value).split("T")[0]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else None


def _open_db():
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing", file=sys.stderr)
        sys.exit(1)
    return psycopg2.connect(db, connect_timeout=15)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Run full backfill (default: dry-run, 10 rows)")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    print("[INFO] Pulling EESC CELEX universe (5{YYYY}AE...) via Cellar SPARQL...", flush=True)
    universe = fetch_universe()
    print(f"[INFO] {len(universe):,} EESC opinions", flush=True)

    print("[INFO] Pulling EuroVoc concepts via bulk SPARQL...", flush=True)
    eurovoc = fetch_eurovoc_map()
    print(f"[INFO] {len(eurovoc):,} rows have EuroVoc concepts", flush=True)

    print("[INFO] Pulling available languages via bulk SPARQL...", flush=True)
    langs = fetch_langs_map()
    print(f"[INFO] {len(langs):,} rows have language info", flush=True)

    if not args.apply:
        universe = universe[: args.limit]

    conn = _open_db()
    cur = conn.cursor()

    counts = {"upserted": 0, "errors": 0, "no_title": 0, "own_initiative": 0, "linked": 0}
    type_dist: dict[str, int] = {}

    for i, row in enumerate(universe, 1):
        celex = row["celex"]
        title = row.get("title")
        if not title:
            counts["no_title"] += 1

        doc_type = classify_eesc(title)
        type_dist[doc_type] = type_dist.get(doc_type, 0) + 1
        own_ini = is_own_initiative(title)
        if own_ini:
            counts["own_initiative"] += 1
        com_ref = extract_com_ref(title)
        rel_celex = derive_celex_from_com(com_ref)
        if rel_celex:
            counts["linked"] += 1

        params = {
            "celex": celex,
            "work_uri": row.get("work_uri"),
            "title": title,
            "document_date": to_iso(row.get("date")),
            "document_type": doc_type,
            "resource_type_uri": row.get("resource_type_uri"),
            "own_initiative": own_ini,
            "related_com_ref": com_ref,
            "related_celex": rel_celex,
            "available_languages": langs.get(celex, []),
            "eurovoc_concepts": eurovoc.get(celex, []),
            "eurlex_url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
        }
        try:
            cur.execute(UPSERT_SQL, params)
            conn.commit()
            counts["upserted"] += 1
        except Exception as exc:
            conn.rollback()
            print(f"  [{i:5}/{len(universe)}] {celex}: UPSERT error {exc!s}", flush=True)
            counts["errors"] += 1

        if i % 250 == 0 or i == len(universe):
            print(f"  [{i:5}/{len(universe)}] {celex}: type={doc_type} | upserted={counts['upserted']} errors={counts['errors']}",
                  flush=True)

    cur.close()
    conn.close()
    print("\n[DONE]")
    print(f"  Upserted: {counts['upserted']:,}")
    print(f"  Errors:   {counts['errors']}")
    print(f"  No-title: {counts['no_title']}")
    print(f"  Own-initiative: {counts['own_initiative']:,}")
    print(f"  Linked to Commission proposal: {counts['linked']:,}")
    print(f"  Type distribution: {type_dist}")


if __name__ == "__main__":
    main()
