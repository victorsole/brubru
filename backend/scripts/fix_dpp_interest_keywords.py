"""Repair the keyword set of the ecodesign / digital-product-passport interest.

When the interest was created it was given keywords that are not about the
digital product passport at all. Measured against the live corpus of 16,401
consultations, news items and carriages:

    delegated act        60 claims,  3 on topic   ( 5%)
    registry             25 claims,  4 on topic   (16%)
    durability            9 claims,  1 on topic   -- seven are Euro 7 vehicle
                                                     emissions and battery
                                                     type-approval
    harmonised standard   4 claims,  1 on topic   -- three are medical devices
    unique identifier     1 claim,   0 on topic

"delegated act" is the most generic phrase in EU law: every policy area has
them. It tagged four EIOPA insurance surveys as digital-product-passport work,
and one of those was the single open consultation on the client's Overview
cockpit, where a tile promised her a consultation about insurance disclosures
under the Taxonomy Delegated Act as something she should respond to.

Each noisy keyword is replaced by the qualified form that keeps the true
positives:

    delegated act        -> espr delegated act, ecodesign delegated act
    registry             -> product passport registry
    unique identifier    -> unique registration identifier
    durability           -> product durability
    harmonised standard  -> dropped; "digital product passport" already matches
                            the harmonised-standards Decision, whose own title
                            says "harmonised standards for digital product
                            passports"

Then re-runs the classifier over every row the bad keywords touched, so the
mis-tagged rows lose the interest instead of keeping it until the next sync.

The lesson generalises: a keyword for a narrow regime must not be a phrase the
whole Official Journal uses.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

TAXONOMY = project_root / "backend/knowledge_base/policy_taxonomy.json"
LEAF = "Ecodesign of sustainable products / Digital product passport"

REMOVE = ["delegated act", "registry", "unique identifier", "durability",
          "harmonised standard"]
ADD = ["espr delegated act", "ecodesign delegated act", "product passport registry",
       "unique registration identifier", "product durability"]

# Rows that must still carry the interest after the change. If a repair makes
# the regime's own acts invisible it has traded one defect for a worse one.
MUST_STILL_MATCH = [
    "Commission Implementing Decision (EU) 2026/1736 of 14 July 2026 on harmonised "
    "standards for digital product passports drafted in support of Regulation (EU) 2024/1781",
    "Commission Implementing Regulation (EU) 2026/1778 laying down the implementation "
    "arrangements for the digital product passport registry",
    "Regulation (EU) 2024/1781 establishing a framework for the setting of ecodesign "
    "requirements for sustainable products",
    "Ecodesign requirements for apparel and footwear textiles",
    "Union-wide end-of-waste criteria for textile waste",
]

MUST_NOT_MATCH = [
    "Technical advice on possible delegated acts concerning the IDD",
    "Consultation on the review of insurance disclosures under the Taxonomy "
    "Disclosures Delegated Act",
    "Endurance and Durability Demonstration (A)",
    "Definition of durability multipliers for Euro 7 heavy-duty vehicles",
    "Harmonised standards under the Medical Devices Directive 93/42/EEC (MDD)",
    "Survey on the integration of sustainability risks and sustainability factors "
    "in the delegated acts under the IDD and the Solvency II Directive",
]


def load_leaf(data):
    for cat in data.get("categories", []):
        for pa in cat.get("policy_areas", []):
            if pa["name"] == LEAF:
                return pa
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    leaf = load_leaf(data)
    if leaf is None:
        print(f"[FAIL] leaf not found: {LEAF}")
        return 1

    before = list(leaf.get("keywords", []))
    after = [k for k in before if k not in REMOVE]
    for k in ADD:
        if k not in after:
            after.append(k)

    print("=== keywords ===")
    for k in before:
        print(f"  {'REMOVE' if k in REMOVE else 'keep  '}  {k}")
    for k in ADD:
        if k not in before:
            print(f"  ADD     {k}")
    print(f"  {len(before)} -> {len(after)}")

    if args.apply:
        leaf["keywords"] = after
        TAXONOMY.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        # the classifier caches the compiled patterns for the process lifetime
        from services.tracking import policy_area_classifier as pac
        pac._leaf_patterns.cache_clear()

    # Test the PROPOSED keyword set directly, so --dry-run proves the change
    # rather than re-measuring the file it has not written yet. This mirrors
    # _leaf_patterns(): phrases match as substrings, single tokens on a left
    # word boundary.
    def leaf_matches(kws, blob: str) -> bool:
        b = blob.lower()
        for k in kws:
            kl = k.lower()
            if (" " in kl and kl in b) or (
                    " " not in kl and re.search(r"\b" + re.escape(kl), b)):
                return True
        return False

    rc = 0
    print("\n=== the regime's own material must still match ===")
    for t in MUST_STILL_MATCH:
        got = leaf_matches(after, t)
        print(f"  {'OK ' if got else 'FAIL'} {t[:82]}")
        if not got:
            rc = 1

    print("\n=== the false positives must stop matching ===")
    for t in MUST_NOT_MATCH:
        got = leaf_matches(after, t)
        was = leaf_matches(before, t)
        print(f"  {'OK ' if not got else 'FAIL'} "
              f"{'(was tagged)' if was else '(was clean)'} {t[:66]}")
        if got:
            rc = 1

    if not args.apply:
        print("\n[DRY-RUN] taxonomy not written, no rows re-classified")
        return rc

    # ---- re-classify the rows the interest currently claims -----------------
    # Imported here, after the taxonomy is written and the pattern cache is
    # cleared, so classify() reads the new keywords.
    from services.tracking.policy_area_classifier import classify

    db = SessionLocal()
    try:
        print("\n=== re-classifying rows that carry the interest ===")
        rows = db.execute(text(
            "SELECT id, title, COALESCE(description,'') AS d, policy_areas "
            "FROM public_consultations WHERE :i = ANY(policy_areas)"),
            {"i": LEAF}).fetchall()
        dropped = kept = 0
        for r in rows:
            areas = classify(r.title, r.d)
            if LEAF in areas:
                kept += 1
                print(f"  [KEEP] {r.title[:74]}")
                continue
            dropped += 1
            new = [a for a in (r.policy_areas or []) if a != LEAF] or areas
            print(f"  [DROP] {r.title[:74]}\n         -> {new}")
            db.execute(text("UPDATE public_consultations SET policy_areas = :a "
                            "WHERE id = :id"), {"a": new, "id": r.id})
        db.commit()
        print(f"  dropped {dropped}, kept {kept}")

        print("\n=== verification ===")
        left = db.execute(text(
            "SELECT title FROM public_consultations WHERE :i = ANY(policy_areas)"),
            {"i": LEAF}).fetchall()
        print(f"  consultations carrying the interest: {len(left)}")
        for x in left:
            print(f"    {x.title[:80]}")
        bad = [x for x in left
               if re.search(r"insurance|solvency|\bIDD\b|taxonomy disclosure",
                            x.title, re.I)]
        print(f"  insurance/IDD rows still tagged: {len(bad)} "
              f"{'OK' if not bad else 'FAIL'}")
        if bad:
            rc = 1
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
