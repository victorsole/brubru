#!/usr/bin/env python3.12
"""Write eu_laws.legal_basis in one form, read from Cellar, without moving updated_at.

18 Oct 2026: the column held four shapes from three writers (the importers' "Having regard to the Treaty ..."
sentences, cut before the article, 7,483; "Regulation 1151/2012" 8,276; whole recitals 3,357; "Article 114 TFEU" 3)
and 13,505 laws had none, GDPR and the DSA among them. Victor chose one form, read from the Publications Office:
what each law is adopted under (cdm:resource_legal_based_on_resource_legal), in the words EU acts use to cite it.

  - A Treaty article: "Article 16 TFEU", "Article 29 TEU", "Article 100a EEC Treaty", "Article 41 of the Charter of
    Fundamental Rights". Its CELEX states treaty and article (12016E114 = TFEU Article 114; 11957E100A = EEC Treaty
    Article 100a; 11992MK03 = TEU Article K.3); the TFEU is the E treaty from 2008, the EC Treaty from 1992, the EEC
    Treaty before. Read from the CELEX, never from the title: the title of 12012E016 (Article 16 TFEU) also names
    "ex Article 286", the article it replaced.
  - An act (the empowering act of an implementing or delegated act, or any other act): its English title from
    Cellar up to its date, the way acts cite each other ("Directive (EU) 2025/2205 of the European Parliament and of
    the Council", "Commission Implementing Regulation (EU) 2021/405"). An old act whose title holds no number
    takes the number of EUR-Lex's prefix ("2008/721/EC: Commission Decision of ..." -> "Commission Decision
    2008/721/EC"), or, without one, keeps the title to its date ("Council Directive of 15 July 1975").
  - Anything else (protocols, acts of accession): the English title as Cellar gives it.
  Treaty articles first, then the rest, each by CELEX; the same label once. The CELEX numbers, in the same order,
  go to extra_metadata.legal_basis_celex, the day of the read to extra_metadata.legal_basis_checked.

Cellar silent on a law: the stored value stays and the law is asked again next run. A law Cellar knows with no
legal basis (a corrigendum, most CFSP decisions before 2009): an empty list. Every call carries two control laws and
counts only if both come back as expected (GDPR: Article 16 TFEU; Implementing Regulation (EU) 2026/2266: Directive
(EU) 2025/2205). Every write keeps updated_at (migration 302's switch, this transaction only) and is skipped when
another writer changed the value since it was read. This script is the column's only writer: the importers and the
daily OJ sync no longer fill it.

Default: the laws never read (the daily tier, key eu_laws_legal_basis). --all re-reads every law. Dry run unless
--apply. Exits 1 when Cellar fails the controls or the time budget runs out; what was written stays.

Usage (from backend/):
    python3.12 scripts/fill_eu_laws_legal_basis.py [--all] [--apply] [--limit N] [--budget SECONDS] [--backup]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))  # production runs with PYTHONPATH=/app (the backend folder)

BATCH = 60
BUDGET_SECONDS = 1200   # under the daily tier's 30-minute timeout
CHUNK = 500
ENG = "http://publications.europa.eu/resource/authority/language/ENG"
CONTROLS = {"32016R0679": ["Article 16 TFEU"],
            "32026R2266": ["Directive (EU) 2025/2205 of the European Parliament and of the Council"]}
QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?c ?tc ?tt WHERE {{
  VALUES ?c {{ {values} }}
  ?w cdm:resource_legal_id_celex ?c .
  OPTIONAL {{ ?w cdm:resource_legal_based_on_resource_legal ?t . ?t cdm:resource_legal_id_celex ?tc .
             OPTIONAL {{ ?e cdm:expression_belongs_to_work ?t ; cdm:expression_uses_language <{eng}> ;
                                cdm:expression_title ?tt }} }}
}}"""
UPDATE = ("UPDATE eu_laws e SET legal_basis = v.new, extra_metadata = coalesce(e.extra_metadata, '{}'::jsonb) || "
          "jsonb_build_object('legal_basis_celex', v.cx, 'legal_basis_checked', v.day) "
          "FROM (VALUES %s) AS v (id, old, new, cx, day) "
          "WHERE e.id = v.id AND e.legal_basis IS NOT DISTINCT FROM v.old RETURNING e.id, e.updated_at")

# ---- the label --------------------------------------------------------------------------------------------------

ART_CELEX = re.compile(r"^1(\d{4})([EMAKP])([A-Z]?)(\d{2,3})([A-Z]?)$")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATED = re.compile(rf"^(.+?)[\s,]+of\s+\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}\b")
UP_TO_DATE = re.compile(rf"^(.+?[\s,]+of\s+\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}})\b")
PREFIX = re.compile(r"^\s*(\d{2,4}\s*/\s*\d{1,4}\s*/\s*[A-Za-z]+(?:\s*,\s*[A-Za-z]+)*)\s*(?::|-|,)\s*")
NUMBERED = re.compile(r"\d{1,4}/\d{1,4}|\((?:EU|EC|EEC|EC, Euratom|EU, Euratom|Euratom)\)\s*(?:No\s*)?\d")


