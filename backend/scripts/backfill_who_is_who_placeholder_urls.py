#!/usr/bin/env python3.12
"""Clear the public_url of officials whose Whoiswho page does not exist.

GovClipping reported on 1 October 2026 that who-is-who URLs led to pages that do
not exist. The first fix pointed every official at their own Whoiswho person page
and was verified on 6 random officials, 6/6 returning 200. The sample never drew
one of the 600 rows whose person id is `UNDEFINED_<something>` -- the directory's
placeholder for a record with no published page -- so 600 of 18,377 officials
(3.3%) were left serving a public_url that 404s. Filling the column was mistaken
for delivering it.

Those are mostly agency staff (ENISA, EASA, CPVO, ACER, Frontex...) present in the
SPARQL directory but never published, and stripping the prefix reveals nothing:
both forms 404.

The organisation page was considered as a substitute and rejected. It resolves for
only 123 of the 600, and it describes a body, not the person the row is about --
the same error as the 404 it would replace. A client can see that an empty field is
empty; it cannot see that a 200 points at the wrong page.

    python3.12 scripts/backfill_who_is_who_placeholder_urls.py --rehearse
    python3.12 scripts/backfill_who_is_who_placeholder_urls.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text  # noqa: E402

PLACEHOLDER = "%UNDEFINED%"

COUNT_BAD = text(
    """
    SELECT count(*) FROM who_is_who_officials
     WHERE person_uri LIKE :ph AND coalesce(public_url, '') <> ''
    """
)

CLEAR = text(
    """
    UPDATE who_is_who_officials
       SET public_url = NULL
     WHERE person_uri LIKE :ph AND coalesce(public_url, '') <> ''
    """
)

# A real page must never be cleared by this job, so prove the shape of what is left.
COUNT_GOOD = text(
    """
    SELECT count(*) FROM who_is_who_officials
     WHERE person_uri NOT LIKE :ph AND coalesce(public_url, '') <> ''
    """
)


def _database_url() -> str:
    env = pathlib.Path(__file__).resolve().parents[1] / ".env"
    m = re.search(r"^DATABASE_URL=(.*)$", env.read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(_database_url())
    with engine.begin() as conn:
        bad_before = conn.execute(COUNT_BAD, {"ph": PLACEHOLDER}).scalar_one()
        good_before = conn.execute(COUNT_GOOD, {"ph": PLACEHOLDER}).scalar_one()
        print(f"[INFO] officials with a placeholder id serving a URL : {bad_before}")
        print(f"[INFO] officials with a real page (must not change)  : {good_before}")

        if args.rehearse:
            print("[INFO] rehearsal only, nothing written")
            return 0

        cleared = conn.execute(CLEAR, {"ph": PLACEHOLDER}).rowcount
        bad_after = conn.execute(COUNT_BAD, {"ph": PLACEHOLDER}).scalar_one()
        good_after = conn.execute(COUNT_GOOD, {"ph": PLACEHOLDER}).scalar_one()

    print(f"\n[INFO] cleared        : {cleared}")
    print(f"[INFO] placeholders   : {bad_before} -> {bad_after}")
    print(f"[INFO] real pages     : {good_before} -> {good_after}")
    if bad_after != 0:
        print(f"[ERROR] {bad_after} placeholder URLs still served")
        return 1
    if good_after != good_before:
        print(f"[ERROR] real pages changed by {good_after - good_before}; they must not")
        return 1
    print("[OK] no official now serves a URL that 404s; real pages untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
