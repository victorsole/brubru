#!/usr/bin/env python3.12
"""Give every LEG_2026-10 row the CELEX of its own folder, and give each freed CELEX back to its act's own row.

Found 14 Oct 2026: 35 rows hold a CELEX that their folder's metadata does not state. 30 are correction notices
(corrigenda) whose row carries the main act's CELEX; 5 are other mix-ups (a wrongly parsed number, a consolidated
notice filed under the act it consolidates). Because CELEX is unique in eu_laws, each wrong row also BLOCKED the
real act: the act's own row was imported without a CELEX (it is among the "250 held elsewhere"), or not imported.

What this does, in one transaction, reusing the importer's own parser and field mapping (import_corpus_update.py):
  1. each wrong row R takes its folder's CELEX M, and its fields are re-read from its folder (title, type, dates);
  2. each freed CELEX X goes to the row of X's own folder: filled in when that row exists without a CELEX,
     inserted (importer path) when the folder has no row;
  3. a freed CELEX with no folder in the export is reported (it was a parsing error, not an act we hold).
Year, type and number are set from the CELEX (fix_eu_laws_celex_parts.celex_parts).
Dry run by default; --apply writes a backup of every touched row first and re-checks afterwards.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.fix_eu_laws_celex_vs_folder [--apply]
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
from backend.models.eu_law import EULaw  # noqa: E402
from backend.scripts.fix_eu_laws_celex_parts import celex_parts  # noqa: E402
from backend.scripts.import_corpus_update import (compute_file_hash, parsed_fields, rdf_in_force,  # noqa: E402
                                                  stored_path)
from backend.scripts.import_leg_archive import find_main_xml_files  # noqa: E402
from backend.services.parsers.formex_parser import FormexParser  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "docs/LEG_2026-10"
VERSION = "LEG_2026-10"
FOLDERS = ROOT / "backend/data/leg_2026-10_table/leg_2026-10_folders.csv"


def plan(db):
    meta = {r["folder"]: r for r in csv.DictReader(FOLDERS.open(encoding="utf-8-sig"))}
    fol = {f: r["celex"] for f, r in meta.items()}
    folder_of = {}
    for f, c in fol.items():
        folder_of.setdefault(c, []).append(f)
    rows = db.execute(text("SELECT uuid::text, celex, xml_path FROM eu_laws WHERE corpus_version = :v AND xml_path LIKE 'docs/LEG_2026-10/%'"),
                      {"v": VERSION}).fetchall()
    by_uuid = {r[0]: r for r in db.execute(text("SELECT uuid::text, celex FROM eu_laws")).fetchall()}
    held = {r[1]: r[0] for r in by_uuid.values() if r[1]}
    wrong = []
    for u, cx, xp in rows:
        f = xp.split("/")[2]
        m = fol.get(f)
        if cx and m and cx != m:
            wrong.append({"uuid": u, "folder": f, "x": cx, "m": m, "xml_path": xp})
    fills, inserts, dropped, no_text = [], [], [], []
    for w in wrong:
        assert held.get(w["m"]) in (None, w["uuid"]), f"{w['m']} is already held by {held[w['m']]}"
        own = folder_of.get(w["x"], [])
        if not own:
            dropped.append(w["x"])
            continue
        assert len(own) == 1, f"{w['x']} has {len(own)} folders"
        r2 = by_uuid.get(own[0])
        if r2 is None and meta[own[0]]["has_text"] != "yes":
            no_text.append(w["x"])  # metadata only in the export: like the other 28,764, not loaded into eu_laws
        elif r2 is None:
            inserts.append({"uuid": own[0], "celex": w["x"]})
        else:
            assert not r2[1], f"the own row of {w['x']} already has CELEX {r2[1]}"
            fills.append({"uuid": own[0], "celex": w["x"]})
    return wrong, fills, inserts, dropped, no_text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        wrong, fills, inserts, dropped, no_text = plan(db)
        print(f"[INFO] rows with a CELEX their folder does not state: {len(wrong)}")
        print(f"[INFO] freed CELEX -> own row filled: {len(fills)} | own row inserted: {len(inserts)} | no folder in the export (parsing error): {dropped}")
        print(f"[INFO] freed CELEX whose own folder has no text (not loaded, like every metadata-only publication): {no_text}")
        for w in wrong[:8]:
            print(f"  {w['uuid'][:8]}  {w['x']:16s} -> {w['m']}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        touched = [w["uuid"] for w in wrong] + [f["uuid"] for f in fills]
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
        backup = ROOT / f"backend/data/backups/celex_vs_folder_before_{ts}.json"
        cols = [c.name for c in EULaw.__table__.columns]
        before = [dict(zip(cols, r)) for r in db.execute(text(f"SELECT {', '.join(cols)} FROM eu_laws WHERE uuid::text = ANY(:u)"), {"u": touched}).fetchall()]
        backup.write_text(json.dumps({"rows_before": before, "inserted_uuids": [i["uuid"] for i in inserts]}, default=str, indent=1))
        print(f"[OK] backup of {len(before)} rows (+{len(inserts)} to insert) -> {backup.relative_to(ROOT)}")

        parser = FormexParser()
        mains = dict(find_main_xml_files(CORPUS)) if inserts else {}  # (folder uuid, main xml path)
        for w in wrong:  # 1. the wrong rows take their own folder's CELEX and fields
            law = db.query(EULaw).filter(EULaw.uuid == w["uuid"]).one()
            path = ROOT / w["xml_path"]
            parsed = parser.parse_file(path)
            assert parsed.title, f"no title parsed for {w['uuid']}"
            for k, v in parsed_fields(parsed, stored_path(path), compute_file_hash(path), VERSION).items():
                setattr(law, k, v)
            law.celex = w["m"]
            law.celex_year, law.celex_type, law.celex_number = celex_parts(w["m"]) or (None, None, None)
        db.flush()
        for f in fills:  # 2a. freed CELEX back to the act's own row
            law = db.query(EULaw).filter(EULaw.uuid == f["uuid"]).one()
            law.celex = f["celex"]
            law.celex_year, law.celex_type, law.celex_number = celex_parts(f["celex"]) or (None, None, None)
        for i in inserts:  # 2b. the act's own row did not exist: import it the importer's way
            path = mains[i["uuid"]]
            parsed = parser.parse_file(path)
            assert parsed.title, f"no title parsed for {i['uuid']}"
            status = "repealed" if rdf_in_force(CORPUS, i["uuid"]) is False else "active"
            y, t, n = celex_parts(i["celex"]) or (None, None, None)
            db.add(EULaw(uuid=i["uuid"], celex=i["celex"], corpus_status=status, celex_year=y, celex_type=t, celex_number=n,
                         **parsed_fields(parsed, stored_path(path), compute_file_hash(path), VERSION)))
        db.flush()
        dup = db.execute(text("SELECT count(*) FROM (SELECT celex FROM eu_laws WHERE celex IS NOT NULL AND celex <> '' GROUP BY celex HAVING count(*) > 1) d")).scalar()
        assert dup == 0, f"{dup} duplicate CELEX after the change: rolled back"
        db.commit()
        print(f"[OK] committed: {len(wrong)} rows corrected, {len(fills)} filled, {len(inserts)} inserted")

        wrong2 = plan(db)[0]
        assert not wrong2, f"{len(wrong2)} rows still disagree"
        print("[VERIFY] every LEG_2026-10 row now carries its own folder's CELEX; no duplicate CELEX")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
