#!/usr/bin/env python3.12
"""Re-read every LEG_2026-10 row that was filled from the wrong file of its folder (item 3, 15 Oct 2026).

Measured 15 Oct 2026 (root element of every file in the export): of 28,497 rows, 7,352 point at an ANNEX page
(7,298 titled "ANNEX..."), 2,849 point at the act's file but were filled from the cover page (hash of the .doc or
.toc file; 1,611 titled "Official Journal of the European Union"), 1 points at the cover page itself, and some
folders hold several act files where the row took the wrong one (a joint statement, an attached agreement). The
laws API serves eu_laws.title, filters on doc_type_normalized and searches title + celex + doc_type, so 8,746 laws
were typed Annex or Table of Contents. Cause: an earlier import picked an annex page as the main file and every
later import kept a row's file. The importer now picks by content (import_corpus_update.main_file); this script
applies the same choice to the rows already wrong.

For each row whose current file is not main_file's choice (the act: root ACT, CORR, GENERAL or AGR; a corrigendum
takes the republished act when its folder holds one, Victor 14 and 15 Oct 2026; with several, the best title match,
the current file on a tie), or whose hash is not its file's:
  - xml_path and content_hash: the act's file;
  - title and date: the export table (the Publications Office's metadata, leg_2026-10_table.csv), the title without
    EUR-Lex's number prefix (Victor, 15 Oct 2026), whitespace normalised;
  - written only when the act file is in English and is that act (its title matches the metadata, or carries the
    act's number); else listed for a person;
  - doc_type_normalized from the CELEX letter (type_label), doc_type the file's own heading; legal basis,
    citations, primary flag, OJ reference, policy area (the importer's own guess; no other job writes it) and
    structure counts from the act's file (parsed_fields); subject words and page numbers by the older parser that
    built the other rows;
  - extra_metadata: the keys the old file put there and the caches computed from it (defined terms, recital map)
    go, merged in the UPDATE itself; other writers' keys stay;
  - kept: CELEX, uuid, text (body_*), EuroVoc tags, links.
Rows already on their act's file but typed with no type or a wrong-file type get their type from the CELEX letter.

Dry run by default: prints the plan and writes wrong_file_review[_dry_run]_<ts>.csv (every multi-file pick and every
row left for a person). --apply writes a JSON backup of the columns it changes, updates in one transaction (one
statement per 500 rows), checks the ids and re-measures; exits 1 if any row is still on the wrong file.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.repair_eu_laws_wrong_file [--apply]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402
from backend.scripts.fix_eu_laws_2025_leftovers import check  # noqa: E402
from backend.scripts.import_corpus_update import (DERIVED_FROM_FILE, FILE_KEYS, MAIN_ROOTS, MATCH_MIN,  # noqa: E402
                                                  WRONG_FILE_TYPES, act_confirmed, act_date, number_in_title,
                                                  corrigendum_corrections,
                                                  compute_file_hash, file_root, main_file,
                                                  parsed_fields, stored_path, title_match, usable_title,
                                                  type_label)
from backend.services.law_database.xml_parser import FormexXMLParser  # noqa: E402
from backend.services.parsers.formex_parser import FormexParser  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "docs/LEG_2026-10"
TABLE = ROOT / "backend/data/leg_2026-10_table/leg_2026-10_table.csv"
VERSION = "LEG_2026-10"
# oj_reference is not written: since 17 Oct 2026 fill_eu_laws_oj_reference.py writes the citation from Cellar
WRITES = ("xml_path", "content_hash", "title", "doc_type", "doc_type_normalized", "date",
          "citations", "is_primary_legislation", "policy_area", "subject_matter", "extra_metadata")


def plan(db, parser):
    table = {r["CELEX"]: (usable_title(r["Title of document"]), r["date_document"])
             for r in csv.DictReader(TABLE.open(encoding="utf-8-sig"))}
    rows = db.execute(text("SELECT id, uuid, celex, xml_path, content_hash, doc_type_normalized, title FROM eu_laws "
                           "WHERE corpus_version = :v AND xml_path LIKE 'docs/LEG_2026-10/%'"), {"v": VERSION}).fetchall()
    fix, retype, review, why = [], [], [], collections.Counter()
    for i, uuid, celex, xp, h, dn, stored_title in rows:
        t_title, t_date = table.get(celex, ("", ""))
        cur = ROOT / xp
        picked, multi_score = main_file(CORPUS, uuid, celex, lambda: t_title, parser, current=cur)
        if picked is None:
            why["no act file in the folder (item 4)"] += 1
            review.append((i, celex, cur.name, "", "", "no act file"))
            continue
        reasons = [k for k, bad in (("annex or cover page", file_root(cur) not in MAIN_ROOTS),
                                    ("another act file", picked != cur),
                                    ("filled from another file", compute_file_hash(cur) != h)) if bad]
        if not reasons:
            label = type_label(celex, dn)
            if (dn is None or dn in WRONG_FILE_TYPES) and label != dn:
                retype.append({"id": i, "doc_type_normalized": label})
            if t_title and title_match(stored_title, t_title) < MATCH_MIN and not number_in_title(celex, stored_title):
                review.append((i, celex, cur.name, "", f"{title_match(stored_title, t_title):.2f}",
                               "right file; stored title differs from the metadata: not touched"))
            continue
        p = parser.parse_file(picked)
        score = title_match(p.title, t_title)
        why_not = act_confirmed(celex, p, t_title) or (None if t_title else "no metadata title")
        if multi_score is not None:
            review.append((i, celex, cur.name, picked.name, f"{score:.2f}", "picked among several act files"))
        if why_not:
            why["not English, or not the act by title or number: left for a person"] += 1
            review.append((i, celex, cur.name, picked.name, f"{score:.2f}", "not written: " + why_not))
            continue
        why[" + ".join(reasons)] += 1
        fix.append({"id": i, "celex": celex, "path": picked, "parsed": p, "title": t_title,
                    "date": t_date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t_date or "") else None,
                    "dn": dn})
    corr = corrigendum_corrections(db, [f["celex"] for f in fix], CORPUS)  # a corrigendum may correct the title's date
    for f in fix:
        f["corrections"] = corr.get(f["celex"], [])
    return fix, retype, review, why, len(rows)


def new_values(f, xp_parser) -> tuple:
    """The values the UPDATE writes for one row: act file + metadata; extra_metadata holds only the new file's keys."""
    p = f["parsed"]
    fields = parsed_fields(p, stored_path(f["path"]), compute_file_hash(f["path"]), VERSION)
    root = ET.parse(f["path"]).getroot()
    old_extra = xp_parser._extract_extra_metadata(root)  # the older parser built the other rows' page keys
    extra = dict(fields["extra_metadata"])
    extra.update({k: old_extra[k] for k in ("page_first", "page_last", "page_count") if k in old_extra})
    v = {"id": f["id"], "xml_path": fields["xml_path"], "content_hash": fields["content_hash"], "title": f["title"],
         "doc_type": p.doc_type or type_label(f["celex"], f["dn"]),
         "doc_type_normalized": type_label(f["celex"], f["dn"]),
         "date": act_date(f["celex"], f["title"], f["date"] or (p.date.isoformat() if p.date else None),
                          f.get("corrections", ())),
         "citations": fields["citations"],
         "is_primary_legislation": fields["is_primary_legislation"], "policy_area": fields["policy_area"],
         "subject_matter": xp_parser._extract_subject_matter(root) or None,
         "extra_metadata": json.dumps(extra, default=str)}
    return tuple(v[c] for c in ("id",) + WRITES)


