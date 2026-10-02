#!/usr/bin/env python3.12
"""Give register documents the CELEX their own record already states, once Cellar confirms it.

148 register documents had no body and no CELEX, so no fetcher could ask Cellar for
their text. The CELEX was in the row all along: SWD rows are titled "SWD document
52026SC0155", and some OJ rows hold the CELEX in `reference` (32026D2225), the same
wrong-column pattern backfill_commission_register_celex.py fixed for 742 rows.

A CELEX-shaped string is a claim, not an identifier. Each one is stored only after
Cellar answers for it (200, 300 or 303; a 404 is refused), and only into an empty
celex cell that no other row already holds. JOIN(2026) 12 style references are mapped
to 52026JC0012 and pass the same Cellar check, so an invented number cannot be stored.

    python3.12 scripts/backfill_register_celex_from_title.py --rehearse
    python3.12 scripts/backfill_register_celex_from_title.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

CELLAR = "https://publications.europa.eu/resource/celex/{c}"
CELEX = re.compile(r"\b([1-9][0-9]{4}[A-Z]{1,2}[0-9]{4,5})\b")
JOIN = re.compile(r"^JOIN\((\d{4})\)\s*(\d+)$")

PICK = text("""
    SELECT id, reference, title FROM commission_documents
     WHERE coalesce(text_body, '') = '' AND coalesce(celex, '') = ''""")
TAKEN = text("SELECT celex FROM commission_documents WHERE coalesce(celex, '') <> ''")
STORE = text("UPDATE commission_documents SET celex = :c, last_updated = now() "
             "WHERE id = :rid AND coalesce(celex, '') = ''")


def _db_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _candidate(reference: str, title: str) -> str | None:
    for s in (reference or "", title or ""):
        m = CELEX.search(s)
        if m:
            return m.group(1)
    m = JOIN.match((reference or "").strip())
    if m:
        return f"5{m.group(1)}JC{int(m.group(2)):04d}"
    return None


def _exists(celex: str, ctx) -> str:
    req = urllib.request.Request(CELLAR.format(c=celex),
                                 headers={"Accept": "application/pdf", "Accept-Language": "eng"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    try:
        with opener.open(req, timeout=45) as r:
            return str(r.status)
    except urllib.error.HTTPError as e:
        return str(e.code)
    except Exception as e:
        return type(e).__name__


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(_db_url(), pool_pre_ping=True)
    with engine.connect() as c:
        rows = list(c.execute(PICK))
        taken = {r[0] for r in c.execute(TAKEN)}
    print(f"[INFO] bodyless register rows with no CELEX: {len(rows)}")

    ctx = ssl.create_default_context(cafile=certifi.where())
    verdict: Counter = Counter()
    writes = []
    for r in rows:
        cand = _candidate(r.reference, r.title)
        if not cand:
            verdict["no CELEX stated"] += 1
            continue
        if cand in taken:
            verdict["held by another row"] += 1
            continue
        st = _exists(cand, ctx)
        if st in ("200", "300", "303"):
            writes.append({"rid": r.id, "c": cand})
            taken.add(cand)
            verdict["confirmed by Cellar"] += 1
        else:
            verdict[f"Cellar {st}"] += 1
        time.sleep(0.2)
    print(f"[INFO] {dict(verdict)}")
    if args.rehearse:
        print(f"[INFO] sample: {[w['c'] for w in writes[:6]]}")
        print("[INFO] rehearsal only, nothing written")
        return 0
    n = 0
    with engine.begin() as c:
        for w in writes:
            n += c.execute(STORE, w).rowcount
    print(f"[INFO] CELEX stored: {n}")
    if rows and n == 0:
        print("[ERROR] nothing stored; this run proves nothing")
        return 1
    print("[OK] every stored CELEX is stated by the row and confirmed by Cellar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