def treaty_article(celex: str) -> Optional[str]:
    """'Article 114 TFEU' for 12016E114: the CELEX of a Treaty article states the treaty and the article."""
    m = ART_CELEX.match(celex)
    if not m:
        return None
    year, letter, pre, num, suf = int(m[1]), m[2], m[3], int(m[4]), m[5].lower()
    art = f"{pre}.{num}" if pre else f"{num}{suf}"
    if letter == "P":
        return f"Article {art} of the Charter of Fundamental Rights"
    name = {"M": "TEU", "A": "Euratom Treaty", "K": "ECSC Treaty"}.get(letter) or (
        "TFEU" if year >= 2008 else "EC Treaty" if year >= 1992 else "EEC Treaty")
    return f"Article {art} {name}"


def label(celex: str, title: Optional[str]) -> str:
    """How EU acts cite the provision or act `celex`, from its CELEX (Treaty articles) or its English title."""
    art = treaty_article(celex)
    if art:
        return art
    t = " ".join((title or "").split())
    if not t:
        return celex
    pm = PREFIX.match(t)
    number = re.sub(r"\s*,\s*", ", ", re.sub(r"\s*/\s*", "/", pm.group(1))) if pm else None
    t = PREFIX.sub("", t, count=1)
    m = DATED.match(t)
    short = (m.group(1) if m else t).rstrip(" ,;:")
    if not NUMBERED.search(short):
        if number:  # an old act carries its number only in EUR-Lex's prefix
            head, sep, rest = short.partition(" of ")
            short = f"{head} {number}{sep}{rest}" if sep else f"{short} {number}"
        elif m:  # no number anywhere: the title up to its date names the act
            short = UP_TO_DATE.match(t).group(1)
    return short


def basis(targets: Dict[str, Optional[str]]) -> Tuple[List[str], List[str]]:
    """(labels, CELEX numbers): Treaty articles first, then the rest, each by CELEX; a label once."""
    order = sorted(targets, key=lambda c: (treaty_article(c) is None, c))
    labels, seen = [], set()
    for c in order:
        lab = label(c, targets[c])
        if lab not in seen:
            seen.add(lab)
            labels.append(lab)
    return labels, order


# ---- Cellar -----------------------------------------------------------------------------------------------------

def parse(bindings: List[dict]) -> Dict[str, Dict[str, Optional[str]]]:
    """{law CELEX: {target CELEX: English title or None}} for every law Cellar knows ({} = no legal basis)."""
    got: Dict[str, Dict[str, Optional[str]]] = {}
    for b in bindings:
        tg = got.setdefault(b["c"]["value"], {})
        tc = b.get("tc", {}).get("value")
        if tc:
            tt = b.get("tt", {}).get("value")
            if tt or tc not in tg:
                tg[tc] = tt or tg.get(tc)
    return got


def _ask(batch: List[str], budget) -> Optional[Dict[str, dict]]:
    from scripts.leg_export_metadata import SPARQL
    budget.check()
    asked = batch + [c for c in CONTROLS if c not in batch]
    values = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in asked)
    try:
        req = urllib.request.Request(SPARQL, data=urllib.parse.urlencode(
            {"query": QUERY.format(values=values, eng=ENG), "format": "application/sparql-results+json"}).encode(),
            headers={"Accept": "application/sparql-results+json", "Content-Type": "application/x-www-form-urlencoded"})
        got = parse(json.load(urllib.request.urlopen(req, timeout=120))["results"]["bindings"])
    except Exception:  # noqa: BLE001 -- a failed call counts against the budget below
        got = {}
    ok = all(c in got and basis(got[c])[0] == want for c, want in CONTROLS.items())
    budget.result(ok)
    return {c: got[c] for c in batch if c in got} if ok else None


def _ask_or_split(batch: List[str], budget) -> Dict[str, dict]:
    """Retry once, then split in halves; a law that fails alone stays unread."""
    for attempt in range(2):
        got = _ask(batch, budget)
        if got is not None:
            return got
        time.sleep(3 * (attempt + 1))
    if len(batch) == 1:
        return {}
    mid = len(batch) // 2
    return {**_ask_or_split(batch[:mid], budget), **_ask_or_split(batch[mid:], budget)}


