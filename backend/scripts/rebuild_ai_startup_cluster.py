"""Rebuild cluster 17, "AI/ML Startup Compliance", from laws that actually bind an AI startup.

The defect
----------
Cluster 17 is one of ten `is_startup_focused` clusters, which are what EU Law
Comply surfaces by default in "For you". It held 19 requirements, all marked
'critical', drawn from exactly two acts:

  32023R1484  Commission Implementing Regulation (EU) 2023/1484 -- the Eurostat
              ICT-usage *statistics* regulation. Its obligations run on national
              statistical offices ("Member States shall transmit the final data
              to the Commission (Eurostat) by 5 October 2024"). It has nothing
              to do with artificial intelligence and binds no company.
  32024D1459  Commission Decision establishing the European AI Office. Every
              operative sentence starts "The Office shall" -- duties on an EU
              body, not on anyone using or building AI.

So a startup running an analysis here was measured against 19 obligations of
which zero applied to it, and told they were all critical. The cluster is worse
than empty: it manufactures a compliance panic out of statistics law.

The likely cause is that the startup clusters were populated by keyword match
over titles ("information and communication technologies", "artificial
intelligence") rather than by reading who the acts bind. Cluster 18 shows the
same fingerprint: it also holds 32023R1484, plus an expert-group decision, while
the DSA sits in the cluster with zero requirements attached.

What this script does
---------------------
Detaches the two acts, deletes their 19 requirements from cluster 17, and seeds
a curated set from the four regimes an AI company in the EU actually has to
answer for. Requirements are duplicated per cluster by design: law_requirements
.cluster_id is single-valued and the corpus already carries 93 such duplicates,
so the AI Act obligations below coexist with cluster 4's copies.

  32024R1689  AI Act                     the core regime
  32016R0679  GDPR                       training data, DPIA, automated decisions
  32023R2854  Data Act                   connected-product data, cloud switching
  32024L2853  Product Liability Directive software and AI are now "products"

Scope notes, so this never reads as a promise it cannot keep
------------------------------------------------------------
* The AI Act applies in stages: prohibitions and AI literacy from 2 Feb 2025,
  GPAI from 2 Aug 2025, the bulk from 2 Aug 2026, and Article 6(1) high-risk
  products from 2 Aug 2027. Requirements carry the date that binds them so a
  startup is not scored today against a duty that starts next year.
* Most startups are NOT providers of high-risk AI. The classification
  requirement is stated first and marked critical precisely so the analysis
  establishes that question before anything downstream.
* 32024D1459 stays attached to cluster 4 ("AI Act Package"), where a decision
  establishing the AI Office genuinely belongs. Only its link to 17 is cut.

Usage:
  python3.12 -m scripts.rebuild_ai_startup_cluster --dry-run
  python3.12 -m scripts.rebuild_ai_startup_cluster --apply
"""
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

CLUSTER_ID = 17

# Acts whose link to THIS cluster is wrong. Neither is deleted from eu_laws and
# 32024D1459 keeps its place in cluster 4.
DETACH_CELEX = {
    "32023R1484": "Eurostat ICT-usage statistics; binds national statistical offices",
    "32024D1459": "establishes the European AI Office; binds an EU body, stays in cluster 4",
}

ATTACH = ["32024R1689", "32016R0679", "32023R2854", "32024L2853"]

SEED_TAG = {"source": "rebuild_ai_startup_cluster", "curated": True}

