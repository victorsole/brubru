"""One-shot ingest of the Cyber Resilience Act into eu_laws, and seed it into the SaaS cluster.

Why this exists
---------------
Regulation (EU) 2024/2847, the Cyber Resilience Act, was missing from `eu_laws`
entirely. Only two corrigenda to it were present, both carrying no requirements,
which is a bad failure mode: the cluster card counted them as "laws covered"
while nothing under them could ever be checked. The CRA is the horizontal
regime for anyone placing software with digital elements on the EU market, so
its absence was the largest single hole in cluster 21, "SaaS & B2B Startup
Compliance".

Source
------
Every fact below is read from the Formex text in the November 2025 bulk export,
not from recollection or a summary:

  docs/LEG_2025-11/21b7d4eb-a6e2-11ef-85f0-01aa75ed71a1/fmx4/
      L_202402847EN.000101.fmx.xml     71 articles, main operative text

Verified from that file: the application dates in Article 71 (the Regulation
applies from 11 December 2027, Article 14 from 11 September 2026, Chapter IV
from 11 June 2026), the five-year minimum support period in Article 13(8), the
24-hour and 72-hour clocks in Article 14(2), and the penalty ceilings in Article
64 (EUR 15 000 000 or 2.5% for Annex I and Articles 13 and 14).

Why a raw INSERT and not the ORM
--------------------------------
`eu_laws.search_vector` is GENERATED ALWAYS in Postgres but declared writable on
the model, so any ORM insert raises. The fix is an explicit column list that
omits it. `corpus_version` is varchar(20), which 'LEG_2025-11' fits.

Usage:
  python3.12 -m scripts._ingest_cra_oneshot --dry-run
  python3.12 -m scripts._ingest_cra_oneshot --apply
"""
import argparse
import json
import sys
import uuid as _uuid
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

CELEX = "32024R2847"
TITLE = (
    "Regulation (EU) 2024/2847 of the European Parliament and of the Council of "
    "23 October 2024 on horizontal cybersecurity requirements for products with "
    "digital elements and amending Regulations (EU) No 168/2013 and (EU) "
    "2019/1020 and Directive (EU) 2020/1828 (Cyber Resilience Act)"
)
DATE = "2024-10-23"
OJ_REFERENCE = "OJ L, 2024/2847, 20.11.2024"
DOC_TYPE = "Regulation"
POLICY_AREA = "Digital Policy and Digital Economy"
CORPUS_VERSION = "LEG_2025-11"
XML_PATH = ("docs/LEG_2025-11/21b7d4eb-a6e2-11ef-85f0-01aa75ed71a1/fmx4/"
            "L_202402847EN.000101.fmx.xml")

SAAS_CLUSTER = 21
SEED_TAG = {"source": "_ingest_cra_oneshot", "curated": True}

