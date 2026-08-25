#!/usr/bin/env python3.12
"""Repair social_accounts.handle rows that hold a URL path segment.

WHY (audit, 25 August 2026)

`_handle()` in services/social/eu_directory_loader took `segs[-1]` of the
account URL, so any URL ending in a VIEW of the account rather than the account
itself stored the view as the identity:

    https://www.youtube.com/user/EpinUk/featured        -> handle "featured"
    https://www.youtube.com/user/EuropeanUnionKosovo/videos -> handle "videos"
    https://x.com/<delegation>/photo                    -> handle "photo"

49 accounts were affected, 22 of them fetch-enabled. Nothing failed loudly:
fetching goes through `platform_account_id`, which was always correct, and
307 posts had been collected from these accounts. What broke was IDENTITY --
eight different accounts, including the European Parliament in the UK and an
MEP, all read as "@featured". Every surface keyed on handle (MEP Watch,
Stakeholder Mapping, the social API, any dedup) saw them as the same thing.

This script re-derives each handle from `account_url` using the FIXED
extractor, so the repair and the loader can never drift apart.

    python3.12 scripts/repair_social_handles.py            # dry run
    python3.12 scripts/repair_social_handles.py --apply

Exit codes: 0 clean, 1 if any row could not be repaired.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.social.eu_directory_loader import (  # noqa: E402
    _handle, _VIEW_SEGMENTS, _CONTAINER_SEGMENTS,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="persist the repairs")
    args = ap.parse_args()

    bad = sorted(_VIEW_SEGMENTS | _CONTAINER_SEGMENTS)
    db = SessionLocal()
    repaired = unresolved = 0
    try:
        # `blogs` rows are personal websites, not accounts: there is no handle
        # to recover. Deriving one produces nonsense -- an MEP's
        # deutsch.fidesz-eu.hu/hu/blog yields "hu", a locale segment presented
        # as an identity. Leave them alone rather than write a plausible wrong
        # value, which is the whole defect this script exists to undo.
        rows = db.execute(text("""
            SELECT id, entity_name, platform, handle, account_url
            FROM social_accounts
            WHERE handle IS NOT NULL AND lower(handle) = ANY(:bad)
              AND platform NOT IN ('blogs')
            ORDER BY platform, entity_name
        """), {"bad": bad}).fetchall()

        print(f"accounts with a view/container segment as handle: {len(rows)}")
        for r in rows:
            new = _handle(r.account_url or "")
            if not new or new.lower() in bad:
                # Say so rather than writing another wrong value. A NULL handle
                # is honest; a guessed one is the bug we are fixing.
                print(f"  [UNRESOLVED] {str(r.entity_name)[:34]:34} {r.platform:9} "
                      f"{r.handle!r} url={str(r.account_url)[:50]}")
                unresolved += 1
                continue
            print(f"  {str(r.entity_name)[:34]:34} {r.platform:9} {r.handle!r:12} -> {new!r}")
            if args.apply:
                db.execute(text("UPDATE social_accounts SET handle=:h, updated_at=now() "
                                "WHERE id=:i"), {"h": new, "i": r.id})
            repaired += 1

        if args.apply:
            db.commit()
        print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: repaired={repaired} "
              f"unresolved={unresolved}")
        if unresolved:
            print("Unresolved rows keep their current value; their account_url has no "
                  "identifiable segment. Fix the URL, not the handle.", file=sys.stderr)
    finally:
        db.close()

    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
