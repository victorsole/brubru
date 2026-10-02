#!/usr/bin/env python3.12
"""Fetch the text of register documents whose CELEX is not in eu_laws, straight from Cellar.

fill_register_bodies_from_laws.py copies a body from eu_laws, so it can only fill a
register document whose act eu_laws holds. After the eu_laws drain finished, 460
register rows still had no body although each carries a CELEX that Cellar serves: 234
Commission proposals (52026PC0314: XHTML 404, PDF 303) and 226 OJ acts that eu_laws
never ingested (32026D03350: XHTML 303). Five-digit act numbers are real CELEX, not
padding: 32026D3350 is a 404.

The fetch is fetch_eu_law_bodies._fetch, imported rather than copied, so there is one
parser: XHTML first, PDF on a 404, the 600-character floor, and the HTML cleaner that
stops a 150 MB inline-image page from hanging the write.

Only an empty text_body is written.

    python3.12 scripts/fetch_register_bodies_from_cellar.py --limit 20 --rehearse
    python3.12 scripts/fetch_register_bodies_from_cellar.py --limit 1000 --apply
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import ssl
import sys
import time
from collections import Counter

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "fetch_eu_law_bodies", BACKEND / "scripts" / "fetch_eu_law_bodies.py")
_laws = importlib.util.module_from_spec(_spec)
sys.modules["fetch_eu_law_bodies"] = _laws
_spec.loader.exec_module(_laws)

PICK = text("""
    SELECT id, celex FROM commission_documents
     WHERE coalesce(text_body, '') = '' AND coalesce(celex, '') <> ''
     ORDER BY celex
     LIMIT :lim""")
STORE = text("""
    UPDATE commission_documents
       SET text_body = :txt, body_html = COALESCE(NULLIF(body_html, ''), :html), last_updated = now()
     WHERE id = :rid AND coalesce(text_body, '') = ''""")
GAP = text("SELECT count(*) FROM commission_documents WHERE coalesce(text_body, '') = ''")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--pause", type=float, default=0.3)
    args = ap.parse_args()

    engine = create_engine(
        _laws._database_url(), pool_pre_ping=True, pool_recycle=300,
        connect_args={"keepalives": 1, "keepalives_idle": 20, "keepalives_interval": 10,
                      "keepalives_count": 3, "connect_timeout": 20})
    with engine.connect() as c:
        rows = list(c.execute(PICK, {"lim": args.limit}))
        before = c.execute(GAP).scalar_one()
    print(f"[INFO] register rows with no body: {before}  (with a CELEX, this run: {len(rows)})")
    if args.rehearse:
        print(f"[INFO] sample: {[r.celex for r in rows[:6]]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    ctx = ssl.create_default_context(cafile=certifi.where())
    stored = 0
    why: Counter = Counter()
    for i, r in enumerate(rows, 1):
        got = _laws._fetch(r.celex, ctx)
        if isinstance(got, str):
            why[got.split("_")[0] if got.startswith("too_short") else got] += 1
        else:
            html, txt = got
            with engine.begin() as c:
                stored += c.execute(STORE, {"rid": r.id, "txt": txt, "html": html}).rowcount
        if i % 50 == 0:
            print(f"   ...{i}/{len(rows)} stored={stored} skipped={sum(why.values())}", flush=True)
        time.sleep(args.pause)

    with engine.connect() as c:
        after = c.execute(GAP).scalar_one()
    print(f"[INFO] stored  : {stored}")
    print(f"[INFO] skipped : {sum(why.values())}  {dict(why)}")
    print(f"[INFO] no body : {before} -> {after}")
    if rows and stored == 0:
        print("[ERROR] nothing stored; Cellar refused us, which is not an absence of text")
        return 1
    print("[OK] every stored body came from Cellar and passed the length floor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
