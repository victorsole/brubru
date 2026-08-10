"""Rebuild cluster 21, "SaaS & B2B Startup Compliance", from duties that bind a SaaS company.

The defect
----------
Third startup cluster with the same shape as 17 and 18, and the emptiest of the
three once you look at who its requirements bind. Cluster 21 held 21 rows:

  * 13 from the NIS2 implementing regulation 2024/2690 -- every one a RECITAL
    ("The relevant entities should establish a policy on the security of network
    and information systems"). Correct content, no operative force, and all now
    excluded from scoring as interpretive. Net contribution: zero.
  * 8 from the GDPR, every one binding a SUPERVISORY AUTHORITY rather than a
    company: Article 41(3) and 41(5) on accrediting monitoring bodies, 43(6) on
    publishing accreditation criteria, 57(1)(p), 64(6) and 64(7) on the
    consistency mechanism, 69(2) on the Board's independence. A B2B SaaS
    company was being asked to demonstrate compliance with the procedure for
    revoking a monitoring body's accreditation.

So the cluster's true binding content was nil. It advertised the GDPR, which is
the single most relevant regime for a B2B SaaS business, and delivered the
regulator's own procedural rules.

What this seeds
---------------
The duties a SaaS or B2B software company in the EU actually carries, from the
acts already in eu_laws:

  32016R0679  GDPR         processor duties, DPAs, transfers, breach, records
  32022R2555  NIS2         where the company is in scope as a digital provider
  32023R2854  Data Act     switching between data processing services

The Cyber Resilience Act (Regulation (EU) 2024/2847) is the fourth regime this
cluster should carry -- it binds anyone placing software with digital elements
on the EU market, with the main obligations applying from 11 December 2027 --
but it is NOT in eu_laws (only two corrigenda to it are, both empty). Adding it
needs a corpus ingest first, so this script does not pretend to cover it. The
gap is stated here rather than quietly left.

Note on NIS2 scope: most small SaaS companies are OUT of scope. NIS2 applies to
medium and large entities, meaning 50+ staff or over EUR 10 million turnover,
and cloud computing, data centre, managed service and managed security service
providers are Annex I "important" or "essential" entities. The scope question is
therefore stated first and marked critical, exactly as the high-risk question is
in cluster 17, so the analysis establishes it before anything downstream.

Usage:
  python3.12 -m scripts.rebuild_saas_startup_cluster --dry-run
  python3.12 -m scripts.rebuild_saas_startup_cluster --apply
"""
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

from core.database import SessionLocal  # noqa: E402

CLUSTER_ID = 21
ATTACH = ["32016R0679", "32022R2555", "32023R2854"]
SEED_TAG = {"source": "rebuild_saas_startup_cluster", "curated": True}

