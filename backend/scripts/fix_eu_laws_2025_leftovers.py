#!/usr/bin/env python3.12
"""The 29 LEG_2025-11 rows without CELEX left by step 3: keep the one law, delete the 28 others (15 Oct 2026).

Each row's folder uuid was looked up at Cellar (SPARQL, 29 of 29 found). None is in force, so none is in the
October 2026 export (the export is the law in force); the acts behind the corrigenda ended between 18 Nov 2025
and 17 Aug 2026:
  - id 14600 is the Dublin III Regulation, 32013R0604 (ended 11 June 2026, repealed by Regulation 2024/1351).
    The 2025 import filled it from the joint statement printed after it: no CELEX, the statement's title,
    policy area, subject words ("THE", "BY", "AND"), page numbers, hash and empty legal basis and citations.
    It gets its CELEX, its English title from Cellar, its type and status 'repealed' (like the 290 repealed
    rows the table keeps); everything taken from the statement is cleared, not guessed. Its xml_path (NOT
    NULL) still names the statement's file in the deleted docs/LEG_2025-11 copy: Cellar names the Formex items
    DOC_1 to DOC_5, so the regulation's own file name cannot be verified. The body and EuroVoc jobs fill
    rows with a CELEX and no fetch date.
  - The 28 others are not laws by the canonical definition (all carry a suffix): 15 corrigenda (14 R(01),
    1 R(02)) of acts that ended, 12 decisions with a "(01)" suffix (Council board appointments, Commission
    expert groups, an EP Bureau decision ended 2014, an Energy Community decision, a model agreement) and
    1 EP-Commission agreement. Deleted.
  - id 2922 (a 2023 EFSA Management Board appointment) is linked to EU Law Comply cluster 20 "Food & AgTech
    Startup Compliance" with one requirement ("enters into force on adoption", marked critical): a mis-link,
    removed with the row.
Victor's choice, 15 Oct 2026: keep the law, drop the rest.

Dry run by default. --apply writes a JSON backup (all columns of the 29 rows, the link, the requirement),
checks that no other column holds the 28 rows' uuids (uuid, uuid[] and *uuid text columns, parent_law_uuid
included) or ids (*law_id columns) and that nothing cascades from the requirement (gap_findings,
compliance_actions), does everything in one transaction, checks each count and re-measures.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.fix_eu_laws_2025_leftovers [--apply]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402
from backend.models.eu_law import EULaw  # noqa: E402
from backend.scripts.repair_eu_laws_celex_vs_folder import normalized  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
LAW = {"id": 14600, "uuid": "8282011e-e08b-11e2-9165-01aa75ed71a1", "celex": "32013R0604", "doc_type": "Regulation (EU) No"}
DROP = [1689, 2175, 2922, 4437, 5833, 5867, 6859, 7748, 9025, 11167, 11411, 11847, 12712, 13469, 14878,
        15495, 16138, 16152, 17122, 18139, 18531, 18703, 21969, 23764, 24126, 26545, 26694, 28280]
LINK = {"cluster_id": 20, "law_id": 2922}
REQUIREMENT = 3446
STATEMENT_KEYS = ("page_first", "page_last", "page_count")


def cellar_title(celex: str) -> str:
    q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> SELECT ?t WHERE { "
         f'?w cdm:resource_legal_id_celex "{celex}"^^<http://www.w3.org/2001/XMLSchema#string> . '
         "?e cdm:expression_belongs_to_work ?w ; "
         "cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ; "
         "cdm:expression_title ?t }")
    req = urllib.request.Request(SPARQL + "?" + urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"}),
                                 headers={"Accept": "application/sparql-results+json"})
    titles = {b["t"]["value"] for b in json.load(urllib.request.urlopen(req, timeout=120))["results"]["bindings"]}
    check(len(titles) == 1, f"Cellar gave {len(titles)} English titles for {celex}")
    return re.sub(r"\s+", " ", titles.pop()).strip()  # non-breaking spaces to plain, like the stored titles


def check(ok: bool, msg: str) -> None:
    """A guard that holds under python -O, unlike assert."""
    if not ok:
        raise RuntimeError(msg)


def other_references(db, uuids, ids):
    """(table.column, hits) for every column that could hold one of the rows: uuid and uuid[] columns, text columns
    named *uuid (eu_laws.uuid and parent_law_uuid are varchar), and integer *law_id columns; eu_laws.uuid excluded."""
    cols = db.execute(text(
        "SELECT c.table_name, c.column_name, c.data_type, c.udt_name FROM information_schema.columns c "
        "JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
        "WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE' "
        "AND NOT (c.table_name = 'eu_laws' AND c.column_name = 'uuid') "
        "AND (c.udt_name IN ('uuid', '_uuid') "
        "OR (c.data_type IN ('character varying', 'text') AND c.column_name LIKE '%uuid%') "
        "OR (c.column_name LIKE '%law_id' AND c.data_type IN ('integer', 'bigint')))")).fetchall()
    hits = []
    for t, c, d, u in cols:
        if u == "_uuid":
            where, p = f'"{c}"::text[] && CAST(:u AS text[])', {"u": uuids}
        elif d in ("integer", "bigint"):
            where, p = f'"{c}" = ANY(:i)', {"i": ids}
        else:
            where, p = f'"{c}"::text = ANY(:u)', {"u": uuids}
        n = db.execute(text(f'SELECT count(*) FROM public."{t}" WHERE {where}'), p).scalar()
        if n:
            hits.append((f"{t}.{c}", n))
    return hits, len(cols)


def cascades_from_requirement(db, rid):
    """Rows in tables whose FK to law_requirements cascades: deleting the requirement would delete them unseen."""
    fks = db.execute(text(
        "SELECT conrelid::regclass::text, a.attname FROM pg_constraint k JOIN pg_attribute a "
        "ON a.attrelid = k.conrelid AND a.attnum = k.conkey[1] WHERE k.confrelid = 'law_requirements'::regclass")).fetchall()
    return {f"{t}.{c}": db.execute(text(f'SELECT count(*) FROM {t} WHERE "{c}" = :r'), {"r": rid}).scalar() for t, c in fks}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, uuid::text, coalesce(celex, ''), corpus_version FROM eu_laws WHERE id = ANY(:i)"),
                          {"i": DROP + [LAW["id"]]}).fetchall()
        check(len(rows) == 29 and all(not c and v == "LEG_2025-11" for _, _, c, v in rows), "the 29 rows moved since the check: stopped")
        check(next(u for i, u, _, _ in rows if i == LAW["id"]) == LAW["uuid"], "id 14600 is not the Dublin III folder: stopped")
        check(not db.execute(text("SELECT count(*) FROM eu_laws WHERE celex = :c"), {"c": LAW["celex"]}).scalar(), f"{LAW['celex']} is already held")
        drop_uuids = [u for i, u, _, _ in rows if i in DROP]
        expected = {("cluster_laws.law_id", 1), ("law_requirements.law_id", 1)}
        hits, n_cols = other_references(db, drop_uuids, DROP)
        cascades = cascades_from_requirement(db, REQUIREMENT)
        title = cellar_title(LAW["celex"])
        print(f"[INFO] keep id {LAW['id']} as {LAW['celex']} 'repealed': {title[:110]}...")
        print(f"[INFO] delete {len(DROP)} rows | references in {n_cols} uuid and law_id columns: {hits} (expected: the EFSA link and requirement)"
              f" | rows hanging from requirement {REQUIREMENT}: {cascades}")
        check(set(hits) == expected, f"unexpected references: {hits}")
        check(cascades and not any(cascades.values()), f"rows would cascade from requirement {REQUIREMENT}: {cascades}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        cols = [c.name for c in EULaw.__table__.columns if c.name != "search_vector"]
        before = [dict(r) for r in db.execute(text(f"SELECT {', '.join(cols)} FROM eu_laws WHERE id = ANY(:i)"), {"i": DROP + [LAW["id"]]}).mappings()]
        link = [dict(r) for r in db.execute(text("SELECT * FROM cluster_laws WHERE law_id = ANY(:i)"), {"i": DROP}).mappings()]
        req = [dict(r) for r in db.execute(text("SELECT * FROM law_requirements WHERE law_id = ANY(:i)"), {"i": DROP}).mappings()]
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
        backup = ROOT / f"backend/data/backups/eu_laws_2025_leftovers_before_{ts}.json"
        backup.write_text(json.dumps({"rows_before": before, "cluster_laws": link, "law_requirements": req}, default=str, indent=1))
        print(f"[OK] backup of {len(before)} rows, {len(link)} link, {len(req)} requirement -> {backup.relative_to(ROOT)}")

        counts = "SELECT (SELECT count(*) FROM eu_laws), (SELECT count(*) FROM cluster_laws), (SELECT count(*) FROM law_requirements)"
        n0 = db.execute(text(counts)).one()
        done = {
            "requirement": db.execute(text("DELETE FROM law_requirements WHERE id = :r AND law_id = :l"), {"r": REQUIREMENT, "l": LINK["law_id"]}).rowcount,
            "link": db.execute(text("DELETE FROM cluster_laws WHERE cluster_id = :cluster_id AND law_id = :law_id"), LINK).rowcount,
            "rows": db.execute(text("DELETE FROM eu_laws WHERE id = ANY(:i) AND coalesce(celex, '') = ''"), {"i": DROP}).rowcount,
            "law": db.execute(text(
                "UPDATE eu_laws SET celex = :c, title = :t, doc_type = :d, doc_type_normalized = :n, corpus_status = 'repealed', "
                "policy_area = NULL, subject_matter = NULL, legal_basis = NULL, citations = NULL, content_hash = NULL, "
                "extra_metadata = extra_metadata - CAST(:k AS text[]) "
                "WHERE id = :i AND coalesce(celex, '') = ''"),
                {"c": LAW["celex"], "t": title, "d": LAW["doc_type"], "n": normalized(LAW["doc_type"]), "k": list(STATEMENT_KEYS), "i": LAW["id"]}).rowcount,
        }
        n1 = db.execute(text(counts)).one()
        check(done == {"requirement": 1, "link": 1, "rows": 28, "law": 1}, f"changed {done}: rolled back")
        check(tuple(n0) == (n1[0] + 28, n1[1] + 1, n1[2] + 1), f"counts {tuple(n0)} -> {tuple(n1)}: rolled back")
        db.commit()
        print(f"[OK] committed: {done}")
        left = db.execute(text("SELECT count(*) FROM eu_laws WHERE coalesce(celex, '') = ''")).scalar()
        law = db.execute(text("SELECT celex, corpus_status, doc_type_normalized, left(title, 40) FROM eu_laws WHERE id = :i"), {"i": LAW["id"]}).one()
        print(f"[VERIFY] eu_laws {n1[0]}, cluster_laws {n1[1]}, law_requirements {n1[2]} | rows without CELEX: {left} | id {LAW['id']}: {tuple(law)}")
        return 0 if left == 0 and law[0] == LAW["celex"] else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
