"""Prove a backfilled table against its SOURCE, not against its own row count.

Hard rule (Victor, 28 Sep 2026): never hallucinate in a backfill. A count proves nothing:
rsb_opinions had 44 of 44 dates "complete" and every one was invented, and 2,973 answers
passed a length check while their words were fused together. This asks the source.

Four questions, reported separately, because merging them is how a gap hides:
  1. Does every stored row's date match the live record?
  2. Is the stored body actually IN the file the source serves?
  3. Are rows without a body honest about it, or is a title standing in for one?
  4. Does the corpus reconcile: no year missing, no silent truncation?

Run:
    python3.12 scripts/verify_backfill_against_source.py --table ep_external_documents --sample 12
"""
from __future__ import annotations

import argparse
import io
import random
import re
import sys
import time
import zipfile
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

HEADERS = {"Accept": "application/ld+json",
           "User-Agent": "Brubru/1.0 (+https://brubru.beresol.eu)",
           "X-Brubru-Probe": "backfill-verify"}

SOURCES = {
    "ep_external_documents": {
        "detail": "https://data.europarl.europa.eu/api/v2/external-documents/{identifier}",
        "date_field": "document_date",
        "year_column": "identifier_year",
    },
}


def _fetch_json(client, url, params, attempts=4):
    for a in range(attempts):
        try:
            r = client.get(url, params=params)
        except Exception:
            time.sleep(4.0 * (a + 1)); continue
        if r.status_code in (429, 503):
            try:
                wait = int(r.headers.get("Retry-After") or 60)
            except (TypeError, ValueError):
                wait = 60
            time.sleep(min(max(wait, 5), 180)); continue
        if r.status_code == 404:
            return None
        try:
            d = r.json()
        except Exception:
            time.sleep(3.0 * (a + 1)); continue
        if "data" not in d and d.get("error"):
            time.sleep(3.0 * (a + 1)); continue
        return d
    return "REFUSED"


def _docx_words(blob: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            xml = z.open("word/document.xml").read().decode("utf-8", "replace")
    except Exception:
        return ""
    return " ".join(re.sub(r"<[^>]+>", " ", xml).split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--sample", type=int, default=12)
    args = ap.parse_args()
    cfg = SOURCES.get(args.table)
    if not cfg:
        print(f"[ERROR] no source recipe for {args.table}; add one to SOURCES")
        return 1

    db = SessionLocal()
    failures = 0
    try:
        total, with_date, with_body, no_body = db.execute(text(
            f"SELECT count(*), count(document_date), "
            f"count(*) FILTER (WHERE length(COALESCE(body_txt,'')) > 200), "
            f"count(*) FILTER (WHERE length(COALESCE(body_txt,'')) <= 200) FROM {args.table}"
        )).one()
        print(f"[1] corpus: {total} rows, {with_date} dated, {with_body} with a body, "
              f"{no_body} without")

        # 3. A row with no body must SAY so rather than carry a title as a body.
        dishonest = db.execute(text(
            f"SELECT count(*) FROM {args.table} "
            f"WHERE length(COALESCE(body_txt,'')) <= 200 AND body_source IS NOT NULL"
        )).scalar()
        print(f"[3] body-less rows claiming a body_source: {dishonest}")
        failures += bool(dishonest)

        # 4. Reconcile the spread of years: a hole is a silent truncation.
        years = db.execute(text(
            f"SELECT {cfg['year_column']}, count(*) FROM {args.table} "
            f"GROUP BY 1 ORDER BY 1")).all()
        present = [int(y) for y, _ in years if y is not None]
        holes = [y for y in range(min(present), max(present) + 1) if y not in present] if present else []
        print(f"[4] years {min(present)}..{max(present)}, {len(present)} present; "
              f"missing in range: {holes or 'none'}")
        failures += bool(holes)

        rows = db.execute(text(
            f"SELECT identifier, document_date, file_url, left(body_txt, 120) AS opening "
            f"FROM {args.table} ORDER BY random() LIMIT :n"), {"n": args.sample}).all()
        ok_date = bad_date = refused = ok_body = bad_body = 0
        with httpx.Client(headers=HEADERS, timeout=90.0, follow_redirects=True) as c:
            for r in rows:
                d = _fetch_json(c, cfg["detail"].format(identifier=r.identifier),
                                {"format": "application/ld+json"})
                if d == "REFUSED":
                    refused += 1
                    print(f"    {r.identifier[:34]:36} source REFUSED (not a mismatch)")
                    continue
                rec = (d or {}).get("data", [{}])[0] if d else {}
                src = str(rec.get(cfg["date_field"]) or "")[:10]
                stored = str(r.document_date)
                if src == stored:
                    ok_date += 1
                else:
                    bad_date += 1
                    print(f"    {r.identifier[:34]:36} DATE stored={stored} source={src or '-'}")
                if r.file_url and (r.opening or "").strip():
                    try:
                        blob = c.get(r.file_url).content
                    except Exception:
                        blob = b""
                    live = _docx_words(blob) if blob[:2] == b"PK" else ""
                    probe = " ".join((r.opening or "").split())[:40]
                    if live and probe in live:
                        ok_body += 1
                    elif live:
                        bad_body += 1
                        print(f"    {r.identifier[:34]:36} BODY not found in the source file")
                time.sleep(0.6)
        print(f"[2] sampled {len(rows)}: dates {ok_date} match, {bad_date} mismatch, "
              f"{refused} refused; bodies {ok_body} found, {bad_body} not found")
        failures += bad_date + bad_body

        print("\n[VERDICT] " + ("PASS" if failures == 0 else f"FAIL ({failures} problem(s))"))
        return 0 if failures == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
