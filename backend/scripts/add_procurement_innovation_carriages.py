#!/usr/bin/env python3.12
"""Add the two 9 September 2026 Commission proposals as legislative carriages.

WHY
---
/news on 10 September 2026 found that neither COM(2026) 590 (Public Procurement
Act) nor COM(2026) 567 (European Innovation Act) existed in
`legislative_carriages`, so My EU Bubble > My Tracked Files could not suggest
either -- on the day they were the largest single-market proposals of the week.

WHAT IS AND IS NOT VERIFIED
---------------------------
Every field written here comes from the PROPOSAL'S OWN COVER PAGE, read as PDF:

    COM(2026) 590 final  2026/0265 (COD)   Public Procurement Act
    COM(2026) 567 final  2026/0264 (COD)   European Innovation Act

`lead_committee` is left NULL ON PURPOSE. IMCO is widely expected for the
procurement file and its chair commented on 8 September, but that is press, not
OEIL, and OEIL is the source of truth for committee and rapporteur identity.
The EP website was down for maintenance when this was written, so it could not
be checked -- and an outage is not an answer. `legislative_carriages` already
carries a known defect of naming the wrong lead committee; guessing here would
add to it. The seeder matches on committee OR policy_areas, so these are
suggestable through policy_areas without inventing a committee.

CELEX is NOT derived from the procedure reference. They are independent
counters (memory/feedback_celex_vs_oeil.md).

Idempotent: re-running updates nothing and inserts nothing if the refs exist.
Usage:  python3.12 -m backend.scripts.add_procurement_innovation_carriages [--apply]
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

FILES = [
    dict(
        file_id="com-2026-590-public-procurement-act",
        oeil_procedure_ref="2026/0265(COD)",
        title=("Proposal for a Regulation on public contracts and concessions, repealing "
               "Directives 2014/23/EU, 2014/24/EU and 2014/25/EU (Public Procurement Act)"),
        short_title="Public Procurement Act",
        celex_numbers=["52026PC0590"],
        policy_areas=["Single Market", "Business and Industry", "Competition"],
        description=(
            "COM(2026) 590 final, adopted by the Commission on 9 September 2026. Replaces the "
            "three 2014 procurement directives with a single Regulation. R&D service contracts, "
            "including pre-commercial procurement, are excluded and regulated in the European "
            "Innovation Act (2026/0264(COD)) instead. Legal basis Article 114 TFEU."
        ),
    ),
    dict(
        file_id="com-2026-567-european-innovation-act",
        oeil_procedure_ref="2026/0264(COD)",
        title=("Proposal for a Regulation establishing a framework of measures for strengthening "
               "the Union innovation ecosystem and amending Regulation (EU) 2017/1001 "
               "(European Innovation Act)"),
        short_title="European Innovation Act",
        celex_numbers=["52026PC0567"],
        policy_areas=["Research and Innovation", "Single Market", "Business and Industry"],
        description=(
            "COM(2026) 567 final, adopted by the Commission on 9 September 2026. Three chapters: "
            "scope, common rules for R&D procurement including joint procurement, and tasks for "
            "EUIPO on IP valuation, an EU IP marketplace and IP-backed finance. Regulatory "
            "sandboxes are a SEPARATE proposal for a Council Recommendation, not part of this Act. "
            "Legal basis Article 114 TFEU."
        ),
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write; otherwise dry-run")
    args = ap.parse_args()

    db = SessionLocal()
    created = skipped = 0
    try:
        for spec in FILES:
            existing = (
                db.query(LegislativeCarriage)
                .filter(LegislativeCarriage.oeil_procedure_ref == spec["oeil_procedure_ref"])
                .first()
            )
            if existing:
                print(f"[skip]   {spec['oeil_procedure_ref']} already present ({existing.file_id})")
                skipped += 1
                continue
            print(f"[create] {spec['oeil_procedure_ref']}  {spec['short_title']}")
            if args.apply:
                db.add(LegislativeCarriage(
                    id=uuid.uuid4(),
                    source=CarriageSourceEnum.OEIL_DIRECT,
                    current_status=CarriageStatusEnum.TABLED,
                    lead_committee=None,   # deliberately unknown -- see module docstring
                    **spec,
                ))
            created += 1
        if args.apply and created:
            db.commit()
        print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: created={created} skipped={skipped}")
        # Count PERSISTED rows, never attempts.
        if args.apply:
            n = (db.query(LegislativeCarriage)
                 .filter(LegislativeCarriage.oeil_procedure_ref.in_(
                     [f["oeil_procedure_ref"] for f in FILES])).count())
            print(f"verified in database: {n}/2")
            return 0 if n == len(FILES) else 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