# article, text, criticality, applicable_entity, addressee, applies_from
#
# A trailing "interpretive" entry marks a row that EXPLAINS the regime instead
# of imposing a duty: the penalty ceilings, the systemic-risk compute threshold,
# the sandbox and SME-support offer. The first run of this cluster returned
# "Article 99 (penalties)" as a GAP, which told a company it had failed to
# comply with the size of its own potential fine. Interpretive rows are excluded
# from the analysed set in api/eu_law_comply.py and stay visible in the cluster
# preview, where the context is worth reading.
REQUIREMENTS = [
    # ---------------------------------------------------------------- AI Act
    ("32024R1689", [
        ("Article 6 + Annex III (high-risk?)",
         "Establish first whether the AI system is high-risk, because almost every other duty "
         "follows from the answer. A system is high-risk if it is a safety component of, or is "
         "itself, a product covered by the Union harmonisation legislation in Annex I and "
         "requires third-party conformity assessment, or if it falls in an Annex III area: "
         "biometrics, critical infrastructure, education, employment and worker management, "
         "access to essential public and private services including creditworthiness and life "
         "or health insurance pricing, law enforcement, migration and border control, or the "
         "administration of justice. A system in an Annex III area is not high-risk if it only "
         "performs a narrow procedural task, improves the result of prior human work, detects "
         "decision patterns without replacing human assessment, or is preparatory. Document the "
         "assessment either way and register it under Article 49(2) when relying on that "
         "exemption.",
         "critical", "AI providers and deployers", "economic_operator", "2026-08-02"),

        ("Article 5 (prohibited practices)",
         "Do not place on the market, put into service or use AI for any of the eight "
         "prohibited practices: purposefully manipulative or deceptive techniques that "
         "materially distort behaviour and cause significant harm; exploitation of "
         "vulnerabilities of age, disability or social or economic situation; social scoring "
         "leading to detrimental treatment in unrelated contexts or disproportionate to the "
         "behaviour; individual criminal-offence risk prediction based solely on profiling or "
         "personality traits; untargeted scraping of facial images from the internet or CCTV to "
         "build facial-recognition databases; emotion inference in the workplace or in "
         "education outside medical or safety reasons; biometric categorisation to deduce race, "
         "political opinions, trade union membership, religious or philosophical beliefs, sex "
         "life or sexual orientation; and real-time remote biometric identification in publicly "
         "accessible spaces for law enforcement, save the narrow listed exceptions.",
         "critical", "All AI operators", "economic_operator", "2025-02-02"),

        ("Article 4 (AI literacy)",
         "Ensure a sufficient level of AI literacy among staff and others operating AI systems "
         "on your behalf, taking into account their technical knowledge, experience, education "
         "and training and the context the systems are used in. This applies to every provider "
         "and deployer regardless of risk tier, and is one of the first duties to bite.",
         "important", "All AI providers and deployers", "economic_operator", "2025-02-02"),

        ("Article 50 (transparency to people)",
         "Tell people when they are dealing with AI. Systems interacting directly with natural "
         "persons must disclose that fact unless it is obvious to a reasonably observant person. "
         "Emotion-recognition and biometric-categorisation systems must inform the people "
         "exposed to them. Synthetic audio, image, video or text output must be marked in a "
         "machine-readable format as artificially generated or manipulated, and deep fakes and "
         "AI-generated text published to inform the public on matters of public interest must be "
         "disclosed as such. This binds most consumer-facing startups even when nothing they "
         "build is high-risk.",
         "critical", "Providers and deployers of interactive or generative AI",
         "economic_operator", "2026-08-02"),

        ("Arts 9, 10, 15 (risk, data, robustness)",
         "If the system is high-risk, run a continuous iterative risk management system across "
         "its lifecycle; govern training, validation and testing data for relevance, "
         "representativeness, and to the extent possible freedom from errors and completeness, "
         "examining it for bias that could affect health, safety or fundamental rights; and "
         "achieve appropriate accuracy, robustness and cybersecurity, declaring the accuracy "
         "metrics in the instructions for use.",
         "critical", "Providers of high-risk AI systems", "economic_operator", "2026-08-02"),

        ("Arts 11-14 (docs, logs, oversight)",
         "If the system is high-risk, draw up the Annex IV technical documentation before "
         "placing it on the market and keep it current; design the system to log events "
         "automatically over its lifetime; make it transparent enough that deployers can "
         "interpret and use the output, with instructions for use; and design it so natural "
         "persons can effectively oversee it, including the ability to intervene or stop it.",
         "critical", "Providers of high-risk AI systems", "economic_operator", "2026-08-02"),

        ("Arts 16, 43, 47-49 (QMS, conformity)",
         "If the system is high-risk, operate a documented quality management system, carry out "
         "the Article 43 conformity assessment (for most Annex III systems this is the "
         "provider's own internal-control assessment, not a notified body), draw up the EU "
         "declaration of conformity, affix CE marking, and register the system in the EU "
         "database before placing it on the market or putting it into service.",
         "critical", "Providers of high-risk AI systems", "economic_operator", "2026-08-02"),

        ("Article 25 (you become the provider)",
         "Understand when you inherit the full provider obligations for a system someone else "
         "built. A distributor, importer, deployer or other third party becomes the provider of "
         "a high-risk system if it puts its name or trade mark on it, makes a substantial "
         "modification to it, or modifies the intended purpose of a system, including a "
         "general-purpose AI system, such that it becomes high-risk. Building a product on top "
         "of a third-party model is the single most common way a startup acquires these duties "
         "without noticing.",
         "critical", "Anyone rebranding or modifying an AI system", "economic_operator",
         "2026-08-02"),

        ("Arts 26-27 (deploying high-risk AI)",
         "If you deploy a high-risk system rather than build one, use it in accordance with the "
         "instructions for use, assign human oversight to people with the competence, training "
         "and authority to exercise it, ensure input data is relevant and sufficiently "
         "representative for the intended purpose, keep the automatically generated logs for at "
         "least six months, and inform workers' representatives before putting a system into "
         "service in the workplace. Bodies governed by public law, private entities providing "
         "public services, and deployers running creditworthiness or life and health insurance "
         "pricing must also complete a fundamental rights impact assessment.",
         "important", "Deployers of high-risk AI systems", "economic_operator", "2026-08-02"),

        ("Article 53 (general-purpose models)",
         "If you place a general-purpose AI model on the market, keep and maintain the technical "
         "documentation in Annex XI, provide downstream providers with the Annex XII information "
         "they need to meet their own obligations, put in place a policy to comply with Union "
         "copyright law including the Article 4(3) text-and-data-mining reservation, and publish "
         "a sufficiently detailed public summary of the content used for training, following the "
         "AI Office template. Fine-tuning an existing model can make you the provider of that "
         "modified model.",
         "critical", "Providers of general-purpose AI models", "economic_operator", "2025-08-02"),

        ("Arts 51, 52, 55 (systemic risk)",
         "Know the threshold even if you are nowhere near it. A general-purpose AI model is "
         "presumed to carry systemic risk when the cumulative compute used for training exceeds "
         "10^25 floating-point operations, and the provider must notify the Commission within "
         "two weeks of meeting or expecting to meet it. Models with systemic risk carry "
         "additional duties: model evaluation including adversarial testing, systemic risk "
         "assessment and mitigation, serious-incident reporting to the AI Office, and adequate "
         "cybersecurity protection.",
         "recommended", "Providers of general-purpose AI models", "economic_operator",
         "2025-08-02", True),

        ("Arts 57, 62 (sandboxes, SME support)",
         "Use the support the Regulation creates for small companies rather than absorbing the "
         "full compliance cost alone. Each Member State must have at least one AI regulatory "
         "sandbox operational by 2 August 2026, and SMEs including startups have priority access "
         "to it free of charge. Member States must also provide dedicated awareness and training "
         "channels, and the Commission provides standardised technical documentation forms for "
         "SMEs. This is an opportunity, not an obligation, and never counts as a gap.",
         "recommended", "SMEs and startups", "economic_operator", "2026-08-02", True),

        ("Article 99 (penalties)",
         "Price the risk. Breaching the Article 5 prohibitions carries administrative fines up "
         "to EUR 35 000 000 or 7% of total worldwide annual turnover for the preceding financial "
         "year, whichever is higher. Most other infringements reach EUR 15 000 000 or 3%, and "
         "supplying incorrect, incomplete or misleading information to authorities EUR 7 500 000 "
         "or 1%. For SMEs including startups each ceiling is the lower of the percentage and the "
         "fixed amount, not the higher.",
         "recommended", "All AI operators", "economic_operator", "2026-08-02", True),
    ]),

    # ------------------------------------------------------------------ GDPR
    ("32016R0679", [
        ("Arts 5, 6, 9 (basis for training data)",
         "Identify and document the lawful basis for every use of personal data in training, "
         "fine-tuning and evaluation, and respect purpose limitation and data minimisation. "
         "Where the basis is legitimate interests, record the balancing test. Special-category "
         "data, including biometric data processed to uniquely identify someone, needs an "
         "Article 9(2) condition on top. Scraped web data is personal data whenever people are "
         "identifiable in it.",
         "critical", "AI developers processing personal data", "economic_operator", None),

        ("Article 35 (DPIA)",
         "Carry out a DPIA before processing likely to result in a high risk to individuals, "
         "which expressly covers systematic and extensive automated evaluation of personal "
         "aspects producing legal or similarly significant effects, large-scale processing of "
         "special-category data, and systematic large-scale monitoring of publicly accessible "
         "areas. Most AI products serving consumers meet at least one limb. Where a fundamental "
         "rights impact assessment is also required under the AI Act, the two can be run "
         "together rather than duplicated.",
         "critical", "Controllers deploying AI on personal data", "economic_operator", None),

        ("Article 22 (automated decisions)",
         "A person has the right not to be subject to a decision based solely on automated "
         "processing, including profiling, that produces legal effects or similarly "
         "significantly affects them, unless it is necessary for a contract, authorised by law, "
         "or based on explicit consent. Where an exception applies, provide meaningful "
         "information about the logic involved and safeguard the right to obtain human "
         "intervention, to express a point of view and to contest the decision.",
         "critical", "Controllers making automated decisions", "economic_operator", None),

        ("Arts 15-17, 20 (subject rights)",
         "Be able to answer access, rectification, erasure and portability requests for data "
         "used in AI systems. Decide in advance how you will locate an individual's data across "
         "training sets, embeddings and logs, since an architecture that makes this impossible "
         "does not remove the obligation.",
         "important", "Controllers processing personal data", "economic_operator", None),

        ("Arts 25, 32 (by design, security)",
         "Implement data protection by design and by default, and security appropriate to the "
         "risk. For AI this includes pseudonymisation where it does not defeat the purpose, "
         "access controls over training data and model artefacts, and consideration of "
         "model-specific attacks such as membership inference, model inversion and training-data "
         "extraction.",
         "important", "Controllers and processors", "economic_operator", None),
    ]),

    # -------------------------------------------------------------- Data Act
    ("32023R2854", [
        ("Arts 3-4 (connected product data)",
         "If your product is a connected product or a related service, design it so that product "
         "data and related service data are, by default, accessible to the user easily, securely, "
         "free of charge, in a comprehensive, structured, commonly used and machine-readable "
         "format and, where relevant and technically feasible, directly. Tell the user before "
         "contracting what data the product generates, in what volume and how to access it.",
         "important", "Manufacturers of connected products", "economic_operator", "2025-09-12"),

        ("Arts 23-26, 29 (cloud switching)",
         "If you provide a data processing service, remove the commercial, technical, "
         "contractual and organisational obstacles to a customer switching to another provider "
         "or to on-premises infrastructure. Switching charges were reduced from 12 January 2024 "
         "and are withdrawn entirely from 12 January 2027.",
         "important", "Providers of cloud and edge services", "economic_operator", "2025-09-12"),
    ]),

    # ---------------------------------------- Product Liability Directive
    ("32024L2853", [
        ("Arts 4, 6 (software is a product)",
         "Software, including AI systems and standalone software, is a product for liability "
         "purposes, and a defect can arise from the product's effect on other products, from its "
         "learning after deployment, or from a failure to supply software updates or security "
         "patches needed to maintain safety. A manufacturer stays liable for defects arising "
         "after the product is placed on the market where it retains control over updates or "
         "upgrades.",
         "important", "Software and AI manufacturers", "economic_operator", "2026-12-09"),

        ("Arts 9-10 (disclosure, presumption)",
         "Expect the evidential burden to shift. A court can order you to disclose relevant "
         "evidence, and defectiveness is presumed where you fail to comply with that order, "
         "where the claimant shows the product breached mandatory safety requirements, or where "
         "the technical or scientific complexity makes it excessively difficult for the claimant "
         "to prove defectiveness or causation. Keep the design, testing and update records that "
         "would answer such an order.",
         "important", "Software and AI manufacturers", "economic_operator", "2026-12-09"),
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
        cname = db.execute(text("SELECT name FROM law_clusters WHERE id=:c"),
                           {"c": CLUSTER_ID}).scalar()
        if not cname:
            print(f"[ERROR] cluster {CLUSTER_ID} not found")
            return 1
        print(f"cluster {CLUSTER_ID}: {cname}\n")

        # Refuse to run destructively if anyone has actually used the cluster.
        used = db.execute(text("""
            SELECT count(*) FROM gap_findings g
              JOIN law_requirements r ON r.id = g.requirement_id
             WHERE r.cluster_id = :c"""), {"c": CLUSTER_ID}).scalar()
        if used:
            print(f"[ABORT] {used} gap_findings reference this cluster's requirements. "
                  "Deleting them would erase analysis history. Re-point the findings first.")
            return 1
        plan.append("0 gap_findings depend on the requirements being replaced")

        # 1. Detach the wrong laws and delete their requirements from this cluster.
        for celex, why in DETACH_CELEX.items():
            lid = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                             {"x": celex}).scalar()
            if not lid:
                continue
            n = db.execute(text("""SELECT count(*) FROM law_requirements
                                    WHERE cluster_id=:c AND law_id=:l"""),
                           {"c": CLUSTER_ID, "l": lid}).scalar()
            other = db.execute(text("""SELECT count(*) FROM cluster_laws
                                        WHERE law_id=:l AND cluster_id<>:c"""),
                               {"l": lid, "c": CLUSTER_ID}).scalar()
            plan.append(f"DETACH {celex} ({why}); drop {n} requirements; "
                        f"law stays in {other} other cluster(s)")
            db.execute(text("DELETE FROM law_requirements WHERE cluster_id=:c AND law_id=:l"),
                       {"c": CLUSTER_ID, "l": lid})
            db.execute(text("DELETE FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                       {"c": CLUSTER_ID, "l": lid})

        # 2. Attach the right laws.
        law_ids = {}
        for celex in ATTACH:
            lid = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                             {"x": celex}).scalar()
            if not lid:
                print(f"[ERROR] {celex} not in eu_laws; cannot continue")
                db.rollback()
                return 1
            law_ids[celex] = lid
            exists = db.execute(text("""SELECT 1 FROM cluster_laws
                                         WHERE cluster_id=:c AND law_id=:l"""),
                                {"c": CLUSTER_ID, "l": lid}).scalar()
            if not exists:
                db.execute(text("""INSERT INTO cluster_laws (cluster_id, law_id)
                                   VALUES (:c, :l)"""), {"c": CLUSTER_ID, "l": lid})
                plan.append(f"ATTACH {celex} (law_id {lid})")

        # 3. Seed the curated requirements, skipping any already present.
        added = 0
        for celex, reqs in REQUIREMENTS:
            lid = law_ids[celex]
            for spec in reqs:
                article, body, crit, entity, addressee, applies_from = spec[:6]
                interpretive = len(spec) > 6 and spec[6]
                # article is varchar(50) and applicable_entity varchar(100).
                # Fail here with the offending label rather than deep inside an
                # INSERT with a truncated psycopg2 message.
                if len(article) > 50 or len(entity) > 100:
                    print(f"[ERROR] label too long for the column: {article!r} "
                          f"({len(article)}/50), entity {len(entity)}/100")
                    db.rollback()
                    return 1
                dupe = db.execute(text("""SELECT 1 FROM law_requirements
                                           WHERE cluster_id=:c AND law_id=:l AND article=:a"""),
                                  {"c": CLUSTER_ID, "l": lid, "a": article}).scalar()
                if dupe:
                    continue
                db.execute(text("""
                    INSERT INTO law_requirements
                        (law_id, cluster_id, article, requirement_text, criticality,
                         applicable_entity, deadline, extra_metadata)
                    VALUES
                        (:l, :c, :a, :t, :crit, :entity, :deadline,
                         CAST(:meta AS jsonb))"""),
                    {"l": lid, "c": CLUSTER_ID, "a": article, "t": body, "crit": crit,
                     "entity": entity, "deadline": applies_from,
                     "meta": __import__("json").dumps(
                         {**SEED_TAG, "law_celex": celex, "addressee": addressee,
                          **({"interpretive": "true"} if interpretive else {})})})
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
                   count(*) FILTER (WHERE r.criticality='critical') AS crit
              FROM law_requirements r JOIN eu_laws l ON l.id=r.law_id
             WHERE r.cluster_id=:c GROUP BY l.celex ORDER BY n DESC"""),
            {"c": CLUSTER_ID}).fetchall()
        total = sum(r[1] for r in rows)
        print(f"\n[OK] committed. Cluster {CLUSTER_ID} now holds {total} requirements:")
        for celex, n, crit in rows:
            print(f"  {celex}  {n:>3} requirements ({crit} critical)")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