DROP = "ARRAY[" + ", ".join(f"'{k}'" for k in FILE_KEYS + DERIVED_FROM_FILE) + "]::text[]"
# one statement per 500 rows (psycopg2 execute_values); extra_metadata merged at write time so no other writer's
# key is lost
UPDATE = ("UPDATE eu_laws e SET xml_path = v.xml_path, content_hash = v.content_hash, title = v.title, "
          "doc_type = v.doc_type, doc_type_normalized = v.doc_type_normalized, date = v.date, "
          "citations = v.citations, "
          "is_primary_legislation = v.is_primary_legislation, policy_area = v.policy_area, subject_matter = v.subject_matter, "
          f"extra_metadata = (coalesce(e.extra_metadata, '{{}}'::jsonb) - {DROP}) || v.extra_metadata "
          f"FROM (VALUES %s) AS v (id, {', '.join(WRITES)}) WHERE e.id = v.id AND e.corpus_version = 'LEG_2026-10' "
          "RETURNING e.id")
TEMPLATE = "(%s, %s, %s, %s, %s, %s, %s::date, %s::text[], %s::boolean, %s, %s::text[], %s::jsonb)"  # legal_basis: fill_eu_laws_legal_basis.py
RETYPE = ("UPDATE eu_laws e SET doc_type_normalized = v.t FROM (VALUES %s) AS v (id, t) "
          "WHERE e.id = v.id AND e.corpus_version = 'LEG_2026-10' RETURNING e.id")
