#!/usr/bin/env python3.12
"""Write eu_laws.oj_reference as the Official Journal citation, read from Cellar, without moving updated_at.

17 Oct 2026: the column held five shapes from three writers ("L 119/1" 23,501, "L 2025/40, p. 1" 3,565, "OJ L,
2026/1672, 10.9.2026" 2,269, "P 065/1173" 4, a few one-offs) and 1,517 laws had none; the lookup route
/eur-lex/oj/{series}/{year}/{number} found none of the "L 2025/40, p. 1" acts (PPWR, the Data Act). Victor chose the
form the acts use to cite each other (services/oj_citation.py) and that the rewrite keeps the change signal: only the
notation changes, so a client syncing by updated_from must not receive 29,000 laws again.

For each law Cellar gives either its act-by-act publication (official-journal-act_*: series, OJ year and number,
date) or the issue it was published in (resource_legal_published_in_official-journal: series, issue, supplement,
date) and the first page of each language's manifestation. Each call carries two control laws, an issue (GDPR:
OJ L 119, 4.5.2016, p. 1) and an act-by-act one (PPWR: OJ L, 2025/40, 22.1.2025), and counts only if both come
back as expected.
  - An act of 2004-2007 also sits in a Maltese special issue ("OJ L 153 M", published later): the earliest issue
    is the original and is cited.
  - The page is the English edition's: pages differ between language editions (Regulation 2840/72: English
    L 300/190, French and German p. 188). Cellar's English page; else the export's stored "L 119/1", read from the
    English Formex file, when its series and issue agree; else the French, then the German page (acts before 1973
    without an English edition).
  - Cellar's English page and the export's page agreed on all but 7 of about 23,900 laws (dry run, 17 Oct 2026),
    and each side was wrong somewhere (95/308/EC: the act's own header reads L 186/42, Cellar 44; 48/90: the header
    reads L 8/16, the export 1). On a disagreement the page printed in the act's own English text decides; without
    it the law is left and reported.
  - A stored issue that is not Cellar's (32014R1322 holds another act's file, a corrigendum of L 127/44): the row is
    left and reported, since its other fields may describe that other act.
  - Cellar silent on a law, or naming two publications on the same day: the stored value stays (unknown is never
    written as empty).
  - Every write keeps updated_at (migration 302's switch, this transaction only) and is skipped when another writer
    changed the value since it was read.

Default: the laws whose reference is empty or not yet in that form (the daily tier, key eu_laws_oj_reference: a law
imported from a bulk export arrives without one, since the importers no longer write the column). --all re-reads
every law and corrects any stored citation Cellar gives differently. Dry run unless --apply. Exits 1 when Cellar
fails the controls (CellarDown) or the time budget runs out; what was written stays.

Usage (from backend/):
    python3.12 scripts/fill_eu_laws_oj_reference.py [--all] [--apply] [--limit N] [--cache FILE] [--backup]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))  # production runs with PYTHONPATH=/app (the backend folder)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND.parent / ".env")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from scripts.leg_export_metadata import SPARQL, Budget, CellarDown  # noqa: E402
from services.oj_citation import (OFFICIAL_SQL, act_citation, export_issue_parts, issue_citation,  # noqa: E402
                                  parse_oj_id)

BATCH = 80
BUDGET_SECONDS = 1200   # under the daily tier's 30-minute timeout
CHUNK = 500
LANG = "http://publications.europa.eu/resource/authority/language/"
PAGE_LANGS = ("ENG", "FRA", "DEU")
SERIES = {"OJ-L": "L", "OJ-C": "C"}
CONTROLS = {"32016R0679": "OJ L 119, 4.5.2016, p. 1", "32025R0040": "OJ L, 2025/40, 22.1.2025"}
QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?c ?k ?coll ?num ?yr ?pub ?id ?pg ?lang WHERE {{
  VALUES ?c {{ {values} }}
  ?w cdm:resource_legal_id_celex ?c .
  {{ ?w cdm:official-journal-act_part_of_collection_document ?coll ; cdm:official-journal-act_number ?num ;
        cdm:official-journal-act_date_publication ?pub . OPTIONAL {{ ?w cdm:official-journal-act_year ?yr }}
     BIND("act" AS ?k) }}
  UNION
  {{ ?w cdm:resource_legal_published_in_official-journal ?oj . ?oj cdm:work_id_document ?id ;
        cdm:publication_general_date_publication ?pub . BIND("issue" AS ?k) }}
  UNION
  {{ ?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language ?lang .
     FILTER(?lang IN (<{lang}ENG>, <{lang}FRA>, <{lang}DEU>))
     ?m cdm:manifestation_manifests_expression ?e ; cdm:manifestation_official-journal_part_page_first ?pg .
     BIND("page" AS ?k) }}
}}"""
UPDATE = ("UPDATE eu_laws e SET oj_reference = v.new FROM (VALUES %s) AS v (id, old, new) "
          "WHERE e.id = v.id AND e.oj_reference IS NOT DISTINCT FROM v.old RETURNING e.id, e.updated_at")


