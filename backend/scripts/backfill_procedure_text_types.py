"""Each procedure's text_type follows its OEIL procedure type (16 Oct 2026).

/api/v2/legislative/oeil/procedures served text_type 'unknown' on 331 COD procedures (COD
is the ordinary legislative procedure) and 'legislative' on 63 NLE ones (NLE is OEIL's
"Non-legislative enactments"). The map is fixed in oeil_sync_service.py; this applies it to
the stored rows whose reference names a type. Document rows (COM, SWD) are left as they are.

    python3.12 scripts/backfill_procedure_text_types.py            # dry run
    python3.12 scripts/backfill_procedure_text_types.py --apply
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from services.scrapers.oeil_sync_service import text_type_for  # noqa: E402

ROWS = text("SELECT id::text AS id, oeil_procedure_ref AS ref, text_type::text AS tt FROM legislative_carriages "
            "WHERE oeil_procedure_ref ~ '\\([A-Z]{3}\\)\\s*$'")
STORE = text("UPDATE legislative_carriages SET text_type = :t, last_updated = now() WHERE id = CAST(:id AS uuid)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        rows = list(c.execute(ROWS))
    plan = []
    for r in rows:
        want = text_type_for(r.ref)
        if want is not None and (r.tt or "") != want.name:
            plan.append((r.id, r.ref, r.tt, want))
    print(f"[INFO] {len(rows)} procedures; {len(plan)} to change: "
          + str(dict(collections.Counter((r[1][-4:-1], (r[2] or '').lower(), r[3].value) for r in plan).most_common(12))))
    if not args.apply:
        print("[DRY RUN] nothing written")
        return 0
    with engine.begin() as c:
        for rid, _, _, want in plan:
            c.execute(STORE, {"id": rid, "t": want.name})
    print(f"[DONE] {len(plan)} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
