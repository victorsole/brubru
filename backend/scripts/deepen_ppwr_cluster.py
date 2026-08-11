"""Deepen and correct cluster 57 (PPWR - Packaging and Packaging Waste Regulation).

The PPWR, Regulation (EU) 2025/40, applies from 12 August 2026 (Article 71),
repealing Directive 94/62/EC that day (Article 70). Cluster 57 had 20
requirements and three problems.

1. Nothing carried the application date. Every row was dated December 2025,
   2028, 2030 or null, so the package never told a company that the Regulation
   becomes applicable to it on 12 August 2026. Two obligations that bite from
   exactly that date were mis-dated:
     * Article 6(1) recyclability was dated 2030. The Commission guidance
       (C(2026) 3702, para 345) is explicit: "Article 6(1) requires that all
       packaging placed on the market is recyclable without providing a
       specific deadline ... which means that it applies from 12 August 2026."
       The 2030 date belongs to the design-for-recycling performance grades set
       by a later implementing act, not to the basic recyclability duty.
     * Article 5 substance restrictions (including the PFAS limits in
       food-contact packaging) carried no date. The guidance (para 319, 328)
       applies the PFAS limits "as of their application date, i.e. 12 August
       2026", with no transitional period for stock exhaustion.

2. Eight rows bound authorities, not companies. Member State duties (waste
   reduction and recycling targets, EPR scheme establishment, competent
   authority designation) and two rows that bind the Commission or Member
   States on penalties were being counted as company obligations. They are
   context a company should see -- the EPR fee under Article 45 is why the
   Article 44 registration matters -- so they are marked interpretive rather
   than deleted: visible in the preview, not scored.

3. The "prove it" duties were missing. A manufacturer must carry out the
   conformity assessment (Article 38), draw up the technical documentation
   (Annex VII), and issue the EU declaration of conformity (Article 39) before
   placing packaging on the market (Article 15). None of that was in the
   package, nor the importer's verification duty (Article 18). All three are
   grounded in the operative article text read from the Formex text of the
   Regulation in the November 2025 corpus.

  python3.12 -m scripts.deepen_ppwr_cluster --dry-run
  python3.12 -m scripts.deepen_ppwr_cluster --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import logging  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal, engine  # noqa: E402

engine.echo = False

CLUSTER_ID = 57
PPWR = "32025R0040"
APPLICATION_DATE = "2026-08-12"
SEED_TAG = {"source": "deepen_ppwr_cluster", "curated": True}

# Rows that bind an authority (Member State or Commission), not a company.
# Marked interpretive so they stay visible as context but are not scored.
# Article label -> the correct addressee to record.
MARK_INTERPRETIVE = {
    "Article 34": "member_state",   # sustained reduction of packaging waste
    "Article 40": "member_state",   # designate competent authorities
    "Article 43": "member_state",   # reduce packaging waste per capita
    "Article 45": "member_state",   # establish and operate EPR schemes
    "Article 50": "member_state",   # separate-collection measures
    "Article 52": "member_state",   # minimum recycling targets
    "Article 63": "commission",     # Commission adopts implementing acts (mis-tagged)
    "Article 68": "member_state",   # Member States lay down penalties (mis-tagged)
}

# Date corrections, with text where the stored text asserted the wrong date.
REDATE = {
    "Article 5": (APPLICATION_DATE, None),
    "Article 10": (APPLICATION_DATE, None),
    "Article 6": (
        APPLICATION_DATE,
        "All packaging placed on the Union market must be recyclable. Under "
        "Article 6(1) this basic duty applies from 12 August 2026, the "
        "Regulation's application date, with no separate deadline. It is "
        "phased: packaging must be designed for recycling and, once the "
        "Commission implementing act on design-for-recycling performance grades "
        "applies (expected from 2028), be assessed against grades A to C; and "
        "from 2035 it must be recyclable at scale. Design your packaging for "
        "material recycling now, because the classification that follows is "
        "built on that design."),
}

# article (<=50), text, criticality, applicable_entity (<=100), addressee, deadline, interpretive
NEW_REQUIREMENTS = [
    ("Arts 15, 38, 39 (conformity + declaration)",
     "Before placing packaging on the market, and as the manufacturer, carry "
     "out the Annex VII conformity assessment (Article 38) or have it carried "
     "out for you, draw up the Annex VII technical documentation, and issue the "
     "EU declaration of conformity (Article 39) stating that the requirements "
     "in Articles 5 to 12 are met. Keep the documentation and the declaration "
     "for five years after the packaging is placed on the market, and keep the "
     "declaration continuously updated. This is the evidence a market "
     "surveillance authority asks for; without it, compliance with the design "
     "rules cannot be demonstrated.",
     "critical", "Manufacturers of packaging", "economic_operator",
     APPLICATION_DATE, False),

    ("Article 18 (importer verification)",
     "If you import packaging or packaged products into the Union, place on the "
     "market only packaging that conforms to Articles 5 to 12. Before doing so, "
     "verify that the manufacturer carried out the conformity assessment and "
     "drew up the technical documentation, that the packaging bears any "
     "required labelling, and that the manufacturer is identified. Keep a copy "
     "of the EU declaration of conformity for five years. An importer that "
     "puts packaging on the market under its own name, or modifies it, takes on "
     "the manufacturer's full obligations.",
     "important", "Importers of packaging", "economic_operator",
     APPLICATION_DATE, False),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    plan = []
    try:
        law_id = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                            {"x": PPWR}).scalar()
        if not law_id:
            print(f"[ERROR] {PPWR} not in eu_laws")
            return 1

        # 1. Mark authority rows interpretive and fix their addressee.
        for article, addressee in MARK_INTERPRETIVE.items():
            r = db.execute(text("""
                UPDATE law_requirements
                   SET extra_metadata = COALESCE(extra_metadata,'{}'::jsonb)
                       || jsonb_build_object('interpretive','true','addressee',:a)
                 WHERE cluster_id=:c AND law_id=:l AND article=:art
                RETURNING id"""),
                {"a": addressee, "c": CLUSTER_ID, "l": law_id, "art": article}).fetchall()
            plan.append(f"{'CONTEXT' if r else '[skip]'} {article} -> interpretive, binds {addressee}")

        # 2. Date corrections.
        for article, (date, new_text) in REDATE.items():
            if new_text:
                r = db.execute(text("""
                    UPDATE law_requirements SET deadline=:d, requirement_text=:t
                     WHERE cluster_id=:c AND law_id=:l AND article=:art RETURNING id"""),
                    {"d": date, "t": new_text, "c": CLUSTER_ID, "l": law_id, "art": article}).fetchall()
                plan.append(f"{'REDATE+REWRITE' if r else '[skip]'} {article} -> {date}")
            else:
                r = db.execute(text("""
                    UPDATE law_requirements SET deadline=:d
                     WHERE cluster_id=:c AND law_id=:l AND article=:art RETURNING id"""),
                    {"d": date, "c": CLUSTER_ID, "l": law_id, "art": article}).fetchall()
                plan.append(f"{'REDATE' if r else '[skip]'} {article} -> {date}")

        # 3. Add the conformity and importer obligations.
        added = 0
        for article, body, crit, entity, addressee, deadline, interp in NEW_REQUIREMENTS:
            if len(article) > 50 or len(entity) > 100:
                print(f"[ERROR] label too long: {article!r} ({len(article)}/50)")
                db.rollback()
                return 1
            if db.execute(text("""SELECT 1 FROM law_requirements
                                   WHERE cluster_id=:c AND law_id=:l AND article=:a"""),
                          {"c": CLUSTER_ID, "l": law_id, "a": article}).scalar():
                plan.append(f"[exists] {article}")
                continue
            meta = {**SEED_TAG, "law_celex": PPWR, "addressee": addressee}
            if interp:
                meta["interpretive"] = "true"
            db.execute(text("""
                INSERT INTO law_requirements
                    (law_id, cluster_id, article, requirement_text, criticality,
                     applicable_entity, deadline, extra_metadata)
                VALUES (:l,:c,:a,:t,:crit,:e,:d, CAST(:m AS jsonb))"""),
                {"l": law_id, "c": CLUSTER_ID, "a": article, "t": body, "crit": crit,
                 "e": entity, "d": deadline, "m": json.dumps(meta)})
            added += 1
            plan.append(f"ADD {article} ({crit}, {deadline})")

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        rows = db.execute(text("""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE COALESCE(extra_metadata->>'interpretive','')<>'true') AS binding,
                   count(*) FILTER (WHERE deadline::date = :d) AS at_application_date
              FROM law_requirements WHERE cluster_id=:c AND law_id=:l"""),
            {"c": CLUSTER_ID, "l": law_id, "d": APPLICATION_DATE}).fetchone()
        print(f"\n[OK] committed. Cluster {CLUSTER_ID}: {rows[0]} rows, {rows[1]} binding, "
              f"{rows[2]} now dated 12 August 2026. Added {added}.")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