def _empty() -> dict:
    return {"acts": [], "issues": [], "pages": {}, "seen": False}


def parse(bindings: List[dict]) -> Dict[str, dict]:
    """Cellar's rows -> {CELEX: {"acts": [[series, year, number, date]], "issues": [[series, issue, supplement,
    date]], "pages": {lang: [pages]}, "seen": True}}; lists, not sets, so the facts can be cached as JSON."""
    got: Dict[str, dict] = {}
    for b in bindings:
        v = lambda k: b.get(k, {}).get("value")  # noqa: E731
        g = got.setdefault(v("c"), {**_empty(), "seen": True})
        pub = (v("pub") or "")[:10]
        if v("k") == "act" and pub:
            series = SERIES.get((v("coll") or "").rsplit("/", 1)[-1])
            year = (v("yr") or pub)[:4]
            if series and (v("num") or "").isdigit():
                item = [series, int(year), int(v("num")), pub]
                if item not in g["acts"]:
                    g["acts"].append(item)
        elif v("k") == "issue" and pub:
            parts = parse_oj_id(v("id"))
            if parts:
                item = [parts[0], parts[2], parts[3], pub]
                if item not in g["issues"]:
                    g["issues"].append(item)
        elif v("k") == "page" and (v("pg") or "").strip("0").isdigit():
            pages = g["pages"].setdefault((v("lang") or "").rsplit("/", 1)[-1], [])
            if int(v("pg")) not in pages:
                pages.append(int(v("pg")))
    return got


NEEDS_TEXT = "page: Cellar and the export disagree; needs the act's text"
# the head of an act's English text: "5.8.1995 EN Official Journal of the European Communities L 186/42 COUNCIL ..."
_HEADER = re.compile(r"Official Journal of the European (?:Union|Communities)\s+([LC])\s+0*(\d+)\s?([A-Z]{0,2})/0*(\d+)")


def text_page(head: Optional[str], series: str, issue: int, supplement: str) -> Optional[int]:
    """The first page the act's own English text prints, when its header names this issue."""
    m = _HEADER.search(head or "")
    if m and (m.group(1), int(m.group(2)), m.group(3)) == (series, issue, supplement):
        return int(m.group(4))
    return None


