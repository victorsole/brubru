#!/usr/bin/env python3.12
"""Repair what fix_eu_laws_celex_vs_folder.py (14 Oct 2026, 17:29) left wrong, found by the independent audit.

That fix gave 35 rows their own folder's CELEX M instead of the CELEX X they held, but it moved only the
identifier. Everything fetched BY CELEX X stayed on the old row: the act's text (body_*) and EuroVoc tags
(eurovoc*), so 33 corrigenda served the full text of the act they correct. And the 26 rows that received X
were junk rows of X's folder (an annex or an Official Journal wrapper, never re-read). Measured 14 Oct 2026:

  1. 26 acts (X has its own row): the act's row O is re-read from its folder's main file (the importer's own
     choice, parser and field mapping), and takes X's text, EuroVoc tags and Cellar-dated keys from the
     before-image of the old row R. If a job already fetched them for O, O keeps its own.
  2. 7 acts whose folder has no text in the export (metadata only, all in force): they had been served from
     row R before the fix (text from Cellar), and two Catalan translations point at them. Each gets its own
     row again, the way the daily sync writes a Cellar row: uuid = its folder, title and date from the export
     table, xml_path cellar://..., with X's text and EuroVoc tags from R's before-image.
  3. The 35 rows R: X's text and EuroVoc tags are cleared (the daily jobs refetch them for M); the keys the
     fix dropped that describe R's own file (page_first, page_last, eea_relevant) come back; 9 corrigenda of
     old acts that carry the corrected act's title take the export's title ("Corrigendum to ...").
  4. EU Law Comply links (cluster_laws, law_requirements) made to row R when it held X move to X's row.
  5. doc_type_normalized is recomputed on every touched row (normalize_doc_types.py rules).

Dry run by default; --apply writes a JSON backup of every touched row, does everything in one transaction,
asserts the counts and re-checks afterwards.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.repair_eu_laws_celex_vs_folder [--apply]
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
from backend.scripts.import_corpus_update import compute_file_hash, parsed_fields, rdf_in_force, stored_path  # noqa: E402
from backend.scripts.import_leg_archive import find_main_xml_files  # noqa: E402
from backend.scripts.normalize_doc_types import NORMALIZATION_RULES  # noqa: E402
from backend.scripts.sync_eu_laws_from_cellar import doc_type_from_title  # noqa: E402
from backend.services.parsers.formex_parser import FormexParser  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "docs/LEG_2026-10"
VERSION = "LEG_2026-10"
TABLE = ROOT / "backend/data/leg_2026-10_table/leg_2026-10_table.csv"
FOLDERS = ROOT / "backend/data/leg_2026-10_table/leg_2026-10_folders.csv"
FIX_BACKUP = ROOT / "backend/data/backups/celex_vs_folder_before_20261014_1729.json"
BODY = ("body_html", "body_txt", "body_chars", "body_fetched_at")
EUROVOC = ("eurovoc", "eurovoc_domain", "eurovoc_fetched_at")
FILE_KEYS = ("page_first", "page_last", "eea_relevant")  # parsed from R's own file: stay with R
CELLAR_KEYS = ("oj_publication_date", "oj_publication_date_source")  # fetched by CELEX X: go to X's row
OLD_TITLE_PREFIX = re.compile(r"^\d{4}/\d+/[A-Z]+\s*:\s*")  # "2004/412/EC:Commission Decision ..."


def normalized(doc_type: str) -> str:
    """normalize_doc_types.py's rules, first match wins ('%x%' contains, 'x%' starts with)."""
    d = (doc_type or "").lower()
    for category, patterns in NORMALIZATION_RULES:
        for p in patterns:
            core = p.strip("%")
            if (p.startswith("%") and core in d) or (not p.startswith("%") and d.startswith(core)):
                return category
    return "Other"