# article (<=50), text, criticality, applicable_entity (<=100), deadline, interpretive
REQUIREMENTS = [
    ("Arts 2-3 (does the CRA reach your product?)",
     "Establish scope first. The Regulation applies to products with digital elements made "
     "available on the market whose intended purpose or reasonably foreseeable use includes a "
     "direct or indirect logical or physical data connection to a device or network. That "
     "captures software as well as hardware, so a hosted product distributed as software is in "
     "scope where it is placed on the market as a product. It does not apply to products "
     "covered by the medical devices Regulations 2017/745 and 2017/746, by Regulation 2019/2144 "
     "on vehicle type-approval, to products certified under Regulation 2018/1139 on aviation, "
     "or to marine equipment under Directive 2014/90/EU. A pure service, as opposed to a "
     "product placed on the market, sits outside it. Record the conclusion either way.",
     "critical", "Manufacturers of products with digital elements", None, False),

    ("Art 6 + Annex I (essential requirements)",
     "Design, develop and produce the product in accordance with the essential cybersecurity "
     "requirements in Part I of Annex I: delivered with a secure by default configuration and "
     "the ability to reset to it, protection from unauthorised access with appropriate "
     "authentication, confidentiality and integrity of stored, transmitted and processed data, "
     "processing only the data adequate, relevant and limited to what is necessary, protection "
     "of the availability of essential functions, minimisation of attack surfaces, reduction of "
     "the impact of incidents, recording and monitoring of relevant internal activity, and the "
     "ability to apply security updates including, where applicable, automatic updates with an "
     "opt-out. Part II adds the vulnerability handling requirements.",
     "critical", "Manufacturers of products with digital elements", "2027-12-11", False),

    ("Art 13(1)-(3) (risk assessment, documented)",
     "Undertake an assessment of the cybersecurity risks associated with the product and take "
     "its outcome into account in the planning, design, development, production, delivery and "
     "maintenance phases. The assessment must be documented and updated as appropriate "
     "throughout the support period, and must analyse risks based on the intended purpose, "
     "reasonably foreseeable use and conditions of use, and state whether and how each Annex I "
     "Part I point (2) security requirement applies and is implemented.",
     "critical", "Manufacturers of products with digital elements", "2027-12-11", False),

    ("Art 13(8) (support period, minimum five years)",
     "Determine and state a support period reflecting how long the product is expected to be in "
     "use, during which vulnerabilities are handled. The support period must be at least five "
     "years, unless the product is expected to be in use for less, in which case it matches the "
     "expected use time. This is a commercial commitment as much as a legal one: it fixes how "
     "long security updates must be produced for versions already sold.",
     "critical", "Manufacturers of products with digital elements", "2027-12-11", False),

    ("Annex I Part II (vulnerability handling)",
     "Handle vulnerabilities for the duration of the support period: identify and document "
     "components in a software bill of materials covering at least the top-level dependencies; "
     "address and remediate vulnerabilities without delay, including by providing security "
     "updates; apply regular tests and reviews; publicly disclose information about fixed "
     "vulnerabilities once available; put in place and enforce a coordinated vulnerability "
     "disclosure policy; provide a contact address for reporting; and distribute security "
     "updates without delay and free of charge, separately from functionality updates where "
     "technically feasible.",
     "critical", "Manufacturers of products with digital elements", "2027-12-11", False),

    ("Art 14 (24h / 72h vulnerability + incident report)",
     "Notify any actively exploited vulnerability, and any severe incident having an impact on "
     "the security of the product, simultaneously to the CSIRT designated as coordinator and to "
     "ENISA through the single reporting platform. The clock is an early warning without undue "
     "delay and in any event within 24 hours of becoming aware, then a fuller notification "
     "within 72 hours giving the general nature of the exploit and any corrective or mitigating "
     "measures taken and available to users. This obligation starts well before the rest of the "
     "Regulation, on 11 September 2026.",
     "critical", "Manufacturers of products with digital elements", "2026-09-11", False),

    ("Arts 28, 30-31 (declaration, CE marking, docs)",
     "Draw up the EU declaration of conformity stating that the essential requirements are met, "
     "affix the CE marking visibly, legibly and indelibly before placing the product on the "
     "market, and prepare the technical documentation before doing so, keeping it and the "
     "declaration at the disposal of market surveillance authorities for at least ten years "
     "after placing on the market or for the support period, whichever is longer.",
     "critical", "Manufacturers of products with digital elements", "2027-12-11", False),

    ("Arts 7-8 + 32 (which conformity route applies)",
     "Determine which conformity assessment route the product needs. For products that are "
     "neither important nor critical, the manufacturer's own internal control procedure under "
     "module A is enough. Important products in Annex III class I may use internal control only "
     "where harmonised standards or a European cybersecurity certification scheme are applied "
     "in full, and otherwise need a third party; class II always needs a third-party route. "
     "Critical products in Annex IV may be required to hold a European cybersecurity "
     "certificate at assurance level at least substantial. Getting this wrong is the difference "
     "between self-assessment and a notified body.",
     "critical", "Manufacturers of products with digital elements", "2027-12-11", False),

    ("Art 24 (open-source software stewards)",
     "If the company acts as an open-source software steward, meaning a legal person other than "
     "a manufacturer that systematically provides sustained support for the development of "
     "specific open-source products intended for commercial activities, put in place and "
     "document in a verifiable manner a cybersecurity policy fostering secure development, "
     "effective vulnerability handling and voluntary reporting. The steward regime is lighter "
     "than the manufacturer regime, and merely contributing to open source does not create it.",
     "recommended", "Open-source software stewards", "2027-12-11", False),

    ("Arts 19-22 (importer, distributor, or maker?)",
     "Know which role the company holds, because the manufacturer's full obligations attach to "
     "an importer or distributor that places a product on the market under its own name or "
     "trade mark, or that carries out a substantial modification of a product already placed on "
     "the market. Rebranding or materially modifying third-party software makes the company the "
     "manufacturer of it.",
     "important", "Importers, distributors and modifiers", "2027-12-11", False),

    ("Art 71 (when each duty starts)",
     "The Regulation entered into force on 10 December 2024 and applies from 11 December 2027. "
     "Two parts start earlier: the Article 14 reporting obligations from 11 September 2026, and "
     "Chapter IV on notification of conformity assessment bodies from 11 June 2026. Work back "
     "from December 2027 for design and conformity work, and from September 2026 for the "
     "reporting pipeline.",
     "recommended", "Manufacturers of products with digital elements", "2026-09-11", True),

    ("Art 64 (penalties)",
     "Non-compliance with the Annex I essential requirements or the Article 13 and 14 "
     "obligations carries administrative fines up to EUR 15 000 000 or, for an undertaking, "
     "2.5% of total worldwide annual turnover for the preceding financial year, whichever is "
     "higher. The obligations in Articles 18 to 23, 28, 30, 31, 32, 33(5), 39, 41, 47, 49 and 53 "
     "reach EUR 10 000 000 or 2%, and supplying incorrect, incomplete or misleading information "
     "to notified bodies or market surveillance authorities EUR 5 000 000 or 1%.",
     "recommended", "Manufacturers of products with digital elements", None, True),

    ("Art 33 (support for SMEs and start-ups)",
     "Member States must, where appropriate, run awareness-raising and training on the "
     "Regulation tailored to microenterprises and small enterprises, establish a dedicated "
     "communication channel for advice and queries, and support testing and conformity "
     "assessment procedures. This is an offer to use, not a duty to discharge, and never counts "
     "as a gap.",
     "recommended", "SMEs and start-ups", None, True),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    src = project_root / XML_PATH
    if not src.exists():
        print(f"[ERROR] source Formex file missing: {XML_PATH}")
        return 1

    db = SessionLocal()
    plan = []
    try:
        law_id = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                            {"x": CELEX}).scalar()
        if law_id:
            plan.append(f"eu_laws row already present (id {law_id})")
        else:
            # Explicit column list: search_vector is GENERATED ALWAYS and must
            # not appear, which is why the ORM cannot be used here.
            law_id = db.execute(text("""
                INSERT INTO eu_laws
                    (uuid, celex, doc_type, doc_type_normalized, title, date,
                     oj_reference, policy_area, xml_path, is_primary_legislation,
                     corpus_version, corpus_status, extra_metadata)
                VALUES
                    (:uuid, :celex, :doc_type, :doc_type, :title, :date,
                     :oj, :area, :xml, true,
                     :cv, 'active', CAST(:meta AS jsonb))
                RETURNING id"""),
                {"uuid": str(_uuid.uuid4()), "celex": CELEX, "doc_type": DOC_TYPE,
                 "title": TITLE, "date": DATE, "oj": OJ_REFERENCE,
                 "area": POLICY_AREA, "xml": XML_PATH, "cv": CORPUS_VERSION,
                 "meta": json.dumps({"short_name": "Cyber Resilience Act",
                                     "articles": 71,
                                     "ingested_by": "_ingest_cra_oneshot"})}).scalar()
            plan.append(f"INSERT eu_laws {CELEX} -> id {law_id}")

        if not db.execute(text("SELECT 1 FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                          {"c": SAAS_CLUSTER, "l": law_id}).scalar():
            db.execute(text("INSERT INTO cluster_laws (cluster_id, law_id) VALUES (:c,:l)"),
                       {"c": SAAS_CLUSTER, "l": law_id})
            plan.append(f"ATTACH to cluster {SAAS_CLUSTER}")

        added = interp = 0
        for article, body, crit, entity, deadline, interpretive in REQUIREMENTS:
            if len(article) > 50 or len(entity) > 100:
                print(f"[ERROR] label too long: {article!r} ({len(article)}/50), "
                      f"entity {len(entity)}/100")
                db.rollback()
                return 1
            if db.execute(text("""SELECT 1 FROM law_requirements
                                   WHERE cluster_id=:c AND law_id=:l AND article=:a"""),
                          {"c": SAAS_CLUSTER, "l": law_id, "a": article}).scalar():
                continue
            meta = {**SEED_TAG, "law_celex": CELEX, "addressee": "economic_operator"}
            if interpretive:
                meta["interpretive"] = "true"
                interp += 1
            db.execute(text("""
                INSERT INTO law_requirements
                    (law_id, cluster_id, article, requirement_text, criticality,
                     applicable_entity, deadline, extra_metadata)
                VALUES (:l,:c,:a,:t,:crit,:e,:d, CAST(:m AS jsonb))"""),
                {"l": law_id, "c": SAAS_CLUSTER, "a": article, "t": body,
                 "crit": crit, "e": entity, "d": deadline, "m": json.dumps(meta)})
            added += 1
        plan.append(f"INSERT {added} requirements ({interp} interpretive)")

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
            {"c": SAAS_CLUSTER}).fetchall()
        print(f"\n[OK] committed. Cluster {SAAS_CLUSTER}:")
        for celex, n, binding in rows:
            print(f"  {celex}  {n} requirements ({binding} binding)")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
