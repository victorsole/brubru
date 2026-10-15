#!/usr/bin/env python3.12
"""Re-read every LEG_2026-10 row that was filled from the wrong file of its folder (item 3, 15 Oct 2026).

Measured 15 Oct 2026 (root element of every file in the export): of 28,497 rows, 7,352 point at an ANNEX page
(7,298 titled "ANNEX..."), 2,849 point at the act's file but were filled from the cover page (hash of the .doc or
.toc file; 1,611 titled "Official Journal of the European Union"), 1 points at the cover page itself, and some
folders hold several act files where the row took the wrong one (a joint statement, a declaration). The laws API
serves eu_laws.title, filters on doc_type_normalized and searches title + celex + doc_type, so these laws were
shown, typed and searched wrongly. Cause: an earlier import picked an annex page as the main file and every later
import kept a row's file. The importer now picks by content (import_corpus_update.main_file).

For each row whose current file is not the act's own file (main_file: root ACT, CORR, GENERAL or AGR; a
corrigendum's CORR; with several, the best title match), or whose hash is not its file's:
  - xml_path and content_hash: the act's file;
  - title and date: the export table (the Publications Office's metadata, leg_2026-10_table.csv: title and
    date_document), whitespace normalised; the act file's own title must match it (title_match >= 0.4), else
    the row is listed, not written;
  - doc_type_normalized from the CELEX letter (type_label), doc_type the file's own heading;
  - legal basis, citations, primary flag, OJ reference and structure counts from the act's file (the importer's
    parsed_fields); subject words and page numbers by the older parser that built the other rows;
  - kept: CELEX, uuid, text (body_*), EuroVoc tags, policy_area once the EuroVoc job set it, other writers'
    extra_metadata keys, links. Not touched: the 9 corrigenda Victor kept on the republished act (14 Oct) and
    32015D1735 (no act file: two TIFF scans, item 4).
Victor's choice, 15 Oct 2026: full fix.

Dry run by default: prints the plan and writes wrong_file_review[_dry_run].csv (every multi-file pick and every row
left for a person). --apply writes a JSON backup of every changed row (all columns but search_vector), updates in
one transaction, checks the count and re-measures.

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
from backend.models.eu_law import EULaw  # noqa: E402
from backend.scripts.fix_eu_laws_2025_leftovers import check  # noqa: E402
from backend.scripts.import_corpus_update import (MAIN_ROOTS, compute_file_hash, file_root, main_file,  # noqa: E402
                                                  parsed_fields, stored_path, title_match, type_label)
from backend.services.law_database.xml_parser import FormexXMLParser  # noqa: E402
from backend.services.parsers.formex_parser import FormexParser  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "docs/LEG_2026-10"
TABLE = ROOT / "backend/data/leg_2026-10_table/leg_2026-10_table.csv"
VERSION = "LEG_2026-10"
MATCH_MIN = 0.4  # title_match of rows read from their act's file: 1% below 0.45 (15 Oct 2026, 18,294 rows)
KEEP_ON_ACT = {"32004D0411R(01)", "32004D0412R(01)", "32004D0417R(01)", "32004D0482R(01)", "32004R0729R(01)",
               "32004R0847R(01)", "32004R0859R(01)", "32006D0456R(01)", "32012R1081R(01)"}  # Victor, 14 Oct 2026
FILE_KEYS = ("short_title", "language", "page_count", "eea_relevance", "article_count", "recital_count",
             "annex_count", "page_first", "page_last", "eea_relevant")  # what the wrong file put there


def clean(s: str) -> str:
    return " ".join((s or "").split())


def plan(db, parser):
    table = {r["CELEX"]: (clean(r["Title of document"]), r["date_document"])
             for r in csv.DictReader(TABLE.open(encoding="utf-8-sig"))}
    rows = db.execute(text("SELECT id, uuid, celex, xml_path, content_hash, title FROM eu_laws "
                           "WHERE corpus_version = :v AND xml_path LIKE 'docs/LEG_2026-10/%'"), {"v": VERSION}).fetchall()
    fix, review, why = [], [], collections.Counter()
    title_only = 0
    for i, uuid, celex, xp, h, title in rows:
        if celex in KEEP_ON_ACT:
            why["kept on the republished act (Victor)"] += 1
            continue
        t_title, t_date = table.get(celex, ("", ""))
        picked, multi_score = main_file(CORPUS, uuid, celex, lambda: t_title, parser)
        cur = ROOT / xp
        if picked is None:
            why["no act file in the folder"] += 1
            review.append((i, celex, Path(xp).name, "", "", "no act file"))
            continue
        reasons = [k for k, bad in (("annex or cover page", file_root(cur) not in MAIN_ROOTS),
                                    ("another act file", picked != cur),
                                    ("filled from another file", compute_file_hash(cur) != h)) if bad]
        if not reasons:
            title_only += title_match(title, t_title) < MATCH_MIN
            continue
        p = parser.parse_file(picked)
        score = title_match(p.title, t_title)
        if reasons == ["another act file"] and title_match(parser.parse_file(cur).title, t_title) >= score:
            continue  # the current act file matches the metadata as well: no switch
        if multi_score is not None:
            review.append((i, celex, Path(xp).name, picked.name, f"{score:.2f}", "picked among several act files"))
        if not t_title or score < MATCH_MIN:
            why["act file's title does not match the metadata: left for a person"] += 1
            review.append((i, celex, Path(xp).name, picked.name, f"{score:.2f}", "title does not match: not written"))
            continue
        why[" + ".join(reasons)] += 1
        fix.append({"id": i, "celex": celex, "path": picked, "parsed": p, "title": t_title,
                    "date": t_date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t_date or "") else None})
    return fix, review, why, title_only, len(rows)


def new_values(row, f, xp_parser):
    """The UPDATE parameters for one row: act file + metadata, keeping what other writers own."""
    p = f["parsed"]
    fields = parsed_fields(p, stored_path(f["path"]), compute_file_hash(f["path"]), VERSION)
    root = ET.parse(f["path"]).getroot()
    old_extra = xp_parser._extract_extra_metadata(root)  # the older parser built the other rows' page keys
    extra = {k: v for k, v in (row["extra_metadata"] or {}).items() if k not in FILE_KEYS}
    extra.update(fields["extra_metadata"])
    extra.update({k: old_extra[k] for k in ("page_first", "page_last", "page_count") if k in old_extra})
    return {
        "id": row["id"], "xml_path": fields["xml_path"], "content_hash": fields["content_hash"], "title": f["title"],
        "doc_type": p.doc_type or type_label(row["celex"], row["doc_type_normalized"]),
        "doc_type_normalized": type_label(row["celex"], row["doc_type_normalized"]),
        "date": f["date"] or (p.date.isoformat() if p.date else None),
        "oj_reference": p.oj_reference or row["oj_reference"],
        "legal_basis": fields["legal_basis"], "citations": fields["citations"],
        "is_primary_legislation": fields["is_primary_legislation"],
        "policy_area": row["policy_area"] if row["eurovoc_fetched_at"] else fields["policy_area"],
        "subject_matter": xp_parser._extract_subject_matter(root) or None,
        "extra_metadata": json.dumps(extra, default=str),
    }


COLS = ("id", "xml_path", "content_hash", "title", "doc_type", "doc_type_normalized", "date", "oj_reference",
        "legal_basis", "citations", "is_primary_legislation", "policy_area", "subject_matter", "extra_metadata")
# one statement per 500 rows (psycopg2 execute_values): 10,519 single UPDATEs would hold the rows for minutes
UPDATE = ("UPDATE eu_laws e SET xml_path = v.xml_path, content_hash = v.content_hash, title = v.title, "
          "doc_type = v.doc_type, doc_type_normalized = v.doc_type_normalized, date = v.date, oj_reference = v.oj_reference, "
          "legal_basis = v.legal_basis, citations = v.citations, is_primary_legislation = v.is_primary_legislation, "
          "policy_area = v.policy_area, subject_matter = v.subject_matter, extra_metadata = v.extra_metadata "
          f"FROM (VALUES %s) AS v ({', '.join(COLS)}) WHERE e.id = v.id AND e.corpus_version = 'LEG_2026-10' RETURNING e.id")
TEMPLATE = "(%s, %s, %s, %s, %s, %s, %s::date, %s, %s::text[], %s::text[], %s::boolean, %s, %s::text[], %s::jsonb)"

MEASURE = ("SELECT count(*) FILTER (WHERE doc_type_normalized IN ('Annex', 'Table of Contents')), "
           "count(*) FILTER (WHERE upper(ltrim(title)) LIKE 'ANNEX%' OR upper(ltrim(title)) LIKE 'APPENDIX%'), "
           "count(*) FILTER (WHERE upper(ltrim(title)) LIKE 'OFFICIAL JOURNAL%') FROM eu_laws WHERE corpus_version = 'LEG_2026-10'")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db, parser, xp_parser = SessionLocal(), FormexParser(), FormexXMLParser()
    try:
        before = db.execute(text(MEASURE)).one()
        fix, review, why, title_only, n = plan(db, parser)
        print(f"[INFO] {n} rows read | to re-read from the act's file: {len(fix)} | left for a person: "
              f"{sum(1 for r in review if r[5] != 'picked among several act files')} | rows on the right file whose "
              f"stored title does not match the metadata (not touched): {title_only}")
        for k, v in why.most_common():
            print(f"[INFO]   {v:6d}  {k}")
        print(f"[INFO] now: typed Annex or Table of Contents {before[0]}, titled ANNEX/APPENDIX {before[1]}, "
              f"titled Official Journal {before[2]}")
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
        rev = ROOT / f"backend/data/backups/wrong_file_review{'' if a.apply else '_dry_run'}_{ts}.csv"
        with rev.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "celex", "current_file", "picked_file", "title_match", "note"])
            w.writerows(review)
        print(f"[INFO] review list ({len(review)} rows) -> {rev.relative_to(ROOT)}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        ids = [f["id"] for f in fix]
        cols = [c.name for c in EULaw.__table__.columns if c.name != "search_vector"]
        rows = {r["id"]: dict(r) for r in db.execute(text(f"SELECT {', '.join(cols)} FROM eu_laws WHERE id = ANY(:i)"), {"i": ids}).mappings()}
        backup = ROOT / f"backend/data/backups/eu_laws_wrong_file_before_{ts}.json"
        backup.write_text(json.dumps({"rows_before": list(rows.values())}, default=str))
        print(f"[OK] backup of {len(rows)} rows -> {backup.relative_to(ROOT)}")
        params = [tuple(new_values(rows[f["id"]], f, xp_parser)[c] for c in COLS) for f in fix]
        cur = db.connection().connection.cursor()  # the session's own transaction
        done = execute_values(cur, UPDATE, params, template=TEMPLATE, page_size=500, fetch=True)
        check(sorted(r[0] for r in done) == sorted(ids), f"updated {len(done)}, expected {len(ids)}: rolled back")
        done = len(done)
        db.commit()
        after = db.execute(text(MEASURE)).one()
        left = plan(db, parser)[0]
        print(f"[OK] committed: {done} rows re-read from the act's file")
        print(f"[VERIFY] typed Annex or Table of Contents {before[0]} -> {after[0]}, titled ANNEX/APPENDIX {before[1]} -> "
              f"{after[1]}, titled Official Journal {before[2]} -> {after[2]} | rows still on the wrong file: {len(left)}")
        return 0 if not left else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
