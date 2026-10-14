#!/usr/bin/env python3.12
"""Step 3 of the 14 Oct 2026 eu_laws clean-up: remove empty duplicates and dead fragment rows, re-point dead text paths.

Measured 14 Oct 2026 (after steps 1 and 2):
  A. 224 LEG_2026-10 rows have no CELEX because another row already holds it (209 rows from the September Cellar
     backfill, 7 EU Canon rows, 3 rows of the deleted 2025 copy, 5 later daily-sync rows). The holders carry every
     reference (EU Law Comply: 14 cluster links, 209 requirements); the empty rows carry none. So the holder stays
     and the empty duplicate goes: nothing cascades.
  B. But the empty row is the only link to the act's text file in the export: 214 holders point at Cellar only
     (cellar://) and 3 at a file of the deleted 2025 copy. Before the empty row goes, those 217 holders take the
     act's main file in docs/LEG_2026-10 (the importer's own main-file choice, hash and structure counts; 17 empty
     rows point at an annex or wrapper, so the path is re-resolved, never copied) and corpus_version LEG_2026-10.
     They keep their id, uuid, CELEX, title, text, EuroVoc tags and links. The 7 EU Canon holders keep their canon
     path (the canon register reads it). Victor's choice, 14 Oct 2026: merge, then delete.
  C. 232 LEG_2025-11 rows have no CELEX, no text on disk and are absent from the 2026 export: 152 annex or appendix
     fragments and 51 Official Journal wrappers imported as if they were acts (deleted here), plus 15 corrigenda and
     14 real documents such as Council appointment decisions (listed, left for a person; one is linked in EU Law Comply).

Deleting is for a person to run: the automatic safeguard blocks bulk deletes in production. Dry run by default.
--apply writes a JSON backup of every row it deletes or changes, checks again that no table points at a row
before deleting it, does everything in one transaction and re-measures afterwards.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.merge_eu_laws_duplicates [--apply]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402
from backend.models.eu_law import EULaw  # noqa: E402
from backend.scripts.import_corpus_update import compute_file_hash, parsed_fields, stored_path  # noqa: E402
from backend.scripts.import_leg_archive import find_main_xml_files  # noqa: E402
from backend.services.parsers.formex_parser import FormexParser  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "docs/LEG_2026-10"
FOLDERS = ROOT / "backend/data/leg_2026-10_table/leg_2026-10_folders.csv"
# an annex, appendix or Official Journal wrapper imported as if it were an act (2025 copy)
FRAGMENT = re.compile(r"^\s*(ANNEX|APPENDIX|PART|TABLE|SCHEDULE)\b|^Official Journal", re.I)
REF_SQL = {"cluster_laws": "SELECT law_id FROM cluster_laws WHERE law_id = ANY(:i)",
           "law_requirements": "SELECT law_id FROM law_requirements WHERE law_id = ANY(:i)",
           "eu_laws.parent_law_uuid": "SELECT e.id FROM eu_laws p JOIN eu_laws e ON e.parent_law_uuid = p.uuid WHERE p.id = ANY(:i)"}


def referenced(db, ids):
    out = set()
    for q in REF_SQL.values():
        out |= {r[0] for r in db.execute(text(q), {"i": list(ids)}).fetchall()}
    return out


def plan(db):
    fol = {r["folder"]: r["celex"] for r in csv.DictReader(FOLDERS.open(encoding="utf-8-sig"))}
    folder_of = {c: f for f, c in fol.items()}
    held = {r[0]: r for r in db.execute(text("SELECT celex, id, corpus_version, xml_path FROM eu_laws WHERE celex IS NOT NULL AND celex <> ''")).fetchall()}
    empty = db.execute(text("SELECT id, xml_path FROM eu_laws WHERE (celex IS NULL OR celex = '') AND corpus_version = 'LEG_2026-10'")).fetchall()
    dup_ids, repoint = [], []
    for i, xp in empty:
        cx = fol.get(xp.split("/")[2]) if xp else None
        if cx in held:
            dup_ids.append(i)
            h = held[cx]
            xp_h = h[3] or ""
            if xp_h.startswith("cellar://") or (xp_h.startswith("docs/LEG_2025-11/") and not (ROOT / xp_h).exists()):
                repoint.append({"id": h[1], "celex": cx, "folder": folder_of[cx]})
    old = db.execute(text("SELECT id, coalesce(title, '') FROM eu_laws WHERE (celex IS NULL OR celex = '') AND corpus_version = 'LEG_2025-11'")).fetchall()
    frag = [i for i, t in old if FRAGMENT.match(t)]
    documents = sorted(i for i, t in old if not FRAGMENT.match(t))  # corrigenda and real documents: a person decides
    frag_ref = referenced(db, frag)
    return dup_ids, repoint, [i for i in frag if i not in frag_ref], sorted(frag_ref) + documents, len(empty)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        dup_ids, repoint, frag_del, frag_kept, n_empty = plan(db)
        dup_ref = referenced(db, dup_ids)
        print(f"[INFO] A. empty LEG_2026-10 duplicates: {len(dup_ids)} of {n_empty} rows without CELEX | referenced by anything: {len(dup_ref)}")
        print(f"[INFO] B. holders that take the act's export file before the duplicate goes: {len(repoint)} "
              f"(left on their canon path: {len(dup_ids) - len(repoint)})")
        print(f"[INFO] C. 2025 fragment rows (annex, appendix, OJ wrapper) to delete: {len(frag_del)} | left for a person (corrigenda, real documents, anything referenced): {len(frag_kept)} {frag_kept}")
        assert not dup_ref, f"an empty duplicate is referenced: {sorted(dup_ref)}"
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        cols = [c.name for c in EULaw.__table__.columns]
        ids = dup_ids + frag_del + [r["id"] for r in repoint]
        before = [dict(zip(cols, r)) for r in db.execute(text(f"SELECT {', '.join(cols)} FROM eu_laws WHERE id = ANY(:i)"), {"i": ids}).fetchall()]
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
        backup = ROOT / f"backend/data/backups/eu_laws_step3_before_{ts}.json"
        backup.write_text(json.dumps({"deleted_duplicates": dup_ids, "deleted_fragments": frag_del, "repointed": repoint, "rows_before": before}, default=str, indent=1))
        print(f"[OK] backup of {len(before)} rows -> {backup.relative_to(ROOT)}")

        assert not referenced(db, dup_ids + frag_del), "a row to delete became referenced: stopped"
        n = db.execute(text("DELETE FROM eu_laws WHERE id = ANY(:i)"), {"i": dup_ids + frag_del}).rowcount
        mains, parser = dict(find_main_xml_files(CORPUS)), FormexParser()
        for r in repoint:  # the holder takes the act's export file; identity, text, tags and links stay
            law = db.query(EULaw).filter(EULaw.id == r["id"]).one()
            path = mains[r["folder"]]
            parsed = parser.parse_file(path)
            assert parsed.title and not parsed.title.lower().startswith(("annex", "official journal")), f"{r['celex']}: {parsed.title!r}"
            assert not getattr(parsed, "celex", None) or parsed.celex == r["celex"], f"{r['celex']}: file says {parsed.celex}"
            counts = parsed_fields(parsed, stored_path(path), compute_file_hash(path), "LEG_2026-10")["extra_metadata"]
            law.xml_path, law.content_hash, law.corpus_version = stored_path(path), compute_file_hash(path), "LEG_2026-10"
            law.extra_metadata = {**counts, **(law.extra_metadata or {})}  # the holder's own keys win
        assert n == len(dup_ids) + len(frag_del), f"deleted {n}, expected {len(dup_ids) + len(frag_del)}: rolled back"
        db.commit()
        print(f"[OK] committed: {len(dup_ids)} duplicates and {len(frag_del)} fragments deleted, {len(repoint)} holders took their export file")
        after = plan(db)
        held = db.execute(text("SELECT xml_path FROM eu_laws WHERE id = ANY(:i)"), {"i": [r["id"] for r in repoint]}).fetchall()
        no_file = [x for (x,) in held if not (x or "").startswith("docs/LEG_2026-10/") or not (ROOT / x).exists()]
        print(f"[VERIFY] after: duplicates {len(after[0])}, fragments without reference {len(after[2])}, referenced fragments kept {after[3]} "
              f"| holders without their export file: {len(no_file)} of {len(held)}")
        return 0 if not after[0] and not after[2] and not no_file else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
