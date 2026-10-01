#!/usr/bin/env python3.12
"""Read parliamentary-question text from the doceo page, not the EP API.

/api/v2/parliament/parliamentary-questions serves 101 of 7,940 rows with neither
question nor answer text. backfill_parl_question_text.py asks the EP Open Data API for
them and gets nothing: every row comes back `q=0c a=0c`, 0 filled, 8 failures on a
15-row test. That reads as "the text does not exist".

It exists. E-000613/2026 renders in full on its doceo page -- the question by Beatrice
Timgren (ECR), its three numbered sub-questions and the submission date, about 2,000
characters -- and all 101 rows already carry that URL. The EP API simply does not
expose the body for these; the published HTML does.

doceo sits behind a WAF that answers curl with 202 and nothing parseable, so the page
is fetched through Playwright. A 202 with an empty body is a blocked fetch, never an
empty document, and is retried rather than written.

Anything under MIN_CHARS is refused: a short response is how a challenge page gets
stored and still passes a non-null check.

    python3.12 scripts/fetch_parl_question_text_doceo.py --limit 5 --rehearse
    python3.12 scripts/fetch_parl_question_text_doceo.py --limit 120 --apply
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import sys
import time
from collections import Counter

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

MIN_CHARS = 300

PICK = text(
    """
    SELECT id, question_reference, source_url
      FROM parliamentary_questions
     WHERE coalesce(text_question, '') = '' AND coalesce(text_answer, '') = ''
       AND coalesce(source_url, '') <> ''
     ORDER BY submitted_date DESC NULLS LAST, id
     LIMIT :lim
    """
)

STORE = text(
    "UPDATE parliamentary_questions SET text_question = :t, last_updated = now() "
    "WHERE id = :rid AND coalesce(text_question, '') = ''"
)

STATE = text(
    """
    SELECT count(*) AS total,
           count(*) FILTER (WHERE coalesce(text_question, '') = ''
                              AND coalesce(text_answer, '') = '') AS no_text
      FROM parliamentary_questions
    """
)


def _browser():
    spec = importlib.util.spec_from_file_location(
        "waf_browser_fetcher", str(BACKEND / "services" / "scrapers" / "waf_browser_fetcher.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["waf_browser_fetcher"] = m
    spec.loader.exec_module(m)
    return m


def _database_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


# Trim the page furniture doceo wraps every document in, so what is stored is the
# question rather than the legal notice and the language picker.
_TAIL = re.compile(r"(Last updated:|Legal notice\s*-\s*Privacy policy).*$", re.S | re.I)


def _clean(body: str) -> str:
    return _TAIL.sub("", body).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args()

    engine = create_engine(_database_url())
    with engine.connect() as conn:
        before = conn.execute(STATE).one()
        rows = list(conn.execute(PICK, {"lim": args.limit}))
    print(f"[INFO] questions           : {before.total}")
    print(f"[INFO] with no text at all : {before.no_text}")
    print(f"[INFO] this run            : {len(rows)}")
    if args.rehearse:
        for r in rows[:5]:
            print(f"   {r.question_reference:<18} {r.source_url[-54:]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    browser = _browser()
    stored = blocked = short = 0
    why: Counter = Counter()
    chars = 0
    for i, r in enumerate(rows, 1):
        try:
            res = browser.fetch_one(r.source_url)
            body = _clean(res.text or "")
            status = res.nav_status
        except Exception as e:
            blocked += 1; why[type(e).__name__] += 1; continue
        if not body:
            # A 202 with nothing in it is the WAF, not an empty document.
            blocked += 1; why[f"blocked_{status}"] += 1; continue
        if len(body) < MIN_CHARS:
            short += 1; why[f"too_short_{len(body)}"] += 1; continue
        with engine.begin() as conn:
            conn.execute(STORE, {"t": body, "rid": r.id})
        stored += 1; chars += len(body)
        if i % 20 == 0:
            print(f"   ...{i}/{len(rows)} stored={stored} blocked={blocked} short={short}", flush=True)
        time.sleep(args.pause)

    with engine.connect() as conn:
        after = conn.execute(STATE).one()
    print(f"\n[INFO] stored  : {stored}" + (f"  (avg {chars // stored} chars)" if stored else ""))
    print(f"[INFO] blocked : {blocked}  (retry; not an absence)  {dict(why)}")
    print(f"[INFO] short   : {short}")
    print(f"[INFO] no text : {before.no_text} -> {after.no_text}")
    if rows and stored == 0:
        print("[ERROR] nothing stored; this run proves nothing about whether the text exists")
        return 1
    print("[OK] every stored body came from the question's own doceo page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
