#!/usr/bin/env python3.12
"""Read each EU-agency consultation's own page, so /commission/consultations serves a body.

The consultations endpoint serves Have Your Say initiatives AND 753 consultations by
EU agencies (EIOPA 257, BEREC 154, ACER 121, EASA 109, EBA 42, EMA 40, AMLA, ECHA, SRB,
ERA, ECB banking supervision). Their stored description is a status line such as
"Closed · 2020-10-01" and full_description is empty, so the body was a stub.

Every one of the 753 has its own page URL (none shared), and the page carries the
consultation's text: BEREC's report background, ACER's case description, AMLA's
target audience and scope. EMA links straight to the consultation PDF. ECHA answers
a plain request with 403, so those go through the headless-browser fetcher.

What may be stored is the point of the guards: the page's <main>/<article> only, with
navigation, headers, footers and forms removed; at least MIN_CHARS; and never a bot
challenge or an access-denied page. Only an empty full_description is written.

    python3.12 scripts/fetch_agency_consultation_text.py --limit 20 --rehearse
    python3.12 scripts/fetch_agency_consultation_text.py --limit 800 --apply
"""
from __future__ import annotations

import argparse
import html as _html
import importlib.util
import io
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

UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"),
      "Accept": "text/html,application/pdf"}
MIN_CHARS = 300
MAX_CHARS = 200_000
CHALLENGE = re.compile(r"just a moment|verify you are human|captcha|access denied|"
                       r"request unsuccessful|incapsula|enable javascript and cookies", re.I)

PICK = text("""
    SELECT id, source_body, portal_url FROM public_consultations
     WHERE source = 'agency' AND coalesce(full_description, '') = ''
       AND coalesce(portal_url, '') <> ''
     ORDER BY source_body, id
     LIMIT :lim""")
STORE = text("UPDATE public_consultations SET full_description = :t, last_updated = now() "
             "WHERE id = :rid AND coalesce(full_description, '') = ''")
GAP = text("SELECT count(*) FROM public_consultations "
           "WHERE source = 'agency' AND coalesce(full_description, '') = ''")


def _db_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _main_text(h: str) -> str:
    h = re.sub(r"<(script|style|nav|header|footer|aside|form|noscript|svg)\b[^>]*>.*?</\1>",
               " ", h, flags=re.S | re.I)
    m = (re.search(r"<main\b[^>]*>(.*?)</main>", h, flags=re.S | re.I)
         or re.search(r"<article\b[^>]*>(.*?)</article>", h, flags=re.S | re.I))
    h = m.group(1) if m else h
    h = re.sub(r"</(p|li|h[1-6]|div|tr|dd|dt)>|<br\s*/?>", "\n", h, flags=re.I)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", h))
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def _text_of(data: bytes) -> str:
    if data[:4] == b"%PDF":
        from pypdf import PdfReader
        pages = PdfReader(io.BytesIO(data)).pages
        return re.sub(r"[ \t]+", " ", "\n".join((pg.extract_text() or "") for pg in pages)).strip()
    return _main_text(data.decode("utf-8", "ignore"))


def _clean(t: str) -> str:
    """PDF extraction can emit NUL bytes and lone surrogates; Postgres refuses both, and
    one such row crashed a 1,194-row run (and, written in one transaction, a 753-row
    run). Drop them; they carry no text."""
    return t.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8")


def _judge(t: str) -> str | None:
    """None when t may be stored, else the reason it may not."""
    if len(t) < MIN_CHARS:
        return "too_short"
    if CHALLENGE.search(t[:2000]):
        return "challenge"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--pause", type=float, default=0.5)
    args = ap.parse_args()

    engine = create_engine(_db_url(), pool_pre_ping=True, pool_recycle=300)
    with engine.connect() as c:
        rows = list(c.execute(PICK, {"lim": args.limit}))
        before = c.execute(GAP).scalar_one()
    print(f"[INFO] agency consultations with no text: {before} | this run: {len(rows)}")

    ctx = ssl.create_default_context(cafile=certifi.where())
    got: dict = {}
    walled: list = []
    why: Counter = Counter()
    for r in rows:
        try:
            req = urllib.request.Request(r.portal_url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
                t = _text_of(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (202, 403, 429, 503):
                walled.append(r)
            else:
                why[f"http_{e.code}"] += 1
            continue
        except Exception as e:  # noqa: BLE001
            why[type(e).__name__] += 1
            continue
        bad = _judge(t)
        if bad == "challenge" or (bad == "too_short" and len(t) < 50):
            walled.append(r)       # a wall dressed as a 200: ask the browser
        elif bad:
            why[f"{r.source_body}:{bad}"] += 1
        else:
            got[r.id] = (r, t[:MAX_CHARS])
        time.sleep(args.pause)

    if walled:
        print(f"[INFO] {len(walled)} behind a wall; asking the headless browser")
        spec = importlib.util.spec_from_file_location(
            "waf_browser_fetcher", BACKEND / "services" / "scrapers" / "waf_browser_fetcher.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["waf_browser_fetcher"] = mod
        spec.loader.exec_module(mod)
        try:
            res = mod.fetch_bytes_isolated([r.portal_url for r in walled], timeout_s=1800)
        except Exception as e:  # noqa: BLE001 -- no fallback is not an empty document
            print(f"[WARN] browser fallback unavailable: {type(e).__name__}")
            res = {}
        for r in walled:
            st, body, err = res.get(r.portal_url, (None, b"", "not fetched"))
            if not body or (st and st >= 400):
                why[f"{r.source_body}:walled_{st or err}"] += 1
                continue
            t = _text_of(body)
            bad = _judge(t)
            if bad:
                why[f"{r.source_body}:browser_{bad}"] += 1
            else:
                got[r.id] = (r, t[:MAX_CHARS])

    per = Counter(r.source_body for r, _ in got.values())
    print(f"[INFO] text found: {len(got)}  {dict(per)}")
    print(f"[INFO] not stored: {dict(why)}")
    if args.rehearse:
        for r, t in list(got.values())[:6]:
            print(f"   {r.source_body:7} {len(t):6}  {t[:110]!r}")
        print("[INFO] rehearsal only, nothing written")
        return 0
    n = 0
    for rid, (r, t) in got.items():
        # One transaction per row: a single bad row must not take the other 700 with it.
        try:
            with engine.begin() as c:
                n += c.execute(STORE, {"t": _clean(t), "rid": rid}).rowcount
        except Exception as e:  # noqa: BLE001
            print(f"   [WARN] {r.source_body} {rid}: {type(e).__name__}")
    with engine.connect() as c:
        after = c.execute(GAP).scalar_one()
    print(f"[INFO] stored: {n} | no text {before} -> {after}")
    if rows and n == 0:
        print("[ERROR] nothing stored; this run proves nothing")
        return 1
    print("[OK] every stored text is the consultation's own page, past the guards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