def citation(facts: Optional[dict], stored: Optional[str], head: Optional[str] = None) -> Tuple[Optional[str], str]:
    """(the citation, why) for one law; None when the sources do not settle it. `head`: the start of the act's
    English text, read only when Cellar's English page and the export's disagree (NEEDS_TEXT)."""
    f = facts or _empty()
    if not f.get("seen"):
        return None, "not at Cellar"
    if f["acts"]:
        if len(f["acts"]) > 1:
            return None, "several act-by-act publications"
        series, year, number, pub = f["acts"][0]
        return act_citation(series, year, number, dt.date.fromisoformat(pub)), "act by act"
    if not f["issues"]:
        return None, "no OJ publication at Cellar"
    # an act of 2004-2007 is also in a Maltese special issue ("OJ L 153 M", 2006): the original is the earliest
    first = min(p for *_, p in f["issues"])
    originals = [i for i in f["issues"] if i[3] == first]
    if len(originals) > 1:
        return None, "several issues on the same day"
    series, issue, supplement, pub = originals[0]
    old = export_issue_parts(stored)
    if old and old[:3] != (series, issue, supplement):
        return None, "stored issue is not Cellar's: the row may hold another act's file"
    eng = min(f["pages"]["ENG"]) if f["pages"].get("ENG") else None
    if old and eng is not None and old[3] != eng:
        page = text_page(head, series, issue, supplement)
        if page is None:
            return None, NEEDS_TEXT if head is None else "page: Cellar and the export disagree, the text does not say"
        why = "issue, page from the act's text (Cellar and the export disagree)"
    elif eng is not None:
        page, why = eng, "issue, page from ENG"
    elif old:
        page, why = old[3], "issue, page from the export's English file"
    else:
        lang = next((lg for lg in PAGE_LANGS[1:] if f["pages"].get(lg)), None)
        page, why = (min(f["pages"][lang]), f"issue, page from {lang}") if lang else (None, "issue, no page known")
    return issue_citation(series, issue, dt.date.fromisoformat(pub), page, supplement), why


def _ask(batch: List[str], budget: Budget) -> Dict[str, dict]:
    budget.check()
    asked = batch + [c for c in CONTROLS if c not in batch]
    values = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in asked)
    q = QUERY.format(values=values, lang=LANG)
    try:
        req = urllib.request.Request(SPARQL + "?" + urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"}),
                                     headers={"Accept": "application/sparql-results+json"})
        got = parse(json.load(urllib.request.urlopen(req, timeout=90))["results"]["bindings"])
    except Exception:  # noqa: BLE001 -- a failed call counts against the budget below
        got = {}
    ok = all(citation(got.get(c), None)[0] == want for c, want in CONTROLS.items())
    budget.result(ok)
    if not ok:
        return {}
    return {c: got.get(c) or _empty() for c in batch}


def _ask_or_split(batch: List[str], budget: Budget) -> Dict[str, dict]:
    """Retry once, then split in halves (the pattern of leg_export_metadata); a law that fails alone stays unknown."""
    for attempt in range(2):
        got = _ask(batch, budget)
        if got:
            return got
        time.sleep(3 * (attempt + 1))
    if len(batch) == 1:
        return {}
    mid = len(batch) // 2
    return {**_ask_or_split(batch[:mid], budget), **_ask_or_split(batch[mid:], budget)}


