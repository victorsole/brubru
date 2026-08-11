"""One-shot ingestion of the five acts of the Digital Product Passport regime that
were missing from eu_laws.

Found 11 August 2026 while building the /api/v2/dpp surface. Commission Implementing
Regulation (EU) 2026/1778 Article 1 names exactly which legislation obliges an operator
to register a passport in the central DPP registry. Four of the five acts it names were
absent from eu_laws, so Brubru could not answer "which laws put my product in the DPP
registry" from its own corpus:

    32024R1252  Critical Raw Materials Act
    32025R2509  Toy Safety Regulation                  (registry hook: Art. 19)
    32024R3110  Construction Products Regulation       (registry hook: Art. 76)
    32026R0405  Detergents and surfactants Regulation  (registry hook: Art. 21)
    32026D1736  Implementing Decision on DPP harmonised standards

Metadata is resolved LIVE from the Publications Office Cellar SPARQL graph rather than
from the LEG_2025-11 Formex export, because three of these acts post-date that export
(Nov 2025) and would otherwise be unavailable at all. Cellar is authoritative and free
of the EUR-Lex JS WAF.

Two traps this script is written around:

  * `eu_laws.search_vector` is GENERATED ALWAYS but is writable on the ORM model, so an
    ORM insert ALWAYS raises. Rows are inserted with an EXPLICIT column list.
    See memory/feedback_eu_laws_orm_insert_impossible.md.
  * OJ references are NOT guessed. Where Cellar does not return one, the column is left
    NULL and the authoritative ELI permalink carries the citation instead. Inventing an
    OJ string would be a fabricated citation.

Idempotent: an act already present is reported and skipped, never duplicated.

Usage:
    python3.12 -m backend.scripts._ingest_dpp_regime_oneshot --dry-run
    python3.12 -m backend.scripts._ingest_dpp_regime_oneshot --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal
from services.api_clients.cellar_sparql_client import CellarSPARQLClient

CORPUS_VERSION = "DPP_TEX_2026-08"
REGISTERED_BY = "_ingest_dpp_regime_oneshot.py"

# celex -> what it is in the DPP regime. `registry_hook` is the article that pulls the
# product into the central registry per Implementing Regulation (EU) 2026/1778 Art. 1.
ACTS: Dict[str, Dict[str, Any]] = {
    "32024R1252": {
        "label": "Critical Raw Materials Act",
        "policy_area": "Internal Market",
        "registry_hook": None,
        "dpp_role": "supply-chain and circularity duties on critical raw materials; "
                    "referenced by the DPP information layer",
        # This act IS in the LEG_2025-11 export, but the multi-file Formex import
        # produced a fragment row titled "ANNEX III" with celex NULL and never
        # created the parent. Promote that row instead of inserting a duplicate,
        # exactly as _ingest_dpp_parents_oneshot.py did for the ESPR.
        "corpus_uuid": "aa3c49f7-08e7-11ef-a251-01aa75ed71a1",
    },
    "32025R2509": {
        "label": "Toy Safety Regulation",
        "policy_area": "Internal Market",
        "registry_hook": "Article 19",
        "dpp_role": "requires a digital product passport for toys, registered in the "
                    "registry set up under ESPR Article 13",
    },
    "32024R3110": {
        "label": "Construction Products Regulation",
        "policy_area": "Internal Market",
        "registry_hook": "Article 76",
        "dpp_role": "requires a digital product passport for construction products, "
                    "registered in the registry set up under ESPR Article 13",
        # Same multi-file Formex bug: the fragment row is titled
        # "Official Journal of the European Union" with celex NULL.
        "corpus_uuid": "a860ee13-bce2-11ef-91ed-01aa75ed71a1",
    },
    "32026R0405": {
        "label": "Detergents and surfactants Regulation",
        "policy_area": "Internal Market",
        "registry_hook": "Article 21",
        "dpp_role": "requires a digital product passport for detergents and end-user "
                    "surfactants, registered in the registry set up under ESPR Art. 13",
    },
    "32026D1736": {
        "label": "Implementing Decision on DPP harmonised standards",
        "policy_area": "Internal Market",
        "registry_hook": None,
        "dpp_role": "lists the harmonised standards carrying a presumption of conformity "
                    "for digital product passport requirements under ESPR",
    },
    "32011R1007": {
        "label": "Textile Labelling Regulation",
        "policy_area": "Internal Market",
        "registry_hook": None,
        "dpp_role": "the existing baseline for textile fibre composition information: "
                    "fibre names, labelling and marking. The textile digital product "
                    "passport builds on the data this regulation already mandates",
        # Third instance of the same multi-file Formex bug: the parent is absent and
        # the corpus uuid is held by a fragment titled "ANNEX I" with celex NULL,
        # while an Addendum (id 7263) and a Corrigendum (id 14548) sit as separate
        # celex-NULL rows.
        "corpus_uuid": "85f446fd-05a5-47d7-b0d3-96418710a1e0",
    },
}

# Cellar resource-type URI tail -> the doc_type vocabulary already used in eu_laws.
_DOC_TYPE = {
    "REG": "Regulation",
    "REG_IMPL": "Commission Implementing Regulation",
    "REG_DEL": "Commission Delegated Regulation",
    "DEC": "Decision",
    "DEC_IMPL": "Commission Implementing Decision",
    "DIR": "Directive",
}

_INSERT = text(
    """
    INSERT INTO eu_laws (
        uuid, celex, doc_type, title, date, oj_reference, policy_area,
        extra_metadata, created_at, updated_at, is_primary_legislation,
        celex_year, celex_type, celex_number, doc_type_normalized,
        corpus_version, corpus_status, xml_path
    ) VALUES (
        :uuid, :celex, :doc_type, :title, :date, :oj_reference, :policy_area,
        CAST(:extra_metadata AS jsonb), :created_at, :updated_at, :is_primary_legislation,
        :celex_year, :celex_type, :celex_number, :doc_type_normalized,
        :corpus_version, :corpus_status, :xml_path
    )
    """
)


_PATCH = text(
    """
    UPDATE eu_laws SET
        celex = :celex,
        doc_type = :doc_type,
        title = :title,
        date = :date,
        oj_reference = COALESCE(:oj_reference, oj_reference),
        policy_area = :policy_area,
        extra_metadata = COALESCE(extra_metadata, '{}'::jsonb) || CAST(:extra_metadata AS jsonb),
        updated_at = :updated_at,
        is_primary_legislation = :is_primary_legislation,
        celex_year = :celex_year,
        celex_type = :celex_type,
        celex_number = :celex_number,
        doc_type_normalized = :doc_type_normalized,
        corpus_status = :corpus_status
    WHERE id = :id
    """
)


def _clean(s: Optional[str]) -> Optional[str]:
    """Cellar titles carry non-breaking spaces; normalise them."""
    if not s:
        return None
    return " ".join(s.replace(" ", " ").split())


def _uuid_from_work(work_uri: Optional[str]) -> Optional[str]:
    if not work_uri:
        return None
    return work_uri.rstrip("/").rsplit("/", 1)[-1]


def _doc_type_from_uri(uri: Optional[str]) -> str:
    if not uri:
        return "Regulation"
    return _DOC_TYPE.get(uri.rstrip("/").rsplit("/", 1)[-1].upper(), "Regulation")


async def _resolve_oj_reference(client: CellarSPARQLClient, celex: str) -> Optional[str]:
    """Best-effort OJ citation from Cellar. Returns None rather than a guess."""
    query = f"""
    PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
    SELECT ?ojClass ?ojYear ?ojNumber ?ojDate
    WHERE {{
        ?work cdm:resource_legal_id_celex ?celexLit .
        FILTER(STR(?celexLit) = "{celex}")
        OPTIONAL {{ ?work cdm:resource_legal_published_in_official-journal ?oj .
                   OPTIONAL {{ ?oj cdm:official-journal_class ?ojClass . }}
                   OPTIONAL {{ ?oj cdm:official-journal_year ?ojYear . }}
                   OPTIONAL {{ ?oj cdm:official-journal_number ?ojNumber . }}
                   OPTIONAL {{ ?oj cdm:work_date_document ?ojDate . }} }}
    }}
    LIMIT 1
    """
    try:
        rows = await client._cached_select(query, cache_ttl=86400)
    except Exception as exc:  # noqa: BLE001
        print(f"    [INFO] OJ lookup failed ({type(exc).__name__}); leaving NULL")
        return None
    if not rows:
        return None
    r = rows[0]
    cls, year, num, ojdate = (
        r.get("ojClass"), r.get("ojYear"), r.get("ojNumber"), r.get("ojDate"),
    )
    if not (cls and year and num):
        return None
    ref = f"OJ {cls} {num}, {year}"
    if ojdate:
        ref = f"OJ {cls} {num}, {ojdate}"
    return ref


async def resolve(celex: str) -> Optional[Dict[str, Any]]:
    async with CellarSPARQLClient() as client:
        meta = await client.get_celex_metadata(celex)
        if not meta:
            return None
        meta["_oj_reference"] = await _resolve_oj_reference(client, celex)
        return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="resolve and report, write nothing")
    g.add_argument("--apply", action="store_true", help="insert the missing rows")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    inserted = patched = skipped = failed = 0

    try:
        for celex, spec in ACTS.items():
            print(f"\n=== {celex}  ({spec['label']}) ===")

            present = db.execute(
                text("SELECT id, title FROM eu_laws WHERE celex = :c"), {"c": celex}
            ).fetchone()
            if present:
                print(f"  [SKIP] already present: id={present[0]}")
                skipped += 1
                continue

            meta = asyncio.run(resolve(celex))
            if not meta:
                print("  [FAIL] Cellar returned no metadata")
                failed += 1
                rc = 1
                continue

            title = _clean(meta.get("title"))
            if not title:
                print("  [FAIL] no title from Cellar; refusing to insert a titleless act")
                failed += 1
                rc = 1
                continue

            doc_type = _doc_type_from_uri(meta.get("resourceTypeUri"))
            oj_ref = meta.get("_oj_reference")
            row = {
                "uuid": _uuid_from_work(meta.get("work")),
                "celex": celex,
                "doc_type": doc_type,
                "title": title,
                "date": meta.get("date"),
                "oj_reference": oj_ref,
                "policy_area": spec["policy_area"],
                "extra_metadata": _json(
                    {
                        "registered_by": REGISTERED_BY,
                        "source": "cellar_sparql",
                        "eli": meta.get("eli"),
                        "in_force": meta.get("in_force"),
                        "entry_into_force": meta.get("dateInForce"),
                        "dpp_role": spec["dpp_role"],
                        "dpp_registry_hook": spec["registry_hook"],
                        "dpp_registry_hook_source": "32026R1778 Art. 1",
                    }
                ),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "is_primary_legislation": True,
                "celex_year": int(celex[1:5]),
                "celex_type": celex[5],
                "celex_number": int(celex[6:]),
                "doc_type_normalized": doc_type,
                "corpus_version": CORPUS_VERSION,
                "corpus_status": "active",
                # eu_laws.xml_path is NOT NULL. These acts have no Formex file in the
                # LEG_2025-11 export, so they carry the cellar:// pseudo-path already
                # used by the DPP rows ingested on 6 Aug 2026.
                "xml_path": f"cellar://publications.europa.eu/resource/celex/{celex}",
            }

            print(f"  title : {title[:88]}")
            print(f"  date  : {row['date']}   type: {doc_type}   eli: {meta.get('eli')}")
            print(f"  oj    : {oj_ref if oj_ref else 'NULL (not resolved; ELI carries the citation)'}")
            print(f"  hook  : {spec['registry_hook'] or 'n/a'}")

            # A corpus act already occupies its cellar uuid as a mis-parsed fragment
            # row. Promote that row rather than inserting a duplicate act.
            corpus_uuid = spec.get("corpus_uuid")
            stray = None
            if corpus_uuid:
                stray = db.execute(
                    text("SELECT id, celex, title, xml_path FROM eu_laws WHERE uuid = :u"),
                    {"u": corpus_uuid},
                ).fetchone()

            if stray is not None:
                if stray[1] not in (None, ""):
                    print(f"  [FAIL] uuid {corpus_uuid} holds celex={stray[1]}, "
                          f"not a stray fragment. Refusing to overwrite.")
                    failed += 1
                    rc = 1
                    continue
                print(f"  mode  : PATCH existing fragment row id={stray[0]} "
                      f"(was title={stray[2]!r}, celex=NULL)")
                print(f"  xml   : keeping local Formex {str(stray[3])[:70]}")
            else:
                print("  mode  : INSERT new row")

            if args.dry_run:
                print("  [DRY-RUN] not written")
                continue

            if stray is not None:
                db.execute(_PATCH, {**row, "id": stray[0]})
                db.commit()
                patched += 1
                print(f"  [OK] patched id={stray[0]}")
            else:
                db.execute(_INSERT, row)
                db.commit()
                inserted += 1
                print("  [OK] inserted")

        # ---- verification ----
        print("\n=== verification ===")
        for celex in ACTS:
            n = db.execute(
                text("SELECT count(*) FROM eu_laws WHERE celex = :c"), {"c": celex}
            ).scalar()
            if args.dry_run:
                # nothing was written, so 0 is the expected state here
                state = "not yet ingested" if n == 0 else "already present"
            else:
                state = "OK" if n == 1 else "PROBLEM"
                if n != 1:
                    rc = 1
            print(f"  {celex}: {n} row(s) {state}")

        print(f"\ninserted={inserted} patched={patched} skipped={skipped} failed={failed}")
    finally:
        db.close()
    return rc


def _json(d: Dict[str, Any]) -> str:
    import json

    return json.dumps(d, default=str)


if __name__ == "__main__":
    sys.exit(main())
