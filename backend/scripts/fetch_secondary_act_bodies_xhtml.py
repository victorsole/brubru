#!/usr/bin/env python3.12
"""Fetch secondary-act text from Cellar as XHTML, not only as PDF.

backfill_secondary_acts_body.py asks Cellar for `application/pdf`. Run over the 229
bodyless delegated acts that carry a CELEX it wrote 73 and reported 156 as "no PDF",
which reads as "Cellar has no text for these".

It does. Those same CELEX return XHTML: 32016R1613 gives 49,180 bytes, 32016R2095
188,509, 32016R2072 201,200, 32017R0104 176,208 -- while each one's PDF 404s. Many
acts simply have no PDF manifestation, and asking for one format and treating its
absence as the document's absence is the same error as reading a single JSON field
and concluding the source publishes nothing.

So this asks for XHTML first and falls back to PDF, which is the order
fetch_eu_law_bodies.py already uses for eu_laws.

A body under MIN_CHARS is refused and left for the next run: a short response is how a
challenge page or an error stub gets stored and still passes a non-null check.

    python3.12 scripts/fetch_secondary_act_bodies_xhtml.py --act-type delegated --limit 20 --rehearse
    python3.12 scripts/fetch_secondary_act_bodies_xhtml.py --act-type delegated --limit 400 --apply
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

CELLAR = "https://publications.europa.eu/resource/celex/{celex}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
MIN_CHARS = 600

PICK = text(
    """
    SELECT id, celex FROM secondary_acts
     WHERE coalesce(text_body, '') = '' AND coalesce(celex, '') <> ''
       AND (:act_type = 'all' OR act_type::text = :act_type)
     ORDER BY celex
     LIMIT :lim
    """
)

STORE = text(
    """
    UPDATE secondary_acts
       SET text_body = :txt, body_html = COALESCE(NULLIF(body_html, ''), :html),
           body_fetched_at = now(), last_updated = now()
     WHERE id = :rid AND coalesce(text_body, '') = ''
    """
)

STATE = text(
    """
    SELECT count(*) AS total,
           count(*) FILTER (WHERE coalesce(text_body, '') = '') AS no_body
      FROM secondary_acts
     WHERE (:act_type = 'all' OR act_type::text = :act_type)
    """
)


def _database_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def _strip(raw: str) -> str:
    out = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    out = re.sub(r"<[^>]+>", " ", out)
    return re.sub(r"\s+", " ", out).strip()


def _fetch(celex: str, ctx: ssl.SSLContext):
    """(html, text) from Cellar, or a marker saying why not. XHTML first, then PDF."""
    last = "unknown"
    for accept in ("application/xhtml+xml, text/html", "application/pdf"):
        try:
            req = urllib.request.Request(
                CELLAR.format(celex=celex),
                headers={"Accept": accept, "Accept-Language": "eng", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            last = f"http_{e.code}"
            continue
        except Exception as e:
            last = type(e).__name__
            continue
        if accept.startswith("application/pdf"):
            try:
                import io
                from pypdf import PdfReader
                pages = PdfReader(io.BytesIO(raw)).pages
                txt = _strip(" ".join((p.extract_text() or "") for p in pages))
            except Exception as e:
                last = f"pdf_{type(e).__name__}"
                continue
            html = None
        else:
            html = raw.decode("utf-8", "ignore")
            txt = _strip(html)
            # Inline images can make one act 150 MB; that hung the write for hours
            # (see fetch_eu_law_bodies._clean_html). Store the markup that carries text.
            html = re.sub(r"<(script|style|svg|object|iframe|img)\b[^>]*?(/>|>.*?</\1>)", " ", html, flags=re.S | re.I)
            html = re.sub(r"\sstyle=\"[^\"]*\"", "", html, flags=re.I)
            if len(html) > 2_000_000:
                html = None
        if len(txt) >= MIN_CHARS:
            return html, txt
        last = f"too_short_{len(txt)}"
    return last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--act-type", choices=("delegated", "implementing", "guidance", "all"), default="all")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--pause", type=float, default=0.3)
    args = ap.parse_args()

    engine = create_engine(_database_url(), pool_pre_ping=True, pool_recycle=300,
                           connect_args={"keepalives": 1, "keepalives_idle": 20, "keepalives_interval": 10,
                                         "keepalives_count": 3, "connect_timeout": 20})
    with engine.connect() as conn:
        before = conn.execute(STATE, {"act_type": args.act_type}).one()
        rows = list(conn.execute(PICK, {"act_type": args.act_type, "lim": args.limit}))
    print(f"[INFO] {args.act_type}: {before.total} rows, {before.no_body} with no body")
    print(f"[INFO] with a CELEX to fetch, this run: {len(rows)}")
    if args.rehearse:
        print(f"[INFO] sample: {[r.celex for r in rows[:6]]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    ctx = ssl.create_default_context(cafile=certifi.where())
    stored = skipped = 0
    why: Counter = Counter()
    chars = 0
    for i, r in enumerate(rows, 1):
        got = _fetch(r.celex, ctx)
        if isinstance(got, str):
            skipped += 1
            why[got.split("_")[0] if got.startswith("too_short") else got] += 1
        else:
            html, txt = got
            with engine.begin() as conn:
                conn.execute(STORE, {"rid": r.id, "txt": txt, "html": html})
            stored += 1
            chars += len(txt)
        if i % 50 == 0:
            print(f"   ...{i}/{len(rows)} stored={stored} skipped={skipped}", flush=True)
        time.sleep(args.pause)

    with engine.connect() as conn:
        after = conn.execute(STATE, {"act_type": args.act_type}).one()
    print(f"\n[INFO] stored  : {stored}" + (f"  (avg {chars // stored} chars)" if stored else ""))
    print(f"[INFO] skipped : {skipped}  {dict(why)}")
    print(f"[INFO] no body : {before.no_body} -> {after.no_body}")
    if rows and stored == 0:
        print("[ERROR] nothing stored; Cellar is refusing us, which is a failure of this "
              "run and not an absence of text")
        return 1
    print("[OK] every stored body came from Cellar and passed the length floor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
