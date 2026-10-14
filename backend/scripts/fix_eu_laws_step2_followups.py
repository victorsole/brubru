#!/usr/bin/env python3.12
"""Close the gaps the second audit found after repair_eu_laws_celex_vs_folder.py (14 Oct 2026, 20:38).

Measured 14 Oct 2026, each re-checked in the database before writing this:
  1. 33 rows hold EuroVoc as JSON null, not SQL NULL: the repair set a JSONB column to None through the ORM,
     which writes the JSON value null. Everywhere else eurovoc is an array or SQL NULL; a query that unnests
     eurovoc WHERE eurovoc IS NOT NULL now fails on them. -> SQL NULL.
  2. 22 of the 35 rows the first fix touched lost their document type (the re-parse gave none; the repair then
     normalised the empty value to "Other"). -> the type they had before the first fix ("Corrigendum to
     Commission Implementing Regulation" and the like), normalised by normalize_doc_types.py's rules.
  3. 32011L0093 is titled "Directive 2011/92/EU ...": the misprint in the original Official Journal text.
     The export table and Cellar say 2011/93/EU. -> the export table's title.
  4. The 7 rows re-created from Cellar were filed under corpus_version LEG_2026-10; every other cellar:// row
     carries the month it was loaded from Cellar. -> OJ_2026-10 (LEG_2026-10 counts its 28,497 rows again).
  5. 3 corrigenda carry eea_relevant next to an identical eea_relevance (the repair restored the older key).
     -> the duplicate key is dropped.
  6. Legislative Train carriage 7e6b5a77 (the directive on combating the sexual abuse of children) links to
     32011L0092, the environmental impact assessment directive, and repeats the misprint in its title.
     -> 32011L0093 and the corrected number. Its 108 daily snapshots are history and stay as recorded.

Dry run by default; --apply writes a JSON backup of every row it changes, does everything in one transaction
and asserts each count before committing.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.fix_eu_laws_step2_followups [--apply]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402
from backend.scripts.repair_eu_laws_celex_vs_folder import normalized  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "backend/data/leg_2026-10_table/leg_2026-10_table.csv"
FIX_BACKUP = ROOT / "backend/data/backups/celex_vs_folder_before_20261014_1729.json"
CARRIAGE = "7e6b5a77-bfd1-456c-9a1a-0d4d125368be"
EXPECTED = {"eurovoc": 33, "doc_type": 22, "title": 1, "corpus_version": 7, "eea_key": 3, "carriage": 1}


def plan(db):
    before = {r["uuid"]: r for r in json.loads(FIX_BACKUP.read_text())["rows_before"] if r["celex"]}
    now = db.execute(text("SELECT uuid::text, doc_type FROM eu_laws WHERE uuid::text = ANY(:u)"), {"u": list(before)}).fetchall()
    doc_types = {u: before[u]["doc_type"] for u, d in now if not (d or "").strip() and (before[u]["doc_type"] or "").strip()}
    title = next(r["Title of document"] for r in csv.DictReader(TABLE.open(encoding="utf-8-sig")) if r["CELEX"] == "32011L0093")
    assert "2011/93/EU" in title, title
    return doc_types, title


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        doc_types, title = plan(db)
        where = {
            "eurovoc": "jsonb_typeof(eurovoc) = 'null'",
            "corpus_version": "xml_path LIKE 'cellar://%' AND corpus_version = 'LEG_2026-10'",
            "eea_key": "extra_metadata ? 'eea_relevant' AND extra_metadata ? 'eea_relevance' "
                       "AND extra_metadata->'eea_relevant' = extra_metadata->'eea_relevance'",
            "title": "celex = '32011L0093' AND title LIKE '%2011/92/EU%'",
        }
        found = {k: db.execute(text(f"SELECT count(*) FROM eu_laws WHERE {w}")).scalar() for k, w in where.items()}
        found["doc_type"] = len(doc_types)
        found["carriage"] = db.execute(text("SELECT count(*) FROM legislative_carriages WHERE id = CAST(:i AS uuid) "
                                            "AND celex_numbers = ARRAY['32011L0092']::varchar[] AND title ILIKE '%sexual abuse%'"),
                                       {"i": CARRIAGE}).scalar()
        print(f"[INFO] rows to change: {found} | expected: {EXPECTED}")
        assert found == EXPECTED, "the database moved since the audit: stopped"
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
        backup = ROOT / f"backend/data/backups/eu_laws_step2_followups_before_{ts}.json"
        cond = " OR ".join(f"({w})" for w in where.values()) + " OR uuid::text = ANY(:u)"
        rows = db.execute(text(f"SELECT uuid::text, celex, doc_type, doc_type_normalized, title, corpus_version, eurovoc, extra_metadata "
                               f"FROM eu_laws WHERE {cond}"), {"u": list(doc_types)}).mappings().all()
        car = db.execute(text("SELECT id::text, title, celex_numbers FROM legislative_carriages WHERE id = CAST(:i AS uuid)"), {"i": CARRIAGE}).mappings().all()
        backup.write_text(json.dumps({"eu_laws": [dict(r) for r in rows], "legislative_carriages": [dict(r) for r in car]}, default=str, indent=1))
        print(f"[OK] backup of {len(rows)} rows + 1 carriage -> {backup.relative_to(ROOT)}")

        done = {
            "eurovoc": db.execute(text(f"UPDATE eu_laws SET eurovoc = NULL WHERE {where['eurovoc']}")).rowcount,
            "corpus_version": db.execute(text(f"UPDATE eu_laws SET corpus_version = 'OJ_2026-10' WHERE {where['corpus_version']}")).rowcount,
            "eea_key": db.execute(text(f"UPDATE eu_laws SET extra_metadata = extra_metadata - 'eea_relevant' WHERE {where['eea_key']}")).rowcount,
            "title": db.execute(text(f"UPDATE eu_laws SET title = :t WHERE {where['title']}"), {"t": title}).rowcount,
            "doc_type": sum(db.execute(text("UPDATE eu_laws SET doc_type = :d, doc_type_normalized = :n WHERE uuid::text = :u AND coalesce(trim(doc_type), '') = ''"),
                                       {"d": d, "n": normalized(d), "u": u}).rowcount for u, d in doc_types.items()),
            "carriage": db.execute(text("UPDATE legislative_carriages SET celex_numbers = ARRAY['32011L0093']::varchar[], "
                                        "title = replace(title, 'Directive 2011/92/EU', 'Directive 2011/93/EU') "
                                        "WHERE id = CAST(:i AS uuid) AND celex_numbers = ARRAY['32011L0092']::varchar[]"), {"i": CARRIAGE}).rowcount,
        }
        assert done == EXPECTED, f"changed {done}, expected {EXPECTED}: rolled back"
        db.commit()
        print(f"[OK] committed: {done}")
        left = {k: db.execute(text(f"SELECT count(*) FROM eu_laws WHERE {w}")).scalar() for k, w in where.items()}
        print(f"[VERIFY] left after: {left} | LEG_2026-10 rows: "
              f"{db.execute(text('SELECT count(*) FROM eu_laws WHERE corpus_version = :v'), {'v': 'LEG_2026-10'}).scalar()}")
        return 0 if not any(left.values()) else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
