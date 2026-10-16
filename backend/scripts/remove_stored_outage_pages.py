"""The Commission's outage page is not a document's text (16 Oct 2026).

"Server inaccessibility / bg български / Сървърът е временно недостъпен ... Försök igen
senare." was stored as the text of 12 EU GovTech items (economy_items) and as the text of an
attached document in 5 Have Your Say initiatives (public_consultations.full_description). The
page reader now refuses it (economy_common._ERROR_BODY_STRONG). Here the stored copies go: an
item's whole body (the API then composes it from title and summary, and the next sync may
read the real page), an initiative's attachment block only.

    python3.12 scripts/remove_stored_outage_pages.py            # dry run
    python3.12 scripts/remove_stored_outage_pages.py --apply
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from sqlalchemy import create_engine, text

# One attachment's label and the outage page that stands for its text.
_BLOCK = re.compile(r"(?:[^\n]{0,80}\((?:MAIN|ANNEX[^)]*)\):\s*)?Server inaccessibility\s+bg\s+български.*?"
                    r"Försök igen senare\.\s*", re.S)


def strip_outage(text_value: str | None) -> str | None:
    if not text_value:
        return text_value
    return re.sub(r"\n{3,}", "\n\n", _BLOCK.sub("", text_value)).strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        c.execute(text("SET statement_timeout = 0"))
        items = list(c.execute(text("SELECT id FROM economy_items WHERE body_code = 'eugovtech' AND body_txt LIKE '%Сървърът е временно недостъпен%'")))
        cons = list(c.execute(text("SELECT id, full_description FROM public_consultations "
                                   "WHERE full_description ILIKE '%Server inaccessibility%'")))
    plan = [(r.id, strip_outage(r.full_description)) for r in cons]
    print(f"[INFO] items whose body is the outage page: {len(items)}; initiatives with it in an attachment: {len(cons)}")
    for rid, new in plan:
        print(f"   initiative row {rid}: {len(new or '')} characters left")
    if not args.apply:
        print("[DRY RUN] nothing written")
        return 0
    with engine.begin() as c:
        c.execute(text("SET LOCAL statement_timeout = 0"))
        for r in items:
            c.execute(text("UPDATE economy_items SET body_txt = NULL, body_html = NULL, updated_at = now() WHERE id = :i"),
                      {"i": r.id})
        for rid, new in plan:
            c.execute(text("UPDATE public_consultations SET full_description = :d, last_updated = now() WHERE id = :i"),
                      {"d": new or None, "i": rid})
    print(f"[DONE] {len(items)} item bodies cleared, {len(plan)} attachment blocks removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
