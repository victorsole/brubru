"""
Rebuild funding_org_identities (migration 314): one PIC for each VAT number the CORDIS consortia show.

/funding/partners puts a Financial Transparency System beneficiary (no PIC) under the PIC of the
CORDIS organisation with the same VAT number. The pairing is read from ft_funded_projects'
consortia, inside the database (nothing is downloaded): a VAT number seen with more than one PIC is
ambiguous and left out, so that beneficiary stands under its VAT number instead, unless one PIC
holds at least 90% of that VAT number's memberships (CSIC: 999991722 on 2,523, one of its institutes'
own PIC on 1; under the strict rule CSIC's 270 FTS payments joined nothing, 26 Oct 2026).

Runs in the weekly tier after the funded-project loaders (api/cron.py). The tier records this job's
run; the script records none itself.

Run: python3.12 -m scripts.refresh_org_identities [--apply]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

PAIRS = """
WITH pairs AS (
    SELECT upper(regexp_replace(o->>'vat', '[^A-Za-z0-9]', '', 'g')) AS vat_key, o->>'pic' AS pic,
           o->>'name' AS name, o->>'country' AS country
      FROM ft_funded_projects p, jsonb_array_elements(p.organisations) o
     WHERE p.is_test = false AND coalesce(o->>'pic', '') <> '' AND coalesce(o->>'vat', '') <> ''
), per_pic AS (
    SELECT vat_key, pic, count(*) AS n, mode() WITHIN GROUP (ORDER BY name) AS name,
           mode() WITHIN GROUP (ORDER BY country) AS country
      FROM pairs WHERE vat_key <> '' GROUP BY vat_key, pic
), ranked AS (
    SELECT per_pic.*, sum(n) OVER (PARTITION BY vat_key) AS projects,
           row_number() OVER (PARTITION BY vat_key ORDER BY n DESC, pic) AS rk
      FROM per_pic
)
SELECT vat_key, pic, name, country, projects, (n >= 0.9 * projects) AS clear FROM ranked WHERE rk = 1
"""
UPSERT = f"""
WITH agg AS ({PAIRS})
INSERT INTO funding_org_identities (vat_key, pic, name, country, projects)
SELECT vat_key, pic, name, country, projects FROM agg WHERE clear
ON CONFLICT (vat_key) DO UPDATE SET pic = EXCLUDED.pic, name = EXCLUDED.name, country = EXCLUDED.country,
    projects = EXCLUDED.projects, scraped_at = now()
"""
STALE = f"""
WITH agg AS ({PAIRS})
DELETE FROM funding_org_identities f
 WHERE NOT EXISTS (SELECT 1 FROM agg WHERE agg.vat_key = f.vat_key AND agg.clear)
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true", help="Write (default: dry run).")
    args = ap.parse_args(argv)
    db = SessionLocal()
    try:
        counts = db.execute(text(f"SELECT count(*) FILTER (WHERE clear), count(*) FILTER (WHERE NOT clear) FROM ({PAIRS}) a")).one()
        single, ambiguous = counts
        if args.apply:
            db.execute(text("SET LOCAL statement_timeout = 0"))
            db.execute(text(UPSERT))
            removed = db.execute(text(STALE)).rowcount
            db.commit()
        else:
            removed = 0
    finally:
        db.close()
    print(f"[{'OK' if args.apply else 'DRY-RUN'}] {single} VAT number(s) paired with a PIC "
          f"{'held' if args.apply else 'to hold'}; {ambiguous} with no PIC holding 90% left out; {removed} stale removed")
    if not single:
        print("[ERROR] no VAT number paired with a PIC: the consortia carry no PIC yet")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
