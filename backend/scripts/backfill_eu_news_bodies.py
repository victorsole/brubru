#!/usr/bin/env python3.12
"""Compose body_txt / body_html / body_source for `eu_news_items`.

Why
---
`/api/v2/news/all` unions `economy_items` (agencies) with `eu_news_items`
(Commission, Parliament, Council, and any other body in `_INSTITUTIONAL_NEWS`).
The economy half carries real body columns; the institutional half had none, so the
endpoint served `body_txt = summary` and `body_html = NULL`. Measured 8 September
2026: `body_html` NULL on 100% of 10,143 rows, `body_txt` empty on 29%.

Two of the five mandatory datapoints, absent from half the corpus. See
`feedback_api_endpoint_pattern_contract`: structured data is not exempt, the body is
COMPOSED at backfill time, and `body_source` records how.

What it composes, and what it does NOT
--------------------------------------
It renders the fields the row actually holds -- title, summary, institution, date,
source URL -- into a readable body. It does NOT fetch the article and does NOT invent
prose. `body_source` states which shape was used so a consumer is never misled:

    composed:title+summary   title and summary both present
    composed:title           summary empty; body is the headline plus provenance

Fabricating an article body would be `feedback_backfill_no_hallucination`. Composing a
truthful rendering of known fields is the contract.

Usage
-----
    python3.12 -m backend.scripts.backfill_eu_news_bodies --dry-run
    python3.12 -m backend.scripts.backfill_eu_news_bodies --apply
    python3.12 -m backend.scripts.backfill_eu_news_bodies --apply --recompose

`--apply` only touches rows where `body_source IS NULL`, so it is idempotent and safe
to re-run. `--recompose` rebuilds every row, for when the template itself changes.

It reports rows PERSISTED, verified by re-reading the table after the commit, not rows
attempted. See `feedback_silent_failure_reports_success`.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_BACKEND = str(pathlib.Path(__file__).resolve().parents[1])
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

BATCH = 500


from services.news.body_composer import compose_news_body as compose  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--recompose", action="store_true",
                    help="Rebuild every row, not only the uncomposed ones.")
    args = ap.parse_args()

    where = "TRUE" if args.recompose else "body_source IS NULL"
    db = SessionLocal()
    try:
        before = db.execute(text(
            "SELECT count(*) AS total, "
            "count(*) FILTER (WHERE body_source IS NOT NULL) AS composed, "
            "count(*) FILTER (WHERE body_txt IS NOT NULL AND btrim(body_txt) <> '') AS with_txt, "
            "count(*) FILTER (WHERE body_html IS NOT NULL AND btrim(body_html) <> '') AS with_html "
            "FROM eu_news_items")).mappings().one()
        print(f"[INFO] before: {before['total']} rows | composed {before['composed']} | "
              f"body_txt {before['with_txt']} | body_html {before['with_html']}")

        rows = db.execute(text(
            f"SELECT id, title, summary, institution, news_date, source_url "
            f"FROM eu_news_items WHERE {where} ORDER BY created_at DESC")).mappings().all()
        print(f"[INFO] candidates: {len(rows)}")
        if not rows:
            print("[OK] nothing to do")
            return 0

        by_shape = {"composed:title+summary": 0, "composed:title": 0}
        payload = []
        for r in rows:
            btxt, bhtml, bsrc = compose(
                r["title"], r["summary"], r["institution"], r["news_date"], r["source_url"])
            by_shape[bsrc] += 1
            payload.append({"id": r["id"], "t": btxt, "h": bhtml, "s": bsrc})

        print(f"[INFO] shapes: {by_shape}")
        sample = payload[0]
        print("\n[SAMPLE body_txt]\n" + sample["t"][:400])
        print("\n[SAMPLE body_html]\n" + sample["h"][:400] + "\n")

        if args.dry_run:
            print("[DRY-RUN] nothing written")
            return 0

        written = 0
        for i in range(0, len(payload), BATCH):
            chunk = payload[i:i + BATCH]
            db.execute(text(
                "UPDATE eu_news_items SET body_txt = :t, body_html = :h, body_source = :s "
                "WHERE id = :id"), chunk)
            db.commit()
            written += len(chunk)
            print(f"[INFO] committed {written}/{len(payload)}")

        # Re-read AFTER the commit. Counting the UPDATE's own rowcount would report
        # attempts; this reports what the table actually holds.
        after = db.execute(text(
            "SELECT count(*) AS total, "
            "count(*) FILTER (WHERE body_source IS NOT NULL) AS composed, "
            "count(*) FILTER (WHERE body_txt IS NOT NULL AND btrim(body_txt) <> '') AS with_txt, "
            "count(*) FILTER (WHERE body_html IS NOT NULL AND btrim(body_html) <> '') AS with_html "
            "FROM eu_news_items")).mappings().one()
        print(f"[INFO] after : {after['total']} rows | composed {after['composed']} | "
              f"body_txt {after['with_txt']} | body_html {after['with_html']}")

        gained = after["composed"] - before["composed"]
        if args.recompose:
            ok = after["composed"] == after["total"]
        else:
            ok = gained == len(payload)
        if not ok:
            print(f"[ERROR] expected +{len(payload)} composed, persisted +{gained}")
            return 1
        if after["with_html"] != after["total"] or after["with_txt"] != after["total"]:
            print(f"[ERROR] body coverage incomplete: txt {after['with_txt']}, "
                  f"html {after['with_html']}, of {after['total']}")
            return 1
        print(f"[OK] {gained} rows composed and verified; "
              f"body_txt and body_html now non-empty on all {after['total']} rows")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
