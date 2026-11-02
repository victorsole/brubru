#!/usr/bin/env python3.12
"""Repair what EEAS rows serve (2 Nov 2026, Victor's go; register O72, O107, O136, O137, O138). From what is
stored, reading nothing from the site:

  the outage page      a body that is the Commission's outage page goes. The longer-body rule keeps each column
                       apart: where body_html still holds the real page the text is read back from it, where
                       the text is real only the html goes, otherwise both go NULL and the API composes the
                       body from the row's own fields until a read brings the page.
  the Share menu       "Share, Facebook, LinkedIn..." and its icons leave text and html (services.news.page_widgets).
  tender dates         a tender's document_date is the line under its title, or NULL (tender_page_date).
  HaDEA calls          a date ahead is an opening, not a publication: NULL.
  one F&T event        484084's public_url, the word "uri", becomes the link its own text gives.

A changed row's updated_date moves, as it should: what it serves changed.

    python3.12 scripts/repair_eeas_bodies_and_dates.py --plan plan.json        # dry run
    python3.12 scripts/repair_eeas_bodies_and_dates.py --apply --backup b.json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
from datetime import date, datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from services.funding.agency_status import deadline_in_text  # noqa: E402
from services.news.page_widgets import clean_html, clean_text  # noqa: E402
from services.scrapers.economy_common import extract_html, is_outage_page  # noqa: E402
from services.scrapers.economy_eeas import tender_page_date  # noqa: E402

_SHARE = re.compile(r"(?m)^\s*Facebook\s*\n\s*(?:LinkedIn|X|Twitter)\s*$")


def repaired(row: dict, today: date) -> dict:
    """The columns of one EEAS row that change, and their new values. Pure."""
    txt, htm = row.get("body_txt"), row.get("body_html")
    new_txt, new_htm = txt, htm
    if is_outage_page(txt):
        new_txt, new_htm = (None, None) if is_outage_page(htm) or not htm else extract_html(htm)
        if is_outage_page(new_txt):
            new_txt, new_htm = None, None
    else:
        if (txt and _SHARE.search(txt[:1000])) or (htm and "content-share" in htm):
            new_txt, new_htm = clean_text(txt) if txt else txt, clean_html(htm) if htm else htm
        if is_outage_page(htm):     # the text is real, only the html went: 6 topic pages
            new_htm = None
    out = {}
    if new_txt != txt:
        out["body_txt"] = new_txt
    if new_htm != htm:
        out["body_html"] = new_htm
    if row.get("item_type") == "tender":
        deadline = deadline_in_text(new_txt)[0] or row.get("deadline")
        doc = tender_page_date(new_txt, deadline, today)
        old = row.get("document_date")
        if (doc.date() if doc else None) != (old.date() if old else None):
            out["document_date"] = doc
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--plan", help="write what would change here")
    ap.add_argument("--backup", help="the rows as they are, written before any change (required with --apply)")
    args = ap.parse_args(argv)
    if args.apply and not args.backup:
        ap.error("--apply needs --backup")
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    today = datetime.now(timezone.utc).date()
    with engine.connect() as c:
        rows = [dict(r) for r in c.execute(text(
            "SELECT id, item_type, title, public_url, body_txt, body_html, document_date, deadline, creation_date "
            "FROM economy_items WHERE body_code = 'eeas'")).mappings()]
        hadea = [dict(r) for r in c.execute(text(
            "SELECT id, item_type, title, public_url, document_date FROM economy_items "
            "WHERE body_code = 'hadea' AND item_type = 'call' AND document_date > now()")).mappings()]
        event = c.execute(text("SELECT id, public_url, body_txt FROM economy_items WHERE id = 484084 AND public_url = 'uri'")).mappings().first()
    plan = {r["id"]: repaired(r, today) for r in rows}
    plan = {k: v for k, v in plan.items() if v}
    by_id = {r["id"]: r for r in rows}
    for r in hadea:
        plan[r["id"]] = {"document_date": None}
        by_id[r["id"]] = r
    if event:
        m = re.search(r"(?m)^Details: (https?://\S+)$", event["body_txt"] or "")
        if m:
            plan[event["id"]] = {"public_url": m.group(1)}
            by_id[event["id"]] = dict(event)
    print(f"[INFO] rows read {len(rows)}, to change {len(plan)}")
    print("[INFO] by column:", {k: sum(1 for v in plan.values() if k in v) for k in ("body_txt", "body_html", "document_date", "public_url")})
    print("[INFO] both bodies to NULL:", sum(1 for v in plan.values() if v.get("body_txt", 1) is None and v.get("body_html", 1) is None))
    if args.plan:
        pathlib.Path(args.plan).write_text(json.dumps(
            {str(k): {c: (val.isoformat() if hasattr(val, "isoformat") else val) for c, val in v.items()} for k, v in plan.items()},
            ensure_ascii=False), encoding="utf-8")
    if not args.apply:
        return 0
    pathlib.Path(args.backup).write_text(json.dumps(
        {str(k): {c: by_id[k].get(c) for c in plan[k]} | {"title": by_id[k].get("title")} for k in plan},
        ensure_ascii=False, default=str), encoding="utf-8")
    done = 0
    for row_id, change in plan.items():
        sets = ", ".join(f"{c} = :{c}" for c in change)
        with engine.begin() as c:
            c.execute(text(f"UPDATE economy_items SET {sets} WHERE id = :id"), {**change, "id": row_id})
        done += 1
        time.sleep(0.05)
    print(f"[OK] changed {done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