def cellar_oj_facts(celexes: List[str], budget: Budget, cache: Optional[Path] = None) -> Tuple[Dict[str, dict], Optional[str]]:
    """({CELEX: facts}, why Cellar stopped the run or None); what was read before a stop is kept."""
    store = json.loads(cache.read_text()) if cache and cache.exists() else {}
    todo = [c for c in celexes if c not in store]
    stopped = None
    for i in range(0, len(todo), BATCH):
        try:
            store.update(_ask_or_split(todo[i:i + BATCH], budget))
        except CellarDown as e:
            stopped = str(e)
        if cache and (stopped or (i // BATCH) % 25 == 24 or i + BATCH >= len(todo)):
            cache.write_text(json.dumps(store))
        if stopped:
            break
        if (i // BATCH) % 25 == 24:
            print(f"[INFO]   Cellar: {min(i + BATCH, len(todo))} of {len(todo)} asked", flush=True)
    return {c: store[c] for c in celexes if c in store}, stopped


def shape(ref: Optional[str]) -> str:
    """A label for the stored form, for the report."""
    if not ref:
        return "empty"
    for label, pat in (("OJ L, 2025/40, 22.1.2025", r"^OJ [LC], \d{4}/\d+, \d"), ("L 2025/40, p. 1", r"^[LC] \d{4}/\d+, p\."),
                       ("L 119/1", r"^[LCP] \d+[A-Z]*/\d+$"), ("OJ L 119, 4.5.2016, p. 1", r"^OJ ([LC] )?\d+( [A-Z]+)?, \d")):
        if re.match(pat, ref):
            return label
    return "other"


def write(db, part: List[Tuple[int, Optional[str], str]]) -> int:
    """One transaction: the switch of migration 302 keeps updated_at; rolled back if any touched row's moved."""
    ids = [i for i, _, _ in part]
    before = dict(db.execute(text("SELECT id, updated_at FROM eu_laws WHERE id = ANY(:i)"), {"i": ids}).fetchall())
    db.execute(text("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)"))
    cur = db.connection().connection.cursor()
    got = execute_values(cur, UPDATE, part, template="(%s, %s, %s)", page_size=len(part), fetch=True)
    moved = [i for i, u in got if u != before.get(i)]
    if moved:
        db.rollback()
        raise RuntimeError(f"updated_at moved on {len(moved)} rows (first {moved[:5]}): chunk rolled back")
    db.commit()
    return len(got)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true", help="re-read every law, not only those without the citation")
    ap.add_argument("--limit", type=int, default=0, help="only the first N laws (a test run)")
    ap.add_argument("--cache", type=Path, help="JSON file keeping Cellar's answers between runs")
    ap.add_argument("--backup", action="store_true", help="write the replaced values to backend/data/backups first")
    a = ap.parse_args()
    db = SessionLocal()
    budget = Budget(BUDGET_SECONDS)
    try:
        where = "" if a.all else " AND (oj_reference IS NULL OR oj_reference !~ :official)"
        rows = db.execute(text("SELECT id, celex, oj_reference FROM eu_laws WHERE coalesce(celex, '') <> ''"
                               f"{where} ORDER BY id"), {"official": OFFICIAL_SQL}).fetchall()
        db.rollback()  # no transaction open while Cellar is read
        rows = rows[:a.limit] if a.limit else rows
        print(f"[INFO] {len(rows)} laws to read at Cellar ({'all' if a.all else 'without the citation'})", flush=True)
        facts, stopped = cellar_oj_facts(sorted({c for _, c, _ in rows}), budget, a.cache)
        changes, why, moves, samples = [], collections.Counter(), collections.Counter(), collections.defaultdict(list)
        decided = {i: citation(facts.get(c), stored) if c in facts else (None, "not asked (Cellar stopped)")
                   for i, c, stored in rows}
        # a page Cellar and the export disagree on: the act's own English text decides (a handful of laws)
        ask = [i for i, (_, r) in decided.items() if r == NEEDS_TEXT]
        if ask:
            heads = dict(db.execute(text("SELECT id, left(body_txt, 600) FROM eu_laws WHERE id = ANY(:i)"), {"i": ask}).fetchall())
            db.rollback()
            for i, c, stored in rows:
                if i in heads or i in ask:
                    decided[i] = citation(facts.get(c), stored, heads.get(i) or "")
        for i, celex, stored in rows:
            new, reason = decided[i]
            why[reason] += 1
            if len(samples[reason]) < 3:
                samples[reason].append(f"{celex}: {stored!r} -> {new!r}")
            if new and new != stored:
                changes.append((i, stored, new))
                moves[(shape(stored), shape(new))] += 1
        print(f"[INFO] Cellar answered for {sum(1 for c in {c for _, c, _ in rows} if (facts.get(c) or {}).get('seen'))} "
              f"of {len({c for _, c, _ in rows})} CELEX | to write: {len(changes)}")
        for k, n in why.most_common():
            print(f"[INFO]   {n:6d}  {k}   e.g. {'; '.join(samples[k])}")
        for (old, new), n in moves.most_common():
            print(f"[INFO]   {n:6d}  {old}  ->  {new}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
        else:
            if a.backup and changes:
                path = BACKEND / f"data/backups/eu_laws_oj_reference_before_{dt.datetime.now():%Y%m%d_%H%M}.json"
                path.parent.mkdir(parents=True, exist_ok=True)  # untracked: absent from a fresh checkout
                path.write_text(json.dumps({"columns": ["id", "oj_reference_before", "oj_reference_after"], "rows": changes,
                                            "restore": "set oj_reference back by id inside a transaction with the switch "
                                                       "on (migration 302)"}))
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