def plan(db):
    rows_before = json.loads(FIX_BACKUP.read_text())["rows_before"]
    before = {r["uuid"]: r for r in rows_before}
    table = {r["CELEX"]: r for r in csv.DictReader(TABLE.open(encoding="utf-8-sig"))}
    folder_of = {r["celex"]: r["folder"] for r in csv.DictReader(FOLDERS.open(encoding="utf-8-sig"))}
    now = {r[0]: r for r in db.execute(text("SELECT uuid::text, id, celex, title, body_fetched_at, eurovoc_fetched_at FROM eu_laws WHERE uuid::text = ANY(:u)"),
                                       {"u": list(before)}).fetchall()}
    held = {r[0]: r[1] for r in db.execute(text("SELECT celex, uuid::text FROM eu_laws WHERE celex IS NOT NULL AND celex <> ''")).fetchall()}
    moved, filled, missing = [], {}, []
    for u, b in before.items():
        if b["celex"]:
            moved.append(u)
        else:
            filled[now[u][2]] = u  # the act's own row, given X by the fix
    pairs = []
    for u in moved:
        x, m = before[u]["celex"], now[u][2]
        assert held.get(m) == u, f"{u} no longer holds {m}: stopped"
        if x in filled:
            pairs.append({"r": u, "x": x, "m": m, "own": filled[x], "kind": "fill"})
        elif x in table and table[x]["has_text"] == "no" and x not in held:
            assert table[x]["in_force"] == "true", f"{x} is not flagged in force"
            pairs.append({"r": u, "x": x, "m": m, "own": folder_of[x], "kind": "insert"})
        else:
            missing.append(x)  # the two bogus identifiers: no act, nothing to move
            assert not before[u]["body_fetched_at"] and not before[u]["eurovoc_fetched_at"], f"{x} carried text: decide by hand"
    return before, table, now, pairs, missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        before, table, now, pairs, missing = plan(db)
        fills = [p for p in pairs if p["kind"] == "fill"]
        inserts = [p for p in pairs if p["kind"] == "insert"]
        retitle = [p for p in pairs if table.get(p["m"], {}).get("Title of document", "").startswith("Corrigendum")
                   and not (now[p["r"]][3] or "").startswith("Corrigendum")]
        links = db.execute(text("SELECT 'cluster_laws', law_id, count(*) FROM cluster_laws WHERE law_id = ANY(:i) GROUP BY law_id "
                                "UNION ALL SELECT 'law_requirements', law_id, count(*) FROM law_requirements WHERE law_id = ANY(:i) GROUP BY law_id"),
                           {"i": [now[p["r"]][1] for p in pairs]}).fetchall()
        print(f"[INFO] acts re-read from their main file and given their text back: {len(fills)}")
        print(f"[INFO] metadata-only acts given their own row again: {[p['x'] for p in inserts]}")
        print(f"[INFO] identifiers that named no act (nothing to move): {missing}")
        print(f"[INFO] corrigenda to retitle from the export table: {[p['m'] for p in retitle]}")
        print(f"[INFO] EU Law Comply links to move to the act's own row: {links}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        cols = [c.name for c in EULaw.__table__.columns if c.name != "search_vector"]
        touched = [p["r"] for p in pairs] + [p["own"] for p in fills]
        snap = [dict(zip(cols, r)) for r in db.execute(text(f"SELECT {', '.join(cols)} FROM eu_laws WHERE uuid::text = ANY(:u)"), {"u": touched}).fetchall()]
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
        backup = ROOT / f"backend/data/backups/celex_vs_folder_repair_before_{ts}.json"
        backup.write_text(json.dumps({"rows_before": snap, "inserted_uuids": [p["own"] for p in inserts], "links": [list(r) for r in links]}, default=str, indent=1))
        print(f"[OK] backup of {len(snap)} rows -> {backup.relative_to(ROOT)}")

        parser, mains = FormexParser(), dict(find_main_xml_files(CORPUS))
        kept_own = []
        for p in pairs:
            b = before[p["r"]]
            if p["kind"] == "fill":  # 1. the act's own row: re-read, then X's text and tags
                law = db.query(EULaw).filter(EULaw.uuid == p["own"]).one()
                path = mains[p["own"]]
                parsed = parser.parse_file(path)
                assert parsed.title and not parsed.title.lower().startswith(("annex", "official journal")), f"{p['x']}: {parsed.title!r}"
                for k, v in parsed_fields(parsed, stored_path(path), compute_file_hash(path), VERSION).items():
                    setattr(law, k, v)
                law.corpus_status = "repealed" if rdf_in_force(CORPUS, p["own"]) is False else "active"
                law.extra_metadata = {**law.extra_metadata, **{k: b["extra_metadata"][k] for k in CELLAR_KEYS if k in (b["extra_metadata"] or {})}}
            else:  # 2. metadata-only act: a Cellar row, as the daily sync writes one
                t = table[p["x"]]
                title = OLD_TITLE_PREFIX.sub("", t["Title of document"]).strip()
                law = EULaw(uuid=p["own"], celex=p["x"], title=title, doc_type=doc_type_from_title(title, p["x"][5]),
                            date=dt.date.fromisoformat(t["date_document"]), policy_area=b["policy_area"],
                            xml_path=f"cellar://publications.europa.eu/resource/celex/{p['x']}", is_primary_legislation=True,
                            corpus_version=VERSION, corpus_status="active",
                            extra_metadata={"eli": t["eli"] or None, "in_force": True, "text_in_export": False,
                                            "ingested_by": "repair_eu_laws_celex_vs_folder"})
                db.add(law)
            for group, stamp in ((BODY, "body_fetched_at"), (EUROVOC, "eurovoc_fetched_at")):
                if getattr(law, stamp) is None:
                    for k in group:
                        setattr(law, k, b[k])
                else:
                    kept_own.append((p["x"], stamp))  # a job already fetched it for the act itself
            law.doc_type_normalized = normalized(law.doc_type)

            r = db.query(EULaw).filter(EULaw.uuid == p["r"]).one()  # 3. the row that held X
            for k in BODY + EUROVOC:
                setattr(r, k, None)
            r.extra_metadata = {**(r.extra_metadata or {}), **{k: b["extra_metadata"][k] for k in FILE_KEYS if k in (b["extra_metadata"] or {})}}
            if p in retitle:
                r.title = table[p["m"]]["Title of document"]
                r.doc_type = doc_type_from_title(r.title, p["m"][5])
            r.doc_type_normalized = normalized(r.doc_type)
        db.flush()

        for p in pairs:  # 4. links made to R when it held X
            own_id = db.execute(text("SELECT id FROM eu_laws WHERE uuid::text = :u"), {"u": p["own"]}).scalar()
            for t in ("cluster_laws", "law_requirements"):
                db.execute(text(f"UPDATE {t} SET law_id = :o WHERE law_id = :r"), {"o": own_id, "r": now[p["r"]][1]})
        for u in [u for u in before if before[u]["celex"] and u not in {p["r"] for p in pairs}]:
            r = db.query(EULaw).filter(EULaw.uuid == u).one()
            r.doc_type_normalized = normalized(r.doc_type)
        db.flush()

        dup = db.execute(text("SELECT count(*) FROM (SELECT celex FROM eu_laws WHERE celex IS NOT NULL AND celex <> '' GROUP BY celex HAVING count(*) > 1) d")).scalar()
        assert dup == 0, f"{dup} duplicate CELEX: rolled back"
        left = db.execute(text("SELECT count(*) FROM cluster_laws WHERE law_id = ANY(:i)"), {"i": [now[p["r"]][1] for p in pairs]}).scalar() \
            + db.execute(text("SELECT count(*) FROM law_requirements WHERE law_id = ANY(:i)"), {"i": [now[p["r"]][1] for p in pairs]}).scalar()
        assert left == 0, f"{left} links still on the old rows: rolled back"
        db.commit()
        print(f"[OK] committed: {len(fills)} acts re-read, {len(inserts)} rows re-created, {len(pairs)} old rows cleared, "
              f"{len(retitle)} retitled, {sum(r[2] for r in links)} links moved | kept the act's own fresh text/tags: {kept_own}")

        bad = db.execute(text("""SELECT celex, title FROM eu_laws WHERE celex = ANY(:c)
                                  AND (title ~* '^(annex|official journal)' OR body_fetched_at IS NULL OR eurovoc_fetched_at IS NULL)"""),
                         {"c": [p["x"] for p in pairs]}).fetchall()
        stale = db.execute(text("SELECT count(*) FROM eu_laws WHERE uuid::text = ANY(:u) AND (body_fetched_at IS NOT NULL OR eurovoc_fetched_at IS NOT NULL)"),
                           {"u": [p["r"] for p in pairs]}).scalar()
        print(f"[VERIFY] acts still junk or without text/tags: {bad} | old rows still holding the act's text or tags: {stale}")
        return 0 if not bad and not stale else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
