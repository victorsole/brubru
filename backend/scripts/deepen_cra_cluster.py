"""Deepen cluster 21's Cyber Resilience Act rows (CELEX 32024R2847).

The CRA's first binding deadline, Article 14 reporting, applies from
11 September 2026. Unlike the AI Act and PPWR runs, the dates in this package
were already right and the application date was already anchored: the Article 14
row carried 2026-09-11 before this script ran. So this is a genuine deepening,
not a correction, and it does three things.

1. Two authority rows were marked interpretive but still recorded
   `addressee=economic_operator`, so the validator reported "0 bind someone
   else" for a package that plainly contains Member State duties. Article 33
   (awareness-raising and training for SMEs) and Article 64 (Member States lay
   down the rules on penalties) bind Member States, not the company. They stay
   visible as context -- a company should see why a national authority may fine
   it -- but they are now attributed correctly.

2. The single most consequential scoping rule in the whole Regulation was
   missing: Article 69(3). Article 69(2) spares products placed on the market
   before 11 December 2027 unless they are substantially modified, and a reader
   who stops there concludes the CRA is a 2027 problem. Article 69(3)
   derogates from exactly that for Article 14, so the reporting duty reaches
   the existing installed base from 11 September 2026. The Commission FAQ
   (v1.0, 3 December 2025, section 5.3) adds the limiting principle that makes
   this workable and that no summary carries: for those legacy products the
   manufacturer must notify, but is NOT required to comply with the other
   obligations such as vulnerability handling, and the duty bites on awareness
   arising after the reporting rules apply.

3. Three context rows for dates the package never carried: the notified-body
   regime that has been applying since 11 June 2026 (Article 71(2) first
   subparagraph, Chapter IV), the Article 69(1) transitional that keeps
   existing certificates valid until 11 June 2028, and the harmonised-standards
   timeline, which matters because self-assessment against harmonised standards
   is the default conformity route and the standards are not ready yet.

Sources read for this run, all primary: the Regulation itself (EUR-Lex CELEX
32024R2847, Articles 13, 14, 16, 27, 35-51, 64, 69, 71 and Annex I); the
Commission FAQ v1.0 of 3 December 2025; and the four DG CNECT audience pages
(manufacturers, Member States, conformity assessment, MSMEs).

  python3.12 -m scripts.deepen_cra_cluster --dry-run
  python3.12 -m scripts.deepen_cra_cluster --apply
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

CLUSTER_ID = 21
CRA = "32024R2847"
REPORTING_DATE = "2026-09-11"      # Article 14, Article 71(2) 2nd subpara
NOTIFIED_BODY_DATE = "2026-06-11"  # Chapter IV, Articles 35-51
FULL_APPLICATION = "2027-12-11"    # Article 71(2)
CERT_VALIDITY_END = "2028-06-11"   # Article 69(1)
SEED_TAG = {"source": "deepen_cra_cluster", "curated": True}

# Rows already flagged interpretive but still attributed to the company.
# Article label prefix -> the addressee that actually bears the duty.
FIX_ADDRESSEE = {
    "Art 33": "member_state",   # awareness-raising and training for SMEs
    "Art 64": "member_state",   # Member States lay down the rules on penalties
}

# article (<=50), text, criticality, applicable_entity (<=100), addressee, deadline, interpretive
NEW_REQUIREMENTS = [
    ("Art 69(3) (legacy products, reporting)",
     "The reporting duty reaches products you already sold. Article 69(2) "
     "spares products placed on the market before 11 December 2027 unless they "
     "are substantially modified, but Article 69(3) expressly disapplies that "
     "for Article 14: from 11 September 2026 you must notify actively "
     "exploited vulnerabilities and severe incidents for every in-scope "
     "product with digital elements you have placed on the market, including "
     "the existing installed base. The Commission FAQ (v1.0, 3 December 2025, "
     "section 5.3) sets the limit: for those legacy products you are required "
     "to notify, but you are NOT required to meet the other obligations such "
     "as vulnerability handling, since build environments, tooling and staff "
     "for old code may no longer exist. The duty attaches on becoming aware "
     "after the reporting rules start applying, not retrospectively. Build the "
     "notification path for the whole portfolio, not only for new products.",
     "critical", "Manufacturers of products with digital elements",
     "economic_operator", REPORTING_DATE, False),

    ("Art 69(1) (existing certificates)",
     "EU-type examination certificates and approval decisions issued on "
     "cybersecurity requirements under other Union harmonisation legislation, "
     "such as Commission Delegated Regulation (EU) 2022/30 under the Radio "
     "Equipment Directive, remain valid until 11 June 2028, unless that "
     "legislation says otherwise or the certificate expires sooner. Check the "
     "expiry of every certificate you rely on and plan reassessment under the "
     "CRA before it lapses, because the transitional does not renew itself.",
     "important", "Manufacturers relying on existing cybersecurity certificates",
     "economic_operator", CERT_VALIDITY_END, False),

    ("Arts 35-51 (notified bodies, applying)",
     "Chapter IV has been applying since 11 June 2026, ahead of the rest of "
     "the Regulation. By that date Member States had to designate the "
     "notifying authorities responsible for assessing, designating and "
     "monitoring conformity assessment bodies. Bodies that complete the "
     "procedure are published on the Commission's NANDO database. This is "
     "context rather than a duty on you, but it is the reason a notified body "
     "can be engaged now: if your product needs a third-party route, capacity "
     "is being built during the run-up, and Article 43(2) only asks Member "
     "States to strive to have enough notified bodies by 11 December 2026.",
     "recommended", "Member States and conformity assessment bodies",
     "member_state", NOTIFIED_BODY_DATE, True),

    ("Art 16 (single reporting platform)",
     "Notifications under Article 14 go through a single reporting platform "
     "operated by ENISA, with the notification reaching the CSIRT designated "
     "as coordinator and ENISA at the same time. The platform is the "
     "infrastructure the reporting duty depends on, so confirm the submission "
     "route and your access to it before 11 September 2026 rather than while "
     "a 24-hour clock is running.",
     "recommended", "ENISA and the coordinating CSIRTs",
     "eu_agency", REPORTING_DATE, True),

    ("Art 27 (harmonised standards route)",
     "Conformity is presumed where a product meets harmonised standards cited "
     "in the Official Journal, and for most products self-assessment against "
     "those standards is the default route. The standards are not all ready: "
     "the Commission FAQ records that the horizontal standard on secure "
     "products and the standard on vulnerability handling were requested from "
     "the European standardisation organisations by 30 August 2026, and the "
     "standard covering the Annex I Part I essential requirements by "
     "30 October 2027. Where no harmonised standard is available in time, the "
     "burden of demonstrating conformity by other means falls on you, so track "
     "the citations rather than assuming a standard will exist.",
     "recommended", "Manufacturers of products with digital elements",
     "commission", FULL_APPLICATION, True),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    plan: list[str] = []
    try:
        law_id = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                            {"x": CRA}).scalar()
        if not law_id:
            print(f"[ERROR] {CRA} not in eu_laws")
            return 1

        # 1. Attribute the authority rows correctly. They are already
        #    interpretive; only the addressee is wrong.
        for prefix, addressee in FIX_ADDRESSEE.items():
            r = db.execute(text("""
                UPDATE law_requirements
                   SET extra_metadata = COALESCE(extra_metadata,'{}'::jsonb)
                       || jsonb_build_object('interpretive','true','addressee',:a)
                 WHERE cluster_id=:c AND law_id=:l AND article LIKE :art
                RETURNING id"""),
                {"a": addressee, "c": CLUSTER_ID, "l": law_id,
                 "art": f"{prefix}%"}).fetchall()
            plan.append(
                f"{'ATTRIBUTE' if r else '[skip]'} {prefix}* -> binds {addressee}"
                f" ({len(r)} row(s))")

        # 2. Add the missing scoping, transitional and context rows.
        added = 0
        for article, body, crit, entity, addressee, deadline, interp in NEW_REQUIREMENTS:
            if len(article) > 50 or len(entity) > 100:
                print(f"[ERROR] too long: {article!r} "
                      f"(article {len(article)}/50, entity {len(entity)}/100)")
                db.rollback()
                return 1
            if db.execute(text("""SELECT 1 FROM law_requirements
                                   WHERE cluster_id=:c AND law_id=:l AND article=:a"""),
                          {"c": CLUSTER_ID, "l": law_id, "a": article}).scalar():
                plan.append(f"[exists] {article}")
                continue
            meta = {**SEED_TAG, "law_celex": CRA, "addressee": addressee}
            if interp:
                meta["interpretive"] = "true"
            db.execute(text("""
                INSERT INTO law_requirements
                    (law_id, cluster_id, article, requirement_text, criticality,
                     applicable_entity, deadline, extra_metadata)
                VALUES (:l,:c,:a,:t,:crit,:e,:d, CAST(:m AS jsonb))"""),
                {"l": law_id, "c": CLUSTER_ID, "a": article, "t": body,
                 "crit": crit, "e": entity, "d": deadline,
                 "m": json.dumps(meta)})
            added += 1
            plan.append(f"ADD {article} ({crit}, {deadline}, "
                        f"{'context' if interp else 'binding'})")

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        row = db.execute(text("""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE COALESCE(extra_metadata->>'interpretive','')<>'true') AS binding,
                   count(*) FILTER (WHERE deadline::date = :d) AS at_reporting_date,
                   count(*) FILTER (WHERE COALESCE(extra_metadata->>'addressee','economic_operator')
                                          <> 'economic_operator') AS binds_others
              FROM law_requirements WHERE cluster_id=:c AND law_id=:l"""),
            {"c": CLUSTER_ID, "l": law_id, "d": REPORTING_DATE}).fetchone()
        print(f"\n[OK] committed. Cluster {CLUSTER_ID} / CRA: {row[0]} rows, "
              f"{row[1]} binding, {row[2]} dated 11 September 2026, "
              f"{row[3]} bind an authority. Added {added}.")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