# article (<=50 chars), text, criticality, applicable_entity (<=100), addressee, deadline, interpretive
REQUIREMENTS = [
    ("32022R2555", [
        ("Arts 2-3 + Annexes I-II (are you in scope?)",
         "Establish first whether NIS2 applies at all, because nothing else in this regime "
         "follows if it does not. It catches medium and large entities, meaning 50 or more "
         "staff or annual turnover and balance sheet total above EUR 10 million, that operate "
         "in an Annex I or Annex II sector. For software businesses the relevant entries are "
         "cloud computing service providers, data centre service providers, managed service "
         "providers and managed security service providers, all of which are 'important' "
         "entities, plus DNS, TLD and trust service providers, which are 'essential'. Size "
         "thresholds do not apply to those last categories. A small SaaS company selling "
         "ordinary business software is usually out of scope, and recording that conclusion is "
         "the compliant outcome.",
         "critical", "Digital service providers", "economic_operator", None, False),

        ("Article 21 (risk management measures)",
         "If in scope, take appropriate and proportionate technical, operational and "
         "organisational measures covering at least: policies on risk analysis and information "
         "system security; incident handling; business continuity including backup management "
         "and crisis management; supply chain security including the security of relationships "
         "with direct suppliers; security in acquisition, development and maintenance including "
         "vulnerability handling and disclosure; policies to assess the effectiveness of those "
         "measures; basic cyber hygiene and security training; policies on cryptography and "
         "encryption; human resources security, access control and asset management; and "
         "multi-factor or continuous authentication and secured communications.",
         "critical", "Essential and important entities", "economic_operator", None, False),

        ("Article 23 (24h / 72h / 1 month reporting)",
         "If in scope, report significant incidents to the CSIRT or competent authority on a "
         "fixed clock: an early warning within 24 hours of becoming aware, an incident "
         "notification with an initial assessment within 72 hours, and a final report within "
         "one month. An incident is significant if it has caused or is capable of causing "
         "severe operational disruption or financial loss, or considerable material or "
         "non-material damage to others. Where the incident is likely to affect the provision "
         "of services, inform recipients too.",
         "critical", "Essential and important entities", "economic_operator", None, False),

        ("Article 20 (management accountability)",
         "If in scope, the management body must approve the cybersecurity risk management "
         "measures, oversee their implementation, and can be held liable for failing to do so. "
         "Members of the management body must follow training, and entities must offer similar "
         "training to their staff regularly.",
         "important", "Management bodies of in-scope entities", "economic_operator", None, False),
    ]),

    ("32016R0679", [
        ("Article 28 (you are probably a processor)",
         "A B2B SaaS provider handling customer data is normally a processor, and must be "
         "engaged under a written contract covering the subject matter, duration, nature and "
         "purpose of processing, the types of data and categories of data subject, and the "
         "controller's rights. Process only on documented instructions, ensure staff are bound "
         "by confidentiality, apply Article 32 security, respect the conditions for engaging "
         "sub-processors including prior specific or general written authorisation and notice "
         "of changes, assist the controller with data subject rights and with Articles 32 to "
         "36, delete or return the data at the end of the service, and make available the "
         "information needed to demonstrate compliance and allow audits.",
         "critical", "SaaS providers acting as processors", "economic_operator", None, False),

        ("Article 30(2) (processor's record of processing)",
         "Maintain a record of all categories of processing carried out on behalf of each "
         "controller, including the controller's identity, the categories of processing, any "
         "third-country transfers with the safeguards relied on, and a general description of "
         "the technical and organisational security measures. The under-250-employee exemption "
         "rarely helps a SaaS business because the processing is not occasional.",
         "important", "Processors", "economic_operator", None, False),

        ("Article 32 (security of processing)",
         "Implement security appropriate to the risk, having regard to the state of the art and "
         "the costs of implementation, considering pseudonymisation and encryption, the ability "
         "to ensure ongoing confidentiality, integrity, availability and resilience, the ability "
         "to restore availability after an incident, and a process for regularly testing and "
         "evaluating the effectiveness of the measures.",
         "critical", "Controllers and processors", "economic_operator", None, False),

        ("Article 33(2) (breach notice to your customer)",
         "As a processor, notify the controller without undue delay after becoming aware of a "
         "personal data breach. The controller's own 72-hour clock to the supervisory authority "
         "starts when it becomes aware, so a slow processor notification is what makes a "
         "customer late. Fix the trigger, the route and the content of that notice in the data "
         "processing agreement rather than leaving it to the incident.",
         "critical", "Processors", "economic_operator", None, False),

        ("Ch V, Arts 44-49 (international transfers)",
         "Transfer personal data outside the EEA only on a valid basis: an adequacy decision, "
         "standard contractual clauses or binding corporate rules with a transfer impact "
         "assessment, or a narrow Article 49 derogation. Map where the data actually goes, "
         "including sub-processors, support teams with remote access and backup regions, "
         "because a US-headquartered analytics tool or a support desk outside the EEA is a "
         "transfer whether or not it appears in the architecture diagram.",
         "critical", "Controllers and processors transferring data", "economic_operator",
         None, False),

        ("Arts 13-14 + 12 (transparency to end users)",
         "Where the company acts as a controller, over its own website, marketing and its "
         "employees, provide the Article 13 and 14 information in a concise, transparent, "
         "intelligible and easily accessible form using clear and plain language, and respond "
         "to data subject requests within one month.",
         "important", "Controllers", "economic_operator", None, False),

        ("Article 37 (do you need a DPO?)",
         "Designate a data protection officer where the core activities consist of processing "
         "that requires regular and systematic monitoring of data subjects on a large scale, or "
         "large-scale processing of special categories or criminal conviction data. Acting as a "
         "processor does not by itself trigger the duty, and recording a reasoned conclusion "
         "that no DPO is required is a compliant outcome.",
         "recommended", "Controllers and processors", "economic_operator", None, False),
    ]),

    ("32023R2854", [
        ("Arts 23-26, 29 (switching and exit)",
         "As a provider of a data processing service, remove the commercial, technical, "
         "contractual and organisational obstacles that stop a customer moving to another "
         "provider or to its own infrastructure: a maximum 30-day notice period to start "
         "switching, a transitional period of up to 30 days extendable where technically "
         "unfeasible, functional equivalence for infrastructure services, and export of all "
         "exportable data in a structured, commonly used and machine-readable format. Switching "
         "charges were reduced from 12 January 2024 and are withdrawn entirely from 12 January "
         "2027.",
         "important", "Providers of data processing services", "economic_operator",
         "2025-09-12", False),

        ("Art 28 + Ch VI (contract terms, non-EU access)",
         "Set out the switching arrangements in the contract in writing and make it available "
         "before signature, and take reasonable technical, organisational and legal measures to "
         "prevent international governmental access to non-personal data held in the Union "
         "where that access would conflict with Union or Member State law.",
         "recommended", "Providers of data processing services", "economic_operator",
         "2025-09-12", False),
    ]),
]


