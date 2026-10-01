#!/usr/bin/env python3.12
"""Read each Have Your Say consultation's objective text from the Commission's own API.

A full walk of /api/v2/commission/consultations found body_txt at a median of 159
characters, with 1,580 of 1,581 bodies under 400. That is a title and a fragment, not
a body. `full_description` is NULL on all 4,880 rows, so the composer had nothing
fuller to offer.

The text exists and is published, in the Commission's own JSON API rather than on the
page. Three fields carry it and which one is filled depends on the initiative: a
publication's `consultationObjective` (1,663 characters on the anti-money-laundering
action plan, against the 137 we stored), the `dossierSummary`, and the English
SUMMARY entry in `initiativeTranslations`. The longest wins.

Taking only the first found it on 1 of 30 rows, which read as "the source publishes
nothing" -- and was wrong: the very same payload held a 496-character dossierSummary.
The instrument was at fault, not the source.

    GET /info/law/better-regulation/brpapi/groupInitiatives/{initiative_id}?language=EN

The initiative id is already in the portal_url we hold
(.../initiatives/12176-action-plan-...), so nothing is guessed or searched for.

An initiative has several publications -- a roadmap, the public consultation, the
adopted act -- and only some carry an objective. The LONGEST is taken, because the
public consultation's objective is the substantive one and a roadmap's is usually
absent. A consultation whose API record carries no objective at all is left alone:
many are upcoming, and their page genuinely says only "Feedback: Upcoming". An empty
field is honest; the page's navigation furniture dressed up as a body is not.

Bounded and resumable, unfetched first.

    python3.12 scripts/fetch_consultation_objectives.py --limit 20 --rehearse
    python3.12 scripts/fetch_consultation_objectives.py --limit 1000 --apply
"""
from __future__ import annotations

import argparse
import json
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

API = ("https://ec.europa.eu/info/law/better-regulation/brpapi/"
       "groupInitiatives/{iid}?language=EN")
HEADERS = {"Accept": "application/json",
           "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
# The id is the digits immediately after /initiatives/ in the portal URL.
_IID = re.compile(r"/initiatives/(\d+)[-/]")
# Below this it is a label, not an objective. The stored descriptions average 132
# characters, so anything shorter is no improvement on what we already serve.
MIN_CHARS = 200

PICK = text(
    """
    SELECT id, portal_url, coalesce(length(description), 0) AS desc_len
      FROM public_consultations
     WHERE coalesce(full_description, '') = ''
       AND portal_url LIKE '%%ec.europa.eu%%/initiatives/%%'
     ORDER BY id
     LIMIT :lim
    """
)

STORE = text(
    "UPDATE public_consultations SET full_description = :t, last_updated = now() "
    "WHERE id = :rid AND coalesce(full_description, '') = ''"
)

PROGRESS = text(
    """
    SELECT count(*) AS total,
           count(*) FILTER (WHERE coalesce(full_description, '') <> '') AS done,
           coalesce(round(avg(length(full_description))
                    FILTER (WHERE full_description IS NOT NULL)), 0) AS avg_len
      FROM public_consultations
     WHERE portal_url LIKE '%%ec.europa.eu%%/initiatives/%%'
    """
)


def _database_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def _objective(iid: str, ctx: ssl.SSLContext) -> str | None | str:
    """The longest consultationObjective across the initiative's publications."""
    try:
        req = urllib.request.Request(API.format(iid=iid), headers=HEADERS)
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            payload = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return f"http_{e.code}"
    except Exception as e:
        return type(e).__name__

    # Three places carry substantive text, and which one is populated depends on the
    # kind of initiative. Taking only consultationObjective found it on 1 of 30 rows,
    # and reading that as "the source publishes nothing" would have been wrong: the
    # same payload carried a 496-character dossierSummary and a 508-character English
    # SUMMARY translation. The longest of the three wins.
    candidates = []

    # 1. The public consultation's own objective, where there is a public consultation.
    for pub in (payload.get("publications") or []):
        obj = (pub.get("consultationObjective") or "").strip()
        if obj:
            candidates.append(obj)

    # 2. The dossier summary, present on most initiatives.
    ds = (payload.get("dossierSummary") or "").strip()
    if ds:
        candidates.append(ds)

    # 3. The English SUMMARY translation. The language key is `language`, not
    #    `languageCode`, and there is no "ENG": reading the wrong key returns zero EN
    #    entries out of 48 and looks exactly like a source that publishes no English.
    for t in (payload.get("initiativeTranslations") or []):
        if str(t.get("field", "")).upper() == "SUMMARY" and str(t.get("language", "")).upper() == "EN":
            v = (t.get("value") or "").strip()
            if v:
                candidates.append(v)

    best = max(candidates, key=len) if candidates else ""
    if len(best) < MIN_CHARS:
        return None          # published nothing substantive; leave the row alone
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--pause", type=float, default=0.4)
    args = ap.parse_args()

    engine = create_engine(_database_url())
    with engine.connect() as conn:
        before = conn.execute(PROGRESS).one()
        rows = list(conn.execute(PICK, {"lim": args.limit}))
    print(f"[INFO] Have Your Say consultations : {before.total}")
    print(f"[INFO] already have an objective   : {before.done}  (avg {before.avg_len} chars)")
    print(f"[INFO] this run                    : {len(rows)}")
    if args.rehearse:
        for r in rows[:5]:
            m = _IID.search(r.portal_url or "")
            print(f"   id={m.group(1) if m else '(no id in url)':<8} stored_desc={r.desc_len:<5} {r.portal_url[-58:]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    ctx = ssl.create_default_context(cafile=certifi.where())
    stored = skipped = failed = 0
    why: Counter = Counter()
    total_chars = 0

    for i, r in enumerate(rows, 1):
        m = _IID.search(r.portal_url or "")
        if not m:
            skipped += 1; why["no id in url"] += 1; continue
        got = _objective(m.group(1), ctx)
        if got is None:
            skipped += 1; why["source publishes no objective"] += 1
        elif isinstance(got, str) and got.startswith(("http_",)) or (isinstance(got, str) and len(got) < MIN_CHARS):
            failed += 1; why[got if len(got) < 40 else "short"] += 1
        else:
            with engine.begin() as conn:
                conn.execute(STORE, {"t": got, "rid": r.id})
            stored += 1; total_chars += len(got)
        if i % 50 == 0:
            print(f"   ...{i}/{len(rows)}  stored={stored} skipped={skipped} failed={failed}", flush=True)
        time.sleep(args.pause)

    with engine.connect() as conn:
        after = conn.execute(PROGRESS).one()
    print(f"\n[INFO] stored  : {stored}" + (f"  (avg {total_chars // stored} chars)" if stored else ""))
    print(f"[INFO] skipped : {skipped}  {dict(why)}")
    print(f"[INFO] failed  : {failed}")
    print(f"[INFO] coverage: {before.done} -> {after.done} of {after.total}")
    if rows and stored == 0 and failed >= len(rows) // 2:
        print("[ERROR] nothing stored and most calls failed; the API is refusing us, "
              "which is a failure of this run, not an absence of text")
        return 1
    print("[OK] every stored objective came from the Commission's own API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
