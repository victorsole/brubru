#!/usr/bin/env python3.12
"""Read the call text the SEDIA search left out, from the portal's own topic page.

A full walk of /api/v2/funding/ft-calls-for-proposals (2,957 calls, 30 pages) found 1,236
with no body. 1,194 of them are closed calls. SEDIA's search record carries no description
for most older calls, which is where the ingest got its text, so the gap is a source quirk,
not an absence of text.

The portal serves each topic's own detail as JSON, and it has the text: 8 of 8 randomly
chosen empty closed calls returned 1,856 to 9,325 characters. The topic id must be
LOWERCASE in the URL (an uppercase id 404s, which reads as "no such topic").

    python3.12 scripts/backfill_ft_call_descriptions.py --limit 20 --rehearse
    python3.12 scripts/backfill_ft_call_descriptions.py --limit 1300 --apply

Only an empty description is written, so it can never shorten a body. The nightly ingest was
changed in the same commit so that the longer value wins, otherwise it would blank this on
its next run.
"""
from __future__ import annotations

import argparse, html, json, pathlib, re, sys, time, urllib.error, urllib.request
from collections import Counter

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)
from sqlalchemy import create_engine, text  # noqa: E402

DETAILS = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicDetails/{t}.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
MIN_CHARS = 200
MAX_CHARS = 8000          # the same cap the ingest applies

PICK = text("""SELECT topic_id FROM ft_calls_for_proposals
                WHERE coalesce(description,'')='' ORDER BY published_at DESC NULLS LAST, topic_id
                LIMIT :lim""")
STORE = text("""UPDATE ft_calls_for_proposals SET description=:d, last_updated=now()
                 WHERE topic_id=:t AND coalesce(description,'')=''""")
GAP = text("SELECT count(*) FROM ft_calls_for_proposals WHERE coalesce(description,'')=''")


def _db() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _strip(h: str) -> str:
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"</(p|li|h[1-6]|div|br)>|<br\s*/?>", "\n", h, flags=re.I)
    h = html.unescape(re.sub(r"<[^>]+>", " ", h))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", h)).strip()


def _fetch(topic: str):
    try:
        req = urllib.request.Request(DETAILS.format(t=topic.lower()),
                                     headers={"User-Agent": UA, "Accept": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())["TopicDetails"]
    except urllib.error.HTTPError as e:
        return f"http_{e.code}"
    except Exception as e:  # noqa: BLE001
        return type(e).__name__
    body = _strip(d.get("description") or "")
    if len(body) < MIN_CHARS:
        # Some topics publish no description at all (ISF-2024-TF2-AG-PROTECT-*: an
        # empty field in both the topic JSON and SEDIA). What the portal shows for them
        # is the topic's conditions and support information, which are the call's own
        # text, so serve those, labelled, rather than nothing.
        parts = [(lbl, _strip(d.get(k) or "")) for lbl, k in
                 (("Call", "callTitle"), ("Topic conditions", "conditions"),
                  ("Support information", "supportInfo"))]
        if sum(len(v) for lbl, v in parts if lbl != "Call") >= MIN_CHARS:
            body = "\n\n".join(f"{lbl}:\n{v}" for lbl, v in parts if v)
    return body[:MAX_CHARS] if len(body) >= MIN_CHARS else "too_short"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true"); g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=50); ap.add_argument("--pause", type=float, default=0.4)
    a = ap.parse_args()
    eng = create_engine(_db(), pool_pre_ping=True)
    with eng.connect() as c:
        before = c.execute(GAP).scalar_one(); rows = [r[0] for r in c.execute(PICK, {"lim": a.limit})]
    print(f"[INFO] calls with no description: {before} | this run: {len(rows)}")
    if a.rehearse:
        print("[INFO] rehearsal only"); return 0
    stored = 0; chars = 0; why: Counter = Counter()
    for i, t in enumerate(rows, 1):
        got = _fetch(t)
        if got.startswith(("http_", "too_short")) or (len(got) < MIN_CHARS):
            why[got if len(got) < 24 else "short"] += 1
        else:
            for n in range(4):
                try:
                    with eng.begin() as c:
                        c.execute(STORE, {"d": got, "t": t})
                    break
                except Exception:  # noqa: BLE001 -- pooler drop: reconnect and retry
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
    print("[OK] every description came from the portal's own topic page"); return 0


if __name__ == "__main__":
    sys.exit(main())
