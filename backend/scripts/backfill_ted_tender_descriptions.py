#!/usr/bin/env python3.12
"""Give TED-sourced tenders the description TED publishes, from TED's own search API.

A full walk of /api/v2/funding/ft-calls-for-tenders (2,052 rows, 21 pages) found 1,139
bodies under 400 characters. 386 of them are TED notices stored with NO description at all,
so the API served a bare reference and title. TED's public search API returns the text:
00870071-2025 carries a lot description ("Lieferung und Inbetriebnahme von 25,00 Stueck
Untersuchungsliegen ...") and the buyer.

    python3.12 scripts/backfill_ted_tender_descriptions.py --limit 10 --rehearse
    python3.12 scripts/backfill_ted_tender_descriptions.py --limit 400 --apply

TED returns the publication number WITHOUT leading zeros ("870071-2025") while we store
"00870071-2025", so the match is made on the zero-stripped form; matching the stored string
would find nothing and read as "TED has no text for this".

The text is stored in the notice's own language, English if there is one, with detected_lang
set, which is how the other foreign-language rows are held; translation is a later step
(Tenderator translation is paused). Only an empty description is written.
"""
from __future__ import annotations

import argparse, json, pathlib, re, sys, time, urllib.error, urllib.request
from collections import Counter

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)
from sqlalchemy import create_engine, text  # noqa: E402

API = "https://api.ted.europa.eu/v3/notices/search"
FIELDS = ["publication-number", "description-proc", "description-lot", "buyer-name"]
ISO3 = {"eng": "en", "fra": "fr", "deu": "de", "spa": "es", "ita": "it", "nld": "nl", "pol": "pl",
        "por": "pt", "ces": "cs", "dan": "da", "ell": "el", "est": "et", "fin": "fi", "hrv": "hr",
        "hun": "hu", "lav": "lv", "lit": "lt", "mlt": "mt", "ron": "ro", "slk": "sk", "slv": "sl",
        "swe": "sv", "bul": "bg", "gle": "ga"}
MIN_CHARS = 40
MAX_CHARS = 8000

PICK = text("""SELECT id, tender_reference FROM ft_calls_for_tenders
                WHERE source_url LIKE '%ted.europa.eu%' AND coalesce(description,'')=''
                ORDER BY published_at DESC NULLS LAST, id LIMIT :lim""")
STORE = text("""UPDATE ft_calls_for_tenders SET description=:d, detected_lang=coalesce(detected_lang,:l),
                last_updated=now() WHERE id=:i AND coalesce(description,'')=''""")
GAP = text("""SELECT count(*) FROM ft_calls_for_tenders
               WHERE source_url LIKE '%ted.europa.eu%' AND coalesce(description,'')=''""")


def _db() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _pick(block):
    """(text, iso3) for one multilingual field: English if present, else the first language."""
    if not isinstance(block, dict) or not block:
        return None, None
    lang = "eng" if block.get("eng") else next(iter(block))
    vals = block.get(lang) or []
    return ("\n\n".join(v.strip() for v in vals if isinstance(v, str) and v.strip()) or None), lang


def _fetch(ref: str):
    num = re.sub(r"^0+", "", ref)               # TED drops the leading zeros
    body = json.dumps({"query": f"publication-number={num}", "fields": FIELDS, "limit": 1}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json",
                                 "Accept": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        return f"http_{e.code}", None
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, None
    n = (d.get("notices") or [None])[0]
    if not n:
        return "not_found", None
    proc, l1 = _pick(n.get("description-proc"))
    lot, l2 = _pick(n.get("description-lot"))
    parts = [x for x in (proc, lot) if x]
    out = "\n\n".join(dict.fromkeys(parts))[:MAX_CHARS]
    if len(out) < MIN_CHARS:
        return "no_text", None
    return out, ISO3.get(l1 or l2 or "", None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true"); g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=20); ap.add_argument("--pause", type=float, default=0.3)
    a = ap.parse_args()
    eng = create_engine(_db(), pool_pre_ping=True)
    with eng.connect() as c:
        before = c.execute(GAP).scalar_one(); rows = list(c.execute(PICK, {"lim": a.limit}))
    print(f"[INFO] TED tenders with no description: {before} | this run: {len(rows)}")
    if a.rehearse:
        print("[INFO] rehearsal only"); return 0
    stored = chars = 0; why: Counter = Counter()
    for i, r in enumerate(rows, 1):
        got, lang = _fetch(r.tender_reference)
        for wait in (8, 20, 45):
            # 429 is TED rate-limiting us, not a notice with no text: 161 of the first
            # run's misses were exactly that, and would have read as "TED has none".
            if got != "http_429":
                break
            time.sleep(wait)
            got, lang = _fetch(r.tender_reference)
        if lang is None and got in ("not_found", "no_text") or (lang is None and got.startswith(("http_",))) \
                or got in ("not_found", "no_text"):
            why[got] += 1
        elif got.startswith(("http_",)):
            why[got] += 1
        else:
            for n in range(4):
                try:
                    with eng.begin() as c:
                        c.execute(STORE, {"d": got, "l": lang, "i": r.id})
                    break
                except Exception:  # noqa: BLE001
                    eng.dispose(); time.sleep(2 * (n + 1))
            stored += 1; chars += len(got)
        if i % 100 == 0:
            print(f"   ...{i}/{len(rows)} stored={stored} {dict(why)}", flush=True)
        time.sleep(a.pause)
    with eng.connect() as c:
        after = c.execute(GAP).scalar_one()
    print(f"[INFO] stored {stored}" + (f" (avg {chars // stored} chars)" if stored else "")
          + f" | not stored {dict(why)} | gap {before} -> {after}")
    if rows and stored == 0:
        print("[ERROR] nothing stored; this run proves nothing"); return 1
    print("[OK] every description came from TED's own API"); return 0


if __name__ == "__main__":
    sys.exit(main())
