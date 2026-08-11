"""Deepen and correct the AI Act obligations in cluster 17 (AI/ML Startup Compliance).

Cluster 17 is the highest-demand package in the catalogue: 741 registered
companies declare the AI Act among the files they work on
(scripts/rank_packages_by_demand). It carried 13 AI Act obligations, and two
things were wrong with them.

1. The dates were pre-amendment. The AI Act's high-risk timeline was moved by
   amending Regulation (EU) 2026/1744, confirmed against the original Article
   113 text and four Commission sources (the regulatory-framework page, the AI
   Act Service Desk FAQ, the high-risk guidelines page, and the amendment
   itself):
     * Annex III high-risk (Chapter III, Sections 1-3): 2 August 2026 -> 2
       December 2027.
     * Article 6(1) product-embedded high-risk: 2 August 2027 -> 2 August 2028.
   Every high-risk row in the cluster said 2 August 2026, so the package was
   telling companies a duty binds them more than a year before it does.

2. It was shallow. Real operator obligations were missing entirely:
   registration in the EU database (Art 49), post-market monitoring (Art 72),
   serious-incident reporting with its 15-day / 10-day / 2-day clock (Art 73),
   and the deployer fundamental-rights impact assessment (Art 27). The two new
   Article 5 prohibitions added by the 2026 amendment -- non-consensual intimate
   imagery and CSAM generation -- were also absent.

Every requirement text below is grounded in the operative article read from the
Formex text of the AI Act in the November 2025 corpus
(docs/LEG_2025-11/dc8116a1-.../L_202401689EN.000101.fmx.xml), not from a
summary. The Article 73 deadlines and the Article 72 wording are quoted from
that text.

The obligations still live in Regulation (EU) 2024/1689, which is in eu_laws;
the 2026 amendment changed dates and added two prohibitions but did not move the
duties to a new act. Requirement text attributes the amendment where it bites.
Ingesting Regulation (EU) 2026/1744 as its own eu_laws row (it postdates the Nov
2025 corpus) is a sensible follow-up but not required for these obligations to
be truthful.

  python3.12 -m scripts.deepen_ai_act_cluster --dry-run
  python3.12 -m scripts.deepen_ai_act_cluster --apply
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

CLUSTER_ID = 17
AI_ACT = "32024R1689"

# The high-risk application date as amended by Regulation (EU) 2026/1744.
HIGH_RISK_DATE = "2027-12-02"

SEED_TAG = {"source": "deepen_ai_act_cluster", "curated": True}

# Existing rows whose date was pre-amendment. Matched by article label so the
# script is idempotent and readable. Each is a high-risk (Chapter III) duty.
REDATE_TO_HIGH_RISK = [
    "Article 6 + Annex III (high-risk?)",
    "Arts 9, 10, 15 (risk, data, robustness)",
    "Arts 11-14 (docs, logs, oversight)",
    "Arts 16, 43, 47-49 (QMS, conformity)",
    "Article 25 (you become the provider)",
    "Arts 26-27 (deploying high-risk AI)",
]

# Text corrections on existing rows, appended so the amendment is visible on the
# obligation itself rather than only in this script.
TEXT_APPENDS = {
    "Article 5 (prohibited practices)":
        " Amending Regulation (EU) 2026/1744 added two further prohibited "
        "practices in 2026: AI that generates non-consensual intimate imagery of "
        "an identifiable person, and AI that generates or manipulates child "
        "sexual abuse material. See the separate row for those.",
    "Article 4 (AI literacy)":
        " The 2026 amendment softened this from a guarantee to an obligation to "
        "take measures to support a sufficient level of AI literacy.",
    "Article 6 + Annex III (high-risk?)":
        " The date this and the other high-risk duties bind was moved from 2 "
        "August 2026 to 2 December 2027 by amending Regulation (EU) 2026/1744; "
        "Article 6(1) product-embedded systems apply from 2 August 2028.",
}

# article (<=50), text, criticality, applicable_entity (<=100), addressee, deadline, interpretive
NEW_REQUIREMENTS = [
    ("Art 5 (new prohibitions: NCII and CSAM)",
     "Do not place on the market, put into service or use an AI system that "
     "generates non-consensual intimate imagery of an identifiable natural "
     "person, or that generates or manipulates child sexual abuse material. "
     "These two prohibitions were added to Article 5 by amending Regulation "
     "(EU) 2026/1744 and bind an operator whether the system is designed for "
     "that output or produces it as a reasonably foreseeable outcome without "
     "reasonable and adequate technical safety measures. The AI Act Service "
     "Desk indicates they apply from 2 December 2026; verify the exact date "
     "against the amendment before relying on it.",
     "critical", "All AI operators", "economic_operator", "2026-12-02", False),

    ("Art 49 (register in the EU database)",
     "Before placing a high-risk Annex III system on the market or putting it "
     "into service, register yourself and the system in the EU database under "
     "Article 71. Registration is also required, under Article 49(2), for a "
     "system you have concluded is NOT high-risk under the Article 6(3) "
     "exemption: claiming the exemption is not silent, it is a filing. Point 2 "
     "of Annex III (biometrics) is the exception to the public-database "
     "requirement.",
     "critical", "Providers of high-risk AI systems", "economic_operator",
     HIGH_RISK_DATE, False),

    ("Art 27 (fundamental-rights impact assessment)",
     "If you are a deployer that is a body governed by public law, a private "
     "entity providing public services, or a deployer using a high-risk system "
     "for creditworthiness or credit scoring, or for risk assessment and "
     "pricing in life and health insurance, carry out a fundamental-rights "
     "impact assessment before first use: the deployment processes, the period "
     "and frequency of use, the categories of people affected, the specific "
     "risks of harm to them, the human-oversight measures, and what you will do "
     "if those risks materialise. Notify the market surveillance authority of "
     "the result.",
     "important", "Deployers of high-risk AI systems", "economic_operator",
     HIGH_RISK_DATE, False),

    ("Art 72 (post-market monitoring)",
     "If you provide a high-risk system, establish and document a post-market "
     "monitoring system proportionate to the technology and the risks, based on "
     "a post-market monitoring plan. It must actively and systematically "
     "collect, document and analyse performance data across the system's "
     "lifetime -- from deployers or other sources -- so you can evaluate its "
     "continuous compliance with the Chapter III requirements. Where relevant "
     "it covers interaction with other AI systems.",
     "important", "Providers of high-risk AI systems", "economic_operator",
     HIGH_RISK_DATE, False),

    ("Art 73 (serious-incident reporting)",
     "If you provide a high-risk system placed on the Union market, report any "
     "serious incident to the market surveillance authorities of the Member "
     "State where it occurred, immediately after establishing a causal link, or "
     "the reasonable likelihood of one, between the system and the incident, and "
     "in any event no later than 15 days after becoming aware of it. The clock "
     "is shorter for the worst cases: not later than 10 days where the incident "
     "caused a person's death, and not later than 2 days for a widespread "
     "infringement or a serious and irreversible disruption of critical "
     "infrastructure. An initial incomplete report is acceptable to meet the "
     "deadline, followed by a complete one.",
     "critical", "Providers of high-risk AI systems", "economic_operator",
     HIGH_RISK_DATE, False),
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
        used = db.execute(text("""
            SELECT count(*) FROM gap_findings g JOIN law_requirements r ON r.id=g.requirement_id
             WHERE r.cluster_id=:c"""), {"c": CLUSTER_ID}).scalar()
        if used:
            print(f"[NOTE] {used} gap_findings reference this cluster. This script only "
                  "edits dates and text and adds rows; it deletes nothing, so history "
                  "is preserved.")

        law_id = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                            {"x": AI_ACT}).scalar()
        if not law_id:
            print(f"[ERROR] {AI_ACT} not in eu_laws")
            return 1

        # 1. Re-date the high-risk rows.
        for article in REDATE_TO_HIGH_RISK:
            r = db.execute(text("""
                UPDATE law_requirements SET deadline = :d
                 WHERE cluster_id=:c AND law_id=:l AND article=:a
                RETURNING id, deadline"""),
                {"d": HIGH_RISK_DATE, "c": CLUSTER_ID, "l": law_id, "a": article}).fetchall()
            if r:
                plan.append(f"REDATE {article!r} -> {HIGH_RISK_DATE}")
            else:
                plan.append(f"[skip] {article!r} not found")

        # 2. Append the amendment notes.
        for article, append in TEXT_APPENDS.items():
            r = db.execute(text("""
                UPDATE law_requirements
                   SET requirement_text = requirement_text || :x
                 WHERE cluster_id=:c AND law_id=:l AND article=:a
                   AND requirement_text NOT LIKE '%' || :marker || '%'
                RETURNING id"""),
                {"x": append, "marker": append.strip()[:40],
                 "c": CLUSTER_ID, "l": law_id, "a": article}).fetchall()
            plan.append(f"{'APPEND note to' if r else '[already noted]'} {article!r}")

        # 3. Add the new obligations.
        added = 0
        for article, body, crit, entity, addressee, deadline, interp in NEW_REQUIREMENTS:
            if len(article) > 50 or len(entity) > 100:
                print(f"[ERROR] label too long: {article!r} ({len(article)}/50)")
                db.rollback()
                return 1
            if db.execute(text("""SELECT 1 FROM law_requirements
                                   WHERE cluster_id=:c AND law_id=:l AND article=:a"""),
                          {"c": CLUSTER_ID, "l": law_id, "a": article}).scalar():
                plan.append(f"[exists] {article!r}")
                continue
            meta = {**SEED_TAG, "law_celex": AI_ACT, "addressee": addressee}
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
            plan.append(f"ADD {article!r} ({crit}, {deadline})")

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        rows = db.execute(text("""
            SELECT count(*) AS n,
                   count(*) FILTER (WHERE COALESCE(extra_metadata->>'interpretive','')<>'true') AS binding,
                   count(*) FILTER (WHERE deadline = :d) AS at_high_risk_date
              FROM law_requirements
             WHERE cluster_id=:c AND law_id=:l"""),
            {"c": CLUSTER_ID, "l": law_id, "d": HIGH_RISK_DATE}).fetchone()
        print(f"\n[OK] committed. Cluster {CLUSTER_ID} AI Act rows: {rows[0]} total, "
              f"{rows[1]} binding, {rows[2]} dated {HIGH_RISK_DATE}.")
        print(f"     Added {added} new obligations.")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