def main():
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
            print(f"[ABORT] {used} gap_findings reference cluster {CLUSTER_ID}")
            return 1
        plan.append(f"0 gap_findings depend on cluster {CLUSTER_ID}")

        # Drop the supervisory-authority GDPR rows and the recital-only NIS2 IR
        # rows. Both are kept in their other clusters; only this cluster's copies go.
        dropped = db.execute(text("""
            DELETE FROM law_requirements
             WHERE cluster_id=:c
               AND (COALESCE(extra_metadata->>'addressee','economic_operator') <> 'economic_operator'
                 OR COALESCE(extra_metadata->>'interpretive','') = 'true')
            RETURNING id"""), {"c": CLUSTER_ID}).fetchall()
        plan.append(f"DELETE {len(dropped)} rows that bind an authority or are recitals")

        law_ids = {}
        for celex in ATTACH:
            lid = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"), {"x": celex}).scalar()
            if not lid:
                print(f"[ERROR] {celex} not in eu_laws")
                db.rollback()
                return 1
            law_ids[celex] = lid
            if not db.execute(text("SELECT 1 FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                              {"c": CLUSTER_ID, "l": lid}).scalar():
                db.execute(text("INSERT INTO cluster_laws (cluster_id, law_id) VALUES (:c,:l)"),
                           {"c": CLUSTER_ID, "l": lid})
                plan.append(f"ATTACH {celex}")

        added = 0
        for celex, reqs in REQUIREMENTS:
            lid = law_ids[celex]
            for article, body, crit, entity, addressee, deadline, interpretive in reqs:
                if len(article) > 50 or len(entity) > 100:
                    print(f"[ERROR] label too long: {article!r} ({len(article)}/50), "
                          f"entity {len(entity)}/100")
                    db.rollback()
                    return 1
                if db.execute(text("""SELECT 1 FROM law_requirements
                                       WHERE cluster_id=:c AND law_id=:l AND article=:a"""),
                              {"c": CLUSTER_ID, "l": lid, "a": article}).scalar():
                    continue
                meta = {**SEED_TAG, "law_celex": celex, "addressee": addressee}
                if interpretive:
                    meta["interpretive"] = "true"
                db.execute(text("""
                    INSERT INTO law_requirements
                        (law_id, cluster_id, article, requirement_text, criticality,
                         applicable_entity, deadline, extra_metadata)
                    VALUES (:l,:c,:a,:t,:crit,:e,:d, CAST(:m AS jsonb))"""),
                    {"l": lid, "c": CLUSTER_ID, "a": article, "t": body, "crit": crit,
                     "e": entity, "d": deadline, "m": json.dumps(meta)})
                added += 1
        plan.append(f"INSERT {added} curated law_requirements")

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        rows = db.execute(text("""
            SELECT l.celex, count(*) AS n,
                   count(*) FILTER (WHERE COALESCE(r.extra_metadata->>'interpretive','')<>'true') AS binding
              FROM law_requirements r JOIN eu_laws l ON l.id=r.law_id
             WHERE r.cluster_id=:c GROUP BY l.celex ORDER BY n DESC"""),
            {"c": CLUSTER_ID}).fetchall()
        print(f"\n[OK] committed. Cluster {CLUSTER_ID}:")
        for celex, n, binding in rows:
            print(f"  {celex}  {n} requirements ({binding} binding)")
        print("  NOT covered: Cyber Resilience Act 2024/2847, absent from eu_laws")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
