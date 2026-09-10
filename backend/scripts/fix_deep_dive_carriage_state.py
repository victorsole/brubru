#!/usr/bin/env python3.12
"""D3 + D4 (10 September 2026): correct one carriage status, add one missing carriage.

D3 -- Critical Medicines Act `2025/0102(COD)` is marked COMPLETED.
It is not adopted. Evidence, from primary sources rather than status text:
  * its only CELEX is 52025PC0102, the PROPOSAL (sector 5, type PC);
  * no adopted act (3YYYY...) for it exists in `eu_laws`;
  * the Council's own outcome document ST-11059/26 of 30 June 2026 carries the
    final compromise as "REGULATION (EU) 2026/... of ..." -- number and date
    still blank -- annexed to the Presidency's letter to the chair of the EP
    public-health committee.
COREPER endorsed on 30 June 2026; formal adoption and OJ publication follow.
So the correct state is CLOSE_TO_ADOPTION. COMPLETED here means "committee stage
finished", and any surface reading it as "in force" would tell a subscriber a law
binds them when it does not.

D4 -- the Affordable Housing Act `2026/0268(COD)` has a deep-dive (built 9 Sep)
and no carriage, so My Tracked Files cannot offer it. Fields come from the
proposal itself, COM(2026) 599. `lead_committee` is left NULL: OEIL is the source
of truth for committee identity and the EP website was down for maintenance when
this ran. An outage is not an answer.

Idempotent. Usage:
    python3.12 -m backend.scripts.fix_deep_dive_carriage_state [--apply]
"""
import argparse
import pathlib
import sys
import uuid

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT + "/backend" not in sys.path:
    sys.path.insert(0, _REPO_ROOT + "/backend")

from core.database import SessionLocal  # noqa: E402
from models.legislative_train import (  # noqa: E402
    LegislativeCarriage, CarriageSourceEnum, CarriageStatusEnum,
)

CMA_REF = "2025/0102(COD)"
AHA = dict(
    file_id="com-2026-599-affordable-housing-act",
    oeil_procedure_ref="2026/0268(COD)",
    title=("Proposal for a Regulation on affordable housing, and the accompanying "
           "Commission Recommendation (Affordable Housing Act)"),
    short_title="Affordable Housing Act",
    celex_numbers=["52026PC0599"],
    policy_areas=["Regional Policy", "Employment and Social Affairs", "Single Market"],
    description=(
        "COM(2026) 599, adopted by the Commission on 9 September 2026. A Regulation "
        "plus a separate Commission Recommendation. Brubru deep-dive: "
        "https://brubru.beresol.eu/affordable-housing-act/index.html"
    ),
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    changed = 0
    try:
        # D3
        cma = (db.query(LegislativeCarriage)
               .filter(LegislativeCarriage.oeil_procedure_ref == CMA_REF).first())
        if cma is None:
            print(f"[warn] {CMA_REF} has no carriage")
        else:
            # UPPER-case the comparison. The first run of this script compared
            # against "COMPLETED" while the enum's VALUE is "completed", so it
            # printed "[ok] already completed" and changed nothing -- a check
            # that reported success for the exact state it existed to fix.
            cur = str(getattr(cma.current_status, "value", cma.current_status) or "").upper()
            adopted = [c for c in (cma.celex_numbers or []) if str(c).startswith("3")]
            if adopted:
                print(f"[skip] {CMA_REF} now holds an adopted CELEX {adopted}; "
                      "COMPLETED may be right. Re-check before changing.")
            elif cur == "COMPLETED":
                print(f"[fix ] {CMA_REF} COMPLETED -> CLOSE_TO_ADOPTION "
                      f"(celex={cma.celex_numbers}, no adopted act)")
                if args.apply:
                    cma.current_status = CarriageStatusEnum.CLOSE_TO_ADOPTION
                changed += 1
            elif cur == "CLOSE_TO_ADOPTION":
                print(f"[ok  ] {CMA_REF} already CLOSE_TO_ADOPTION")
            else:
                print(f"[warn] {CMA_REF} is {cur!r}, which is neither COMPLETED nor "
                      "CLOSE_TO_ADOPTION -- not touching it, but it needs a look.")

        # D4
        existing = (db.query(LegislativeCarriage)
                    .filter(LegislativeCarriage.oeil_procedure_ref == AHA["oeil_procedure_ref"])
                    .first())
        if existing:
            print(f"[skip] {AHA['oeil_procedure_ref']} already present ({existing.file_id})")
        else:
            print(f"[add ] {AHA['oeil_procedure_ref']}  {AHA['short_title']}")
            if args.apply:
                db.add(LegislativeCarriage(
                    id=uuid.uuid4(),
                    source=CarriageSourceEnum.OEIL_DIRECT,
                    current_status=CarriageStatusEnum.TABLED,
                    lead_committee=None,
                    **AHA,
                ))
            changed += 1

        if args.apply and changed:
            db.commit()

        print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: {changed} change(s)")
        if args.apply:
            # Count PERSISTED state, never attempts.
            c = (db.query(LegislativeCarriage)
                 .filter(LegislativeCarriage.oeil_procedure_ref == CMA_REF).first())
            a = (db.query(LegislativeCarriage)
                 .filter(LegislativeCarriage.oeil_procedure_ref == AHA["oeil_procedure_ref"]).first())
            st = str(getattr(c.current_status, "value", c.current_status) or "").upper() if c else None
            print(f"verified: {CMA_REF} status={st} | "
                  f"{AHA['oeil_procedure_ref']} present={a is not None}")
            return 0 if (st == "CLOSE_TO_ADOPTION" and a is not None) else 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