def cellar_bases(celexes: List[str], budget) -> Tuple[Dict[str, dict], Optional[str]]:
    """({law CELEX: targets}, why Cellar stopped the run or None); what was read before a stop is kept."""
    from scripts.leg_export_metadata import CellarDown
    store: Dict[str, dict] = {}
    for i in range(0, len(celexes), BATCH):
        try:
            store.update(_ask_or_split(celexes[i:i + BATCH], budget))
        except CellarDown as e:
            return store, str(e)
        if (i // BATCH) % 50 == 49:
            print(f"[INFO]   Cellar: {min(i + BATCH, len(celexes))} of {len(celexes)} asked", flush=True)
    return store, None


# ---- the write --------------------------------------------------------------------------------------------------

def changes_for(rows, bases: Dict[str, dict], today: str) -> List[tuple]:
    """(id, stored, labels, celex json, day) for every law Cellar answered whose value or mark is not yet written."""
    out = []
    for i, celex, stored, checked in rows:
        if celex not in bases:
            continue  # Cellar silent: keep the stored value, ask again next run
        labels, cx = basis(bases[celex])
        if list(stored or []) == labels and checked:
            continue
        out.append((i, stored, labels, json.dumps(cx), today))
    return out


def write(db, part: List[tuple]) -> int:
    """One transaction: the switch of migration 302 keeps updated_at; rolled back if any touched row's moved."""
    from psycopg2.extras import execute_values
    from sqlalchemy import text
    ids = [p[0] for p in part]
    before = dict(db.execute(text("SELECT id, updated_at FROM eu_laws WHERE id = ANY(:i)"), {"i": ids}).fetchall())
    db.execute(text("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)"))
    cur = db.connection().connection.cursor()
    got = execute_values(cur, UPDATE, part, template="(%s, %s::text[], %s::text[], %s::jsonb, %s)",
                         page_size=len(part), fetch=True)
    moved = [i for i, u in got if u != before.get(i)]
    if moved:
        db.rollback()
        raise RuntimeError(f"updated_at moved on {len(moved)} rows (first {moved[:5]}): chunk rolled back")
    db.commit()
    return len(got)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true", help="re-read every law, not only those never read")
    ap.add_argument("--limit", type=int, default=0, help="only the first N laws (a test run)")
    ap.add_argument("--budget", type=float, default=BUDGET_SECONDS, help="seconds Cellar may take (0 = no limit)")
    ap.add_argument("--backup", action="store_true", help="write the replaced values to backend/data/backups first")
    a = ap.parse_args()
    import logging
    from dotenv import load_dotenv
    load_dotenv(BACKEND.parent / ".env")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    from sqlalchemy import text
    from core.database import SessionLocal
    from scripts.leg_export_metadata import Budget
    db = SessionLocal()
    budget = Budget(a.budget or None)
    try:
        where = "" if a.all else " AND extra_metadata->>'legal_basis_checked' IS NULL"
        rows = db.execute(text("SELECT id, celex, legal_basis, extra_metadata->>'legal_basis_checked' FROM eu_laws "
                               f"WHERE coalesce(celex, '') <> ''{where} ORDER BY id")).fetchall()
        db.rollback()  # no transaction open while Cellar is read
        rows = rows[:a.limit] if a.limit else rows
        print(f"[INFO] {len(rows)} laws to read at Cellar ({'all' if a.all else 'never read'})", flush=True)
        bases, stopped = cellar_bases(sorted({r[1] for r in rows}), budget)
        changes = changes_for(rows, bases, dt.date.today().isoformat())
        n_empty = sum(1 for c in changes if not c[2])
        moves = collections.Counter(("empty" if not c[1] else "stored") + " -> " + ("empty" if not c[2] else "labels")
                                    for c in changes)
        print(f"[INFO] Cellar answered for {len(bases)} of {len({r[1] for r in rows})} CELEX | to write: {len(changes)} "
              f"({n_empty} with no legal basis at Cellar) | {dict(moves)}")
        for c in changes[:5]:
            print(f"[INFO]   e.g. id {c[0]}: {(c[1] or [])[:2]} -> {c[2][:3]}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
        else:
            if a.backup and changes:
                path = BACKEND / f"data/backups/eu_laws_legal_basis_before_{dt.datetime.now():%Y%m%d_%H%M}.json"
                path.parent.mkdir(parents=True, exist_ok=True)  # untracked: absent from a fresh checkout
                path.write_text(json.dumps({"columns": ["id", "legal_basis_before"], "rows": [(c[0], c[1]) for c in changes],
                                            "restore": "set legal_basis back by id inside a transaction with the switch "
                                                       "on (migration 302); drop extra_metadata legal_basis_celex and "
                                                       "legal_basis_checked"}))
                print(f"[OK] backup of {len(changes)} rows -> {path.relative_to(BACKEND.parent)}")
            done = 0
            for j in range(0, len(changes), CHUNK):
                done += write(db, changes[j:j + CHUNK])
                time.sleep(0.2)
            print(f"[OK] written: {done} of {len(changes)} (a row another writer changed meanwhile is left); updated_at kept")
        if stopped:
            print(f"[ERROR] Cellar stopped the run: {stopped}; what was written stays", file=sys.stderr)
            return 1
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
