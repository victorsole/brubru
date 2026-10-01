#!/usr/bin/env python3.12
"""Read each law's full text from Cellar and store it, so /laws can serve a body.

GovClipping walked /api/v2/legislative/eur-lex/laws and found body_txt and body_html
null on all 17,947 rows of their backfill window. The list pointed at
/laws/{celex}/text, which fetches the act live from Cellar per call: workable for one
act, impossible for a list, since a 100-row page would be 100 live fetches.

Cellar is the source, never EUR-Lex: the EUR-Lex front end sits behind a WAF that
answers 202 with nothing parseable, while Cellar serves the XHTML directly.

What may be stored as a body is the point of the length floor. A short response is
how a challenge page, an error stub or a bare nav fragment gets written and still
reads as "filled" on a non-null check. Anything under MIN_CHARS is refused and left
for the next run, and coverage is reported on the LENGTH distribution.

Bounded and resumable: --limit rows per run, unfetched first then stalest, so a
30,531-row corpus is drained over repeated runs rather than one fragile job.

    python3.12 scripts/fetch_eu_law_bodies.py --limit 20 --rehearse
    python3.12 scripts/fetch_eu_law_bodies.py --limit 2000 --apply
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
_REPO_ROOT = str(BACKEND.parent)
for p in (_REPO_ROOT, str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

CELLAR = "https://publications.europa.eu/resource/celex/{celex}"
HEADERS = {"Accept": "application/xhtml+xml, text/html", "Accept-Language": "eng"}
# An act shorter than this is not an act. The real floor observed on Cellar is ~10 KB
# of XHTML for the smallest implementing decisions; 600 characters of stripped text
# is comfortably below any genuine act and comfortably above a challenge or error page.
MIN_CHARS = 600

PICK = text(
    """
    SELECT id, celex FROM eu_laws
     WHERE celex IS NOT NULL AND celex <> '' AND body_fetched_at IS NULL
     ORDER BY celex
     LIMIT :lim
    """
)

STORE = text(
    """
    UPDATE eu_laws
       SET body_html = :html, body_txt = :txt, body_chars = :n, body_fetched_at = now()
     WHERE id = :rid
    """
)

PROGRESS = text(
    """
    SELECT count(*) AS total,
           count(*) FILTER (WHERE body_fetched_at IS NOT NULL) AS fetched,
           count(*) FILTER (WHERE coalesce(body_chars, 0) >= :floor) AS real_bodies,
           coalesce(round(avg(body_chars) FILTER (WHERE body_chars > 0)), 0) AS avg_chars
      FROM eu_laws
     WHERE celex IS NOT NULL AND celex <> ''
    """
)


def _database_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def _strip(raw: str) -> str:
    out = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    out = re.sub(r"<[^>]+>", " ", out)
    return re.sub(r"\s+", " ", out).strip()


def _fetch(celex: str, ctx: ssl.SSLContext) -> tuple[str, str] | str:
    """The act's XHTML and text, or a marker string saying why not."""
    try:
        req = urllib.request.Request(CELLAR.format(celex=celex), headers=HEADERS)
        with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
            raw = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return f"http_{e.code}"
    except Exception as e:
        return type(e).__name__
    if not raw:
        return "empty"
    txt = _strip(raw)
    if len(txt) < MIN_CHARS:
        # Not an act: a challenge, a stub or a nav fragment. Never stored.
        return f"too_short_{len(txt)}"
    return raw, txt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--pause", type=float, default=0.3)
    args = ap.parse_args()

    engine = create_engine(_database_url())
    with engine.connect() as conn:
        before = conn.execute(PROGRESS, {"floor": MIN_CHARS}).one()
        rows = list(conn.execute(PICK, {"lim": args.limit}))

    print(f"[INFO] laws with a CELEX : {before.total}")
    print(f"[INFO] already fetched   : {before.fetched}  (real bodies {before.real_bodies}, avg {before.avg_chars} chars)")
    print(f"[INFO] this run          : {len(rows)}")
    if args.rehearse:
        print(f"[INFO] sample: {[r.celex for r in rows[:6]]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    ctx = ssl.create_default_context(cafile=certifi.where())
    stored = skipped = 0
    why: Counter = Counter()

    for i, r in enumerate(rows, 1):
        got = _fetch(r.celex, ctx)
        if isinstance(got, str):
            skipped += 1
            why[got.split("_")[0] if got.startswith("too_short") else got] += 1
        else:
            raw, txt = got
            with engine.begin() as conn:
                conn.execute(STORE, {"rid": r.id, "html": raw, "txt": txt,
                                     "n": len(txt)})
            stored += 1
        if i % 100 == 0:
            print(f"   ...{i}/{len(rows)}  stored={stored} skipped={skipped}", flush=True)
        time.sleep(args.pause)

    with engine.connect() as conn:
        after = conn.execute(PROGRESS, {"floor": MIN_CHARS}).one()

    print(f"\n[INFO] stored   : {stored}")
    print(f"[INFO] skipped  : {skipped}  {dict(why)}")
    print(f"[INFO] fetched  : {before.fetched} -> {after.fetched} of {after.total}")
    print(f"[INFO] real bodies : {after.real_bodies}   avg {after.avg_chars} chars")
    print(f"[INFO] remaining   : {after.total - after.fetched}")

    if stored == 0 and rows:
        print("[ERROR] not one body was stored; Cellar is refusing us, which is a "
              "failure of this run, not an absence of texts")
        return 1
    if skipped > stored:
        print(f"[ERROR] {skipped} skipped against {stored} stored: this run's picture "
              f"is not trustworthy, re-run with a larger --pause")
        return 1
    print("[OK] every stored body is a real act text, measured by length")
    return 0


if __name__ == "__main__":
    sys.exit(main())
