#!/usr/bin/env python3.12
"""Set eu_laws.date to the date the act's title gives it, Cellar's date otherwise; a corrigendum gets Cellar's.

20 Oct 2026: 665 laws held a date that was neither. Read against every title (where title and Cellar differ, the act's signature sides with the title):

  - 540 corrigenda held the corrected act's date (the old parser read it from the corrigendum's title) or their
    Formex date, not their own (Cellar's work_date_document, the corrigendum's publication, which the others hold).
  - 125 acts held the old parser's misreadings (the OJ publication date, a date cited in the text) or Cellar's
    errors, copied by the importer and the daily sync: 32026R0144 "of 14 January 2026" held 2025-01-14 at Cellar.
  - 86 acts hold the right date while Cellar's is wrong (32013D0719 "of 16 November 2012": Cellar 2013-11-16):
    left as they are, listed.

23 Oct 2026 (register O65): the title can be wrong too. In 26 acts a corrigendum corrected the title's date to Cellar's
("for: 4 April 2006, read: 4 April 2005", 32006D0635R(01)); the rule now takes Cellar's date when a corrigendum of the
act corrects the title's date to exactly it (leg_folder.act_date, corrigendum_corrections).

The rule is leg_folder.act_date, which the importer, the repair script and the daily Cellar sync apply. Cellar's
date is the LEG_2026-10 folder's tree_non_inferred.rdf (the export's own metadata); a row with no folder keeps its
stored date as Cellar's. recheck_acts applies the rule to a few acts: the importer calls it for the acts of the
corrigenda it wrote and for acts whose title and Cellar disagree, and the hot tier's fetch_eu_law_bodies for the acts
of the corrigenda whose text arrived in the last 3 days (the daily Cellar sync inserts a corrigendum without text).
Each write is skipped when another writer changed the date since it was read; updated_at moves (a corrected date
partners should receive). Dry run unless --apply.

Usage (from backend/):
    python3.12 scripts/fix_eu_laws_dates.py [--apply] [--backup] [--dump PATH]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import functools
import json
import re
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))  # production runs with PYTHONPATH=/app (the backend folder)

CHUNK = 200
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
UPDATE = """UPDATE eu_laws e SET date = v.new::date
FROM (VALUES %s) AS v(id, old, new)
WHERE e.id = v.id AND e.date IS NOT DISTINCT FROM v.old::date
RETURNING e.id"""


def changes_for(rows, recorded_of, corrections_of=lambda celex: ()):
    """(id, celex, stored, new, how) for every row whose date the rule changes; (id, celex, stored, cellar) where the
    stored date is the title's and Cellar's differs. corrections_of(celex): the (old, new) pairs its corrigenda state."""
    from scripts.leg_folder import act_date
    out, cellar_wrong = [], []
    for i, celex, uuid, stored, title, version in rows:
        recorded = recorded_of(uuid, version) or stored
        new = act_date(celex, title, recorded, corrections_of(celex))
        if new and new != stored:
            out.append((i, celex, stored, new, "corrigendum" if re.search(r"R\(\d{2}\)$", celex) else "act"))
        elif recorded != stored:
            cellar_wrong.append((i, celex, stored, recorded))
    return out, cellar_wrong


def cellar_dates(celexes) -> dict:
    """{CELEX: work_date_document} read at Cellar now, for CELEX values with exactly one date."""
    import urllib.parse
    import urllib.request
    vals = " ".join('"%s"^^<http://www.w3.org/2001/XMLSchema#string>' % c for c in sorted(set(celexes)))
    if not vals:
        return {}
    q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> SELECT ?c ?d WHERE { VALUES ?c { %s } "
         "?w cdm:resource_legal_id_celex ?c . ?w cdm:work_date_document ?d }" % vals)
    req = urllib.request.Request(f"{SPARQL}?{urllib.parse.urlencode({'query': q})}",
                                 headers={"Accept": "application/sparql-results+json",
                                          "User-Agent": "Brubru data check (hello@beresol.eu)"})
    got: dict = {}
    for b in json.load(urllib.request.urlopen(req, timeout=120))["results"]["bindings"]:
        got.setdefault(b["c"]["value"], set()).add(b["d"]["value"][:10])
    return {c: d.pop() for c, d in got.items() if len(d) == 1}


def fresh_recorded(rows, recorded_of, corr) -> dict:
    """{uuid: Cellar's date now} for acts whose corrigendum corrects the title's own date to a date the export's metadata
    (or, with no export, the stored date) does not hold: the export is a snapshot and Cellar may have been corrected
    since (32022R0363: export 2022-01-02, Cellar 2022-03-02 after the helpdesk's fix of 23 Oct 2026). One SPARQL query
    for the few acts concerned."""
    from scripts.leg_folder import title_date
    stale = {}
    for _i, celex, uuid, stored, title, version in rows:
        t = title_date(title)
        news = {new for old, new in corr.get(celex, ()) if old == t}
        if uuid and news and (recorded_of(uuid, version) or stored) not in news:
            stale[celex] = uuid
    live = cellar_dates(stale) if stale else {}
    return {stale[c]: d for c, d in live.items() if stale.get(c)}


def recheck_changes(db, acts, dump: Path | None = None) -> list:
    """What the rule changes for these acts, as changes_for lists it; nothing is written (recheck_acts writes it).
    Cellar's date is each act's folder under dump; with no folder (no dump on Railway) the stored date stands for it,
    and Cellar is read live wherever a corrigendum corrects the title to a date that is not the stored one."""
    from sqlalchemy import text
    from scripts.leg_folder import corrigendum_corrections, rdf_meta
    acts = sorted({a for a in acts if a})
    if not acts:
        return []
    rows = db.execute(text("SELECT id, celex, uuid, date::text, title, corpus_version FROM eu_laws "
                           "WHERE celex = ANY(:a)"), {"a": acts}).fetchall()
    corr = corrigendum_corrections(db, acts, dump)

    def recorded_of(uuid, version):
        return rdf_meta(dump, uuid)["date"] if dump is not None and uuid and (Path(dump) / uuid).is_dir() else None

    live = fresh_recorded(rows, recorded_of, corr)
    return changes_for(rows, lambda u, v: live.get(u) or recorded_of(u, v), lambda c: corr.get(c, ()))[0]


def recheck_acts(db, acts, dump: Path | None = None) -> int:
    """Apply the rule again to these acts and write what it changes; returns the rows written. The importer calls it
    for the acts of the corrigenda it wrote (a corrigendum may correct its act's title date) and for acts whose title
    and Cellar disagree; fetch_eu_law_bodies for the acts of corrigenda whose text just arrived."""
    from sqlalchemy import text
    changes = recheck_changes(db, acts, dump)
    if not changes:
        return 0
    done = 0
    for i, _celex, old, new, _how in changes:
        done += db.execute(text("UPDATE eu_laws SET date = CAST(:new AS date) WHERE id = :i "
                                "AND date IS NOT DISTINCT FROM CAST(:old AS date)"),
                           {"new": new, "i": i, "old": old}).rowcount or 0
    db.commit()
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", action="store_true", help="write the replaced dates to backend/data/backups first")
    ap.add_argument("--dump", default=str(BACKEND.parent / "docs/LEG_2026-10"), help="the LEG_2026-10 folders")
    a = ap.parse_args()
    import logging
    from dotenv import load_dotenv
    load_dotenv(BACKEND.parent / ".env")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    from psycopg2.extras import execute_values
    from sqlalchemy import text
    from core.database import SessionLocal
    from scripts.leg_folder import corrigendum_corrections, rdf_meta, title_date
    dump = Path(a.dump)
    if not dump.is_dir():
        print(f"[ERROR] no LEG_2026-10 folders at {dump}", file=sys.stderr)
        return 2

    def recorded_of(uuid, version):
        if (version or "").startswith("LEG_2026-10") and uuid and (dump / uuid).is_dir():
            return rdf_meta(dump, uuid)["date"]
        return None

    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, celex, uuid, date::text, title, corpus_version FROM eu_laws "
                               "WHERE coalesce(celex, '') <> '' ORDER BY id")).fetchall()
        db.rollback()
        recorded_of = functools.lru_cache(maxsize=None)(recorded_of)
        # only acts whose title and Cellar disagree can be moved by a corrigendum: their corrigenda, in one query
        disagree = [r[1] for r in rows if not re.search(r"R\(\d{2}\)$", r[1]) and title_date(r[4])
                    and (recorded_of(r[2], r[5]) or r[3]) != title_date(r[4])]
        corr = corrigendum_corrections(db, disagree, dump)
        live = fresh_recorded(rows, recorded_of, corr)
        changes, cellar_wrong = changes_for(rows, lambda u, v: live.get(u) or recorded_of(u, v), lambda c: corr.get(c, ()))
        print(f"[INFO] {len(rows)} laws read | to change: {len(changes)} "
              f"{dict(collections.Counter(c[4] for c in changes))} | stored right, Cellar wrong: {len(cellar_wrong)} "
              f"| title and Cellar disagree: {len(disagree)}, with a corrigendum's correction: {len(corr)}, "
              f"Cellar re-read: {len(live)}")
        for c in changes[:8]:
            print(f"[INFO]   e.g. {c[1]}: {c[2]} -> {c[3]} ({c[4]})")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0
        if a.backup and changes:
            path = BACKEND / f"data/backups/eu_laws_dates_before_{dt.datetime.now():%Y%m%d_%H%M}.json"
            path.parent.mkdir(parents=True, exist_ok=True)  # untracked: absent from a fresh checkout
            path.write_text(json.dumps({"columns": ["id", "celex", "date_before", "date_after", "kind"], "rows": changes,
                                        "cellar_wrong": {"columns": ["id", "celex", "date", "cellar"],
                                                         "rows": cellar_wrong},
                                        "restore": "set date back to date_before by id"}))
            print(f"[OK] backup of {len(changes)} rows -> {path.relative_to(BACKEND.parent)}")
        done = 0
        for j in range(0, len(changes), CHUNK):
            part = [(c[0], c[2], c[3]) for c in changes[j:j + CHUNK]]
            cur = db.connection().connection.cursor()
            got = execute_values(cur, UPDATE, part, template="(%s, %s, %s)", page_size=len(part), fetch=True)
            db.commit()
            done += len(got)
            time.sleep(0.2)
        print(f"[OK] written: {done} of {len(changes)} (a row another writer changed meanwhile is left)")
        return 0 if done == len(changes) else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