MEASURE = ("SELECT count(*) FILTER (WHERE doc_type_normalized IN ('Annex', 'Table of Contents')), "
           "count(*) FILTER (WHERE upper(ltrim(title)) LIKE 'ANNEX%' OR upper(ltrim(title)) LIKE 'APPENDIX%'), "
           "count(*) FILTER (WHERE upper(ltrim(title)) LIKE 'OFFICIAL JOURNAL%'), count(*) FILTER (WHERE doc_type_normalized IS NULL) "
           "FROM eu_laws WHERE corpus_version = 'LEG_2026-10'")


def measure(db) -> str:
    a, b, c, d = db.execute(text(MEASURE)).one()
    return f"typed Annex or Table of Contents {a}, titled ANNEX/APPENDIX {b}, titled Official Journal {c}, no type {d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db, parser, xp_parser = SessionLocal(), FormexParser(), FormexXMLParser()
    try:
        before = measure(db)
        fix, retype, review, why, n = plan(db, parser)
        held = [r for r in review if r[5].startswith(("not written", "no act file"))]
        print(f"[INFO] {n} rows read | to re-read from the act's file: {len(fix)} | type from the CELEX only: {len(retype)} "
              f"| left for a person: {len(held)}")
        for k, v in why.most_common():
            print(f"[INFO]   {v:6d}  {k}")
        print(f"[INFO] now: {before}")
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
        rev = ROOT / f"backend/data/backups/wrong_file_review{'' if a.apply else '_dry_run'}_{ts}.csv"
        with rev.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "celex", "current_file", "picked_file", "title_match", "note"])
            w.writerows(review)
        print(f"[INFO] review list ({len(review)} rows, {len(held)} left for a person) -> {rev.relative_to(ROOT)}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        ids = [f["id"] for f in fix] + [r["id"] for r in retype]
        cols = ("id", "uuid", "celex") + WRITES
        rows = [dict(r) for r in db.execute(text(f"SELECT {', '.join(cols)} FROM eu_laws WHERE id = ANY(:i)"), {"i": ids}).mappings()]
        backup = ROOT / f"backend/data/backups/eu_laws_wrong_file_before_{ts}.json"
        backup.write_text(json.dumps({"columns": cols, "rows_before": rows}, default=str))
        print(f"[OK] backup of {len(rows)} rows ({len(cols)} columns) -> {backup.relative_to(ROOT)}")
        params = [new_values(f, xp_parser) for f in fix]
        cur = db.connection().connection.cursor()  # the session's own transaction
        done = execute_values(cur, UPDATE, params, template=TEMPLATE, page_size=500, fetch=True)
        check(sorted(r[0] for r in done) == sorted(f["id"] for f in fix), f"re-read {len(done)}, expected {len(fix)}: rolled back")
        typed = execute_values(cur, RETYPE, [(r["id"], r["doc_type_normalized"]) for r in retype], page_size=500, fetch=True) if retype else []
        check(len(typed) == len(retype), f"retyped {len(typed)}, expected {len(retype)}: rolled back")
        db.commit()
        print(f"[OK] committed: {len(done)} rows re-read from the act's file, {len(typed)} typed from the CELEX")
        left_fix, left_retype, left_review = plan(db, parser)[:3]
        left_held = [r for r in left_review if r[5].startswith(("not written", "no act file"))]
        print(f"[VERIFY] {before} -> {measure(db)} | still on the wrong file: {len(left_fix)}, type still to set: "
              f"{len(left_retype)}, left for a person (listed): {len(left_held)}")
        return 0 if not left_fix and not left_retype else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
