"""Seed the ESPR / Digital Product Passport layer of the TEX (textiles) compliance cluster.

Context
-------
Cluster 58 was seeded on 5 August 2026 from Directive (EU) 2025/1892 only (textile EPR +
food waste). That covers the *waste* side of a textile producer's obligations and nothing
of the *product* side. A textile client building a Digital Product Passport (e.g. the LIFE
DPP-TEX consortium, LIFE-2025-SAP-ENV topic 1.1.1(g) "separate collection, preparation for
re-use and recycling of textiles, including mattresses and footwear", whose footnote 21
scopes it to "characterisation and product passport approaches") needs the ESPR chain.

This script adds that chain, curated from a full sequential read of the operative text of
each act via Cellar (not from summaries):

  32024R1781  Regulation (EU) 2024/1781 (ESPR)                      already in eu_laws (id 11447)
  32026R0002  Commission Implementing Regulation (EU) 2026/2        disclosure of discarded unsold products
  32026R0296  Commission Delegated Regulation (EU) 2026/296         derogations from the destruction ban
  32026R1778  Commission Implementing Regulation (EU) 2026/1778     digital product passport registry

It also splits the three food-waste obligations out of cluster 58 into their own cluster:
a textile producer running a gap analysis should not be scored against Article 9a food
waste reduction targets.

Honest scope note (do NOT let this drift into a promise)
--------------------------------------------------------
There is **no adopted ESPR product-specific delegated act for textiles yet**. The ESPR and
Energy Labelling Working Plan 2025-2030 (COM(2025) 187) ranks Textiles/Apparel 1st with an
*indicative* adoption timeline of 2027, and treats footwear as a separate product category
for which only a study is commissioned during the working-plan period. So today the binding
textile obligations are the destruction ban (Art 25 + Annex VII, from 19 July 2026), the
disclosure duty (Art 24 + IR 2026/2, from 2 March 2027) and the horizontal DPP registry
rules that will govern the textile DPP once the delegated act lands. Requirement R-ESPR-18
below states exactly that and is marked 'recommended' so it never inflates a gap score.

Verified IDs before writing:
  SELECT id FROM eu_laws WHERE celex='32024R1781';                    -> 11447
  SELECT id FROM eu_laws WHERE celex='32025L1892';                    -> 15039
  SELECT id, name FROM law_clusters WHERE id=58;                      -> Textile EPR and Food Waste Package

Usage:
  python3.12 -m backend.scripts._seed_dpp_tex_requirements --dry-run
  python3.12 -m backend.scripts._seed_dpp_tex_requirements --apply
"""
import argparse
import json as _json
import sys
import uuid as _uuid
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from backend.core.database import SessionLocal
from backend.models.eu_law import ClusterLaw, EULaw, LawCluster, LawRequirement

TEX_CLUSTER_ID = 58
ESPR_CELEX = "32024R1781"
WFD_AMEND_CELEX = "32025L1892"

SEED_TAG = {"source": "dpp_tex_curated_seed", "seeded_at": "2026-08-08"}

# ---------------------------------------------------------------------------
# 1. Laws to register (post-LEG_2025-11 corpus, so hand-registered)
# ---------------------------------------------------------------------------

NEW_LAWS = [
    {
        "celex": "32026R0002",
        "doc_type": "Regulation",
        "title": (
            "Commission Implementing Regulation (EU) 2026/2 of 9 February 2026 laying down "
            "rules for the application of Regulation (EU) 2024/1781 of the European Parliament "
            "and of the Council as regards the details and format for the disclosure of "
            "information on discarded unsold consumer products"
        ),
        "date": date(2026, 2, 9),
        "oj_reference": "OJ L, 2026/2, 10.2.2026",
        "relationship_type": "implementing",
    },
    {
        "celex": "32026R0296",
        "doc_type": "Regulation",
        "title": (
            "Commission Delegated Regulation (EU) 2026/296 of 9 February 2026 supplementing "
            "Regulation (EU) 2024/1781 of the European Parliament and of the Council by setting "
            "out derogations from the prohibition of destruction of unsold consumer products"
        ),
        "date": date(2026, 2, 9),
        "oj_reference": "OJ L, 2026/296, 2026",
        "relationship_type": "delegated",
    },
    {
        "celex": "32026R1778",
        "doc_type": "Regulation",
        "title": (
            "Commission Implementing Regulation (EU) 2026/1778 of 16 July 2026 laying down the "
            "implementation arrangements for the digital product passport registry set up under "
            "Regulation (EU) 2024/1781 of the European Parliament and of the Council"
        ),
        "date": date(2026, 7, 16),
        "oj_reference": "OJ L, 2026/1778, 2026",
        "relationship_type": "implementing",
    },
]

# ---------------------------------------------------------------------------
# 2. Requirements, keyed by the CELEX of the act they come from
# ---------------------------------------------------------------------------

TEXTILE_ENTITY = "Producers, importers and distributors of apparel, clothing accessories and footwear"

REQUIREMENTS = {
    ESPR_CELEX: [
        {
            "article": "Article 25(1), Annex VII",
            "requirement_text": (
                "From 19 July 2026 the destruction of unsold consumer products listed in Annex VII "
                "is prohibited. Annex VII covers, by Combined Nomenclature code as in force on "
                "28 June 2024: apparel and clothing accessories (4203 leather articles, chapter 61 "
                "knitted or crocheted, chapter 62 not knitted or crocheted, 6504 and 6505 headgear) "
                "and footwear (6401 to 6405). The prohibition does not apply to micro and small "
                "enterprises, and applies to medium-sized enterprises only from 19 July 2030."
            ),
            "criticality": "critical",
            "applicable_entity": TEXTILE_ENTITY,
            "deadline": date(2026, 7, 19),
        },
        {
            "article": "Article 25(2)",
            "requirement_text": (
                "Economic operators that are not themselves subject to the destruction prohibition "
                "shall not destroy unsold consumer products supplied to them with the purpose of "
                "circumventing that prohibition. This closes the route of passing unsold stock to an "
                "exempt micro or small entity for disposal."
            ),
            "criticality": "critical",
            "applicable_entity": "All economic operators in the textile and footwear supply chain",
        },
        {
            "article": "Article 24(1)",
            "requirement_text": (
                "Large enterprises that discard unsold consumer products directly, or have them "
                "discarded on their behalf, shall disclose annually: the number and weight of unsold "
                "consumer products discarded during the previous financial year; the reasons for "
                "discarding them; where applicable the derogation relied on; the proportion of "
                "discarded products delivered to each waste treatment operation; and the measures "
                "taken and planned to prevent destruction. Micro and small enterprises are excluded; "
                "medium-sized enterprises are covered from 19 July 2030. The information may instead "
                "be included in sustainability reporting under Article 19a or 29a of Directive 2013/34/EU."
            ),
            "criticality": "critical",
            "applicable_entity": "Large enterprises discarding unsold consumer products",
        },
        {
            "article": "Article 13",
            "requirement_text": (
                "A digital product passport required by a delegated act adopted under Article 4 must "
                "be registered in the digital product passport registry established and maintained by "
                "the Commission. The implementation arrangements for that registry are laid down in "
                "Commission Implementing Regulation (EU) 2026/1778."
            ),
            "criticality": "critical",
            "applicable_entity": "Economic operators placing products with a DPP on the Union market",
        },
        {
            "article": "Article 18, Working Plan 2025-2030",
            "requirement_text": (
                "HORIZON, NOT YET BINDING. Article 18 lists textiles, in particular garments and "
                "footwear, among the priorities for the first ESPR working plan. The Ecodesign for "
                "Sustainable Products and Energy Labelling Working Plan 2025-2030 (COM(2025) 187) "
                "ranks Textiles/Apparel first with an indicative delegated-act adoption timeline of "
                "2027, and states that information will generally be provided in the digital product "
                "passport, working in synergy with the Textile Labelling Regulation currently under "
                "review. Footwear is treated as a separate product category for which only a study is "
                "commissioned during the working-plan period. No product-specific ecodesign or DPP "
                "delegated act for textiles has been adopted at the time of seeding."
            ),
            "criticality": "recommended",
            "applicable_entity": "Textile and apparel manufacturers planning DPP readiness",
        },
    ],
    "32026R0002": [
        {
            "article": "Article 1",
            "requirement_text": (
                "The disclosure obligation applies to products discarded in each financial year as "
                "from the first full financial year after 2 March 2027, the date of application of "
                "this Regulation. Economic operators shall disclose that information within 12 months "
                "after the end of that financial year."
            ),
            "criticality": "critical",
            "applicable_entity": "Large enterprises discarding unsold consumer products",
            "deadline": date(2027, 3, 2),
        },
        {
            "article": "Article 2(1), Annex I",
            "requirement_text": (
                "The visual presentation and content of the disclosure shall comply with the format "
                "set out in Annex I. That format requires, per CN product category: legal entity name "
                "and identifier (EUID or other), standalone or consolidated disclosure, financial year "
                "start and end dates, number of units discarded, total weight in kilograms, whether "
                "packaging is included in that weight, the reason for discarding, and a percentage "
                "split across preparing for reuse, recycling, other recovery, disposal and total "
                "destruction, plus measures taken and planned to prevent destruction."
            ),
            "criticality": "critical",
            "applicable_entity": "Large enterprises discarding unsold consumer products",
        },
        {
            "article": "Article 2(2)",
            "requirement_text": (
                "Operators bound to publish sustainability reporting in their management report under "
                "Article 19a or 29a of Directive 2013/34/EU, or publishing such reports voluntarily, "
                "that include the Annex I format in that reporting may publish a link to the report on "
                "their website instead of disclosing the information on the website directly, provided "
                "the link clearly states where the report contains that information."
            ),
            "criticality": "recommended",
            "applicable_entity": "Enterprises within the scope of CSRD sustainability reporting",
        },
        {
            "article": "Article 3, Annex II",
            "requirement_text": (
                "Disclosure shall be delimited on the first two digits of the relevant Combined "
                "Nomenclature code. The products listed in Annex II must instead be delimited at "
                "four-digit CN level. The Annex II list includes textile and apparel headings: 4203 "
                "(articles of apparel and clothing accessories of leather), 4303 (articles of apparel, "
                "clothing accessories and other articles of furskin), 4818, 6301 (blankets and "
                "travelling rugs), 6302 (bed, table, toilet and kitchen linen), 6303 (curtains and "
                "interior blinds), 6304 (other furnishing articles) and 6306 (tarpaulins, awnings, "
                "tents and sails)."
            ),
            "criticality": "critical",
            "applicable_entity": TEXTILE_ENTITY,
        },
        {
            "article": "Article 4",
            "requirement_text": (
                "Economic operators shall keep the information and documentation necessary to "
                "demonstrate, in accordance with Article 24(2) of Regulation (EU) 2024/1781, the "
                "delivery and reception of discarded unsold consumer products, including statements on "
                "reception and treatment received from waste treatment operators, for five years after "
                "the disclosure of information on those products."
            ),
            "criticality": "important",
            "applicable_entity": "Large enterprises discarding unsold consumer products",
        },
    ],
    "32026R0296": [
        {
            "article": "Article 2",
            "requirement_text": (
                "Unsold consumer products listed in Annex VII to Regulation (EU) 2024/1781 may be "
                "destroyed only where the documentation in Article 3 can be presented and one of ten "
                "circumstances applies: (a) the product is dangerous under Regulation (EU) 2023/988; "
                "(b) it is unfit for purpose through non-compliance with Union or national law and "
                "destruction is required by law or is the appropriate and proportionate corrective "
                "action; (c) it infringes intellectual property rights as established by a final "
                "judicial or ADR decision, a right-holder or authority notification, or a "
                "substantiated internal investigation; (d) a licence or contractual IP requirement has "
                "expired making further transfer an infringement; (e) removing protected or "
                "inappropriate labels, logos or recognisable design is technically unfeasible; (f) the "
                "product is unacceptable for consumer use through damage, deterioration or "
                "contamination and repair or refurbishment is not technically feasible or "
                "cost-effective; (g) design or manufacturing defects make repair technically "
                "unfeasible; (h) the donation route in Article 2(h) has been exhausted; (i) a social "
                "economy entity received it as a donation but found no recipient; (j) it was placed on "
                "the market after preparing for reuse by a waste treatment operator but found no "
                "recipient. This Regulation applies from 19 July 2026."
            ),
            "criticality": "critical",
            "applicable_entity": TEXTILE_ENTITY,
            "deadline": date(2026, 7, 19),
        },
        {
            "article": "Article 2(h)",
            "requirement_text": (
                "Where none of the circumstances in points (a) to (g) applies, destruction is lawful "
                "only if the product was first offered for donation either directly to at least three "
                "suitable social economy entities located within the Union, or on an easily accessible "
                "page of the economic operator's website, for a period of at least eight weeks, and was "
                "not accepted for donation. 'Social economy entity' takes the meaning in Article 3(4i) "
                "of Directive 2008/98/EC. Build the eight-week clock and the three-entity offer into "
                "the unsold-stock process rather than treating it as an after-the-fact justification."
            ),
            "criticality": "critical",
            "applicable_entity": TEXTILE_ENTITY,
        },
        {
            "article": "Article 3",
            "requirement_text": (
                "For five years after a product subject to a derogation has been destroyed, economic "
                "operators shall keep and, on request, put at the disposal of competent authorities in "
                "electronic form within 30 days of receipt of the request, the documentation "
                "substantiating the derogation relied on, unless the information is already available "
                "to the competent national authority under another legal act."
            ),
            "criticality": "important",
            "applicable_entity": TEXTILE_ENTITY,
        },
    ],
    "32026R1778": [
        {
            "article": "Article 4",
            "requirement_text": (
                "Before it can register a digital product passport, an economic operator must be "
                "qualified as a 'verified economic operator'. A legal person established in the Union "
                "does so by submitting evidence of identity and establishment by means of a qualified "
                "electronic seal supported by a qualified certificate issued by a qualified trust "
                "service provider under Regulation (EU) No 910/2014, or by a qualified electronic "
                "attestation of attributes. A sole trader uses a qualified electronic signature or an "
                "eIDAS electronic identification means at assurance level 'high'. Procure the eIDAS "
                "qualified seal or signature as a lead-time item; it is a precondition, not a "
                "formality."
            ),
            "criticality": "critical",
            "applicable_entity": "Economic operators registering a DPP in the Commission registry",
        },
        {
            "article": "Article 8(1)-(2)",
            "requirement_text": (
                "The digital product passport shall be registered by the verified economic operator "
                "placing the product on the market or putting it into service, at the granularity "
                "level (model, batch or item) specified in the applicable delegated act adopted under "
                "Article 4 of Regulation (EU) 2024/1781. Where Union law allows a third party to act "
                "in the registry on the operator's behalf, that third party must itself be verified."
            ),
            "criticality": "critical",
            "applicable_entity": "Economic operators registering a DPP in the Commission registry",
        },
        {
            "article": "Article 8(3)-(5)",
            "requirement_text": (
                "Where the same product is subject to different Union rules requiring registration at "
                "different levels of granularity, the passport shall be registered at the most granular "
                "level required by any of them. A passport created at item level must link both the "
                "batch and the model identifier where batch and model designs exist; a passport created "
                "at batch level must link the model identifier where a model design exists. Design the "
                "identifier hierarchy up front: retrofitting item-level linkage across an existing "
                "catalogue is materially harder than building it in."
            ),
            "criticality": "important",
            "applicable_entity": "Economic operators registering a DPP in the Commission registry",
        },
        {
            "article": "Article 9",
            "requirement_text": (
                "An economic operator that has registered a digital product passport shall be able to "
                "generate proof of registration at any time. The proof is a secure electronic document "
                "downloadable from the registry containing at least the unique product identifier, "
                "where relevant the commodity code, the name and identity of the responsible verified "
                "economic operator, the date and time of registration of the latest passport version "
                "validated by a Commission electronic time stamp, and a hash of that version. It is "
                "guaranteed by a qualified electronic seal under Article 38 of Regulation (EU) No "
                "910/2014 and serves as evidence, including against third parties, that the "
                "registration obligation has been fulfilled."
            ),
            "criticality": "important",
            "applicable_entity": "Economic operators registering a DPP in the Commission registry",
        },
        {
            "article": "Article 19",
            "requirement_text": (
                "The verified economic operator is responsible for the accuracy and completeness of the "
                "information submitted at registration; shall keep the information stored in the "
                "registry accurate, complete and up to date at all times; shall implement appropriate "
                "technical and organisational security measures for the IT systems and credentials used "
                "to access the registry so as to prevent unauthorised access or modification of "
                "registration data; remains fully responsible for compliance where it authorises a "
                "verified third party to act on its behalf; and is the controller of the data it "
                "submits."
            ),
            "criticality": "critical",
            "applicable_entity": "Economic operators registering a DPP in the Commission registry",
        },
    ],
}

# Requirements currently in cluster 58 that are about food waste, not textiles.
FOOD_WASTE_ARTICLES = {"Article 9a(4)", "Article 9a(1)", "Article 29a"}

NEW_TEX_NAME = "Textiles: EPR, Ecodesign and Digital Product Passport (DPP-TEX)"
NEW_TEX_DESCRIPTION = (
    "The full obligation set for a textile, apparel or footwear producer placing products on "
    "the Union market: extended producer responsibility under Directive (EU) 2025/1892 "
    "amending the Waste Framework Directive, plus the product-side Ecodesign for Sustainable "
    "Products Regulation (EU) 2024/1781 chain, being the prohibition on destroying unsold "
    "apparel and footwear from 19 July 2026, the annual disclosure of discarded unsold "
    "products from 2 March 2027, and the horizontal digital product passport registry rules "
    "that will govern the textile DPP once the product-specific delegated act, indicatively "
    "timetabled for 2027 in the ESPR Working Plan 2025-2030, is adopted."
)
NEW_TEX_APPLICABILITY = (
    "Producers, importers, distributors and distance sellers of apparel, clothing accessories, "
    "home textiles and footwear (CN chapters 61 and 62, headings 4203, 4303, 6301 to 6306, "
    "6309, 6401 to 6405, 6504, 6505); producer responsibility organisations; online platforms "
    "and fulfilment service providers; sorting and preparing-for-reuse operators; social "
    "economy entities receiving donated unsold stock."
)

FOOD_WASTE_CLUSTER = {
    "name": "Food Waste Reduction Targets (Directive (EU) 2025/1892)",
    "description": (
        "Binding food waste reduction targets and prevention measures introduced into Directive "
        "2008/98/EC by Directive (EU) 2025/1892: a 10 % reduction in processing and manufacturing "
        "and a 30 % per capita reduction in retail, restaurants, food services and households by "
        "31 December 2030 against a 2021-2023 baseline."
    ),
    "applicability": (
        "Food processors and manufacturers, retailers, restaurants and food service operators, "
        "and the Member State authorities coordinating food waste prevention."
    ),
    "policy_area": "Food Safety",
    "priority_level": "high",
}


def _law_id(db, celex):
    row = db.query(EULaw.id).filter(EULaw.celex == celex).first()
    return row[0] if row else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="commit changes")
    ap.add_argument("--dry-run", action="store_true", help="report only (default)")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    plan = []
    try:
        espr_id = _law_id(db, ESPR_CELEX)
        if not espr_id:
            print(f"[ERROR] ESPR {ESPR_CELEX} not found in eu_laws. Aborting.")
            return 1
        print(f"[INFO] ESPR {ESPR_CELEX} -> law_id={espr_id}")

        cluster = db.query(LawCluster).filter(LawCluster.id == TEX_CLUSTER_ID).first()
        if not cluster:
            print(f"[ERROR] cluster {TEX_CLUSTER_ID} not found. Aborting.")
            return 1

        # -- 1. register the three new acts -------------------------------------
        law_ids = {ESPR_CELEX: espr_id}
        for spec in NEW_LAWS:
            existing = _law_id(db, spec["celex"])
            if existing:
                law_ids[spec["celex"]] = existing
                print(f"[SKIP] {spec['celex']} already in eu_laws (id={existing})")
                continue
            plan.append(f"INSERT eu_laws {spec['celex']}")
            if apply:
                # NOTE: eu_laws.search_vector is GENERATED ALWAYS in Postgres but is
                # declared as a plain writable Column on the EULaw model, so any ORM
                # insert fails with psycopg2.errors.GeneratedAlways. Insert with an
                # explicit column list instead. Do not "fix" this by adding
                # search_vector=None -- the column must be absent from the INSERT.
                res = db.execute(
                    text(
                        """
                        INSERT INTO eu_laws
                            (uuid, celex, doc_type, doc_type_normalized, title, date,
                             oj_reference, policy_area, xml_path, is_primary_legislation,
                             corpus_version, corpus_status, extra_metadata)
                        VALUES
                            (:uuid, :celex, :doc_type, :doc_type, :title, :date,
                             :oj_reference, :policy_area, :xml_path, false,
                             :corpus_version, 'active', CAST(:extra_metadata AS jsonb))
                        RETURNING id
                        """
                    ),
                    {
                        "uuid": str(_uuid.uuid4()),
                        "celex": spec["celex"],
                        "doc_type": spec["doc_type"],
                        "title": spec["title"],
                        "date": spec["date"],
                        "oj_reference": spec["oj_reference"],
                        "policy_area": "Environment",
                        "xml_path": (
                            "cellar://publications.europa.eu/resource/celex/"
                            f"{spec['celex']}"
                        ),
                        "corpus_version": "DPP_TEX_2026-08",
                        "extra_metadata": _json.dumps(
                            {
                                "registered_by": "_seed_dpp_tex_requirements.py",
                                "parent_celex": ESPR_CELEX,
                                "act_relationship": spec["relationship_type"],
                            }
                        ),
                    },
                )
                new_id = res.scalar_one()
                law_ids[spec["celex"]] = new_id
                print(f"[OK]   inserted {spec['celex']} -> law_id={new_id}")

        # -- 2. link acts to the TEX cluster ------------------------------------
        for spec in [{"celex": ESPR_CELEX, "relationship_type": "primary"}] + NEW_LAWS:
            lid = law_ids.get(spec["celex"])
            if not lid:
                continue
            link = (
                db.query(ClusterLaw)
                .filter(ClusterLaw.cluster_id == TEX_CLUSTER_ID, ClusterLaw.law_id == lid)
                .first()
            )
            if link:
                print(f"[SKIP] cluster_laws link exists for {spec['celex']}")
                continue
            plan.append(f"LINK cluster {TEX_CLUSTER_ID} <- {spec['celex']}")
            if apply:
                db.add(
                    ClusterLaw(
                        cluster_id=TEX_CLUSTER_ID,
                        law_id=lid,
                        relationship_type=spec["relationship_type"],
                    )
                )

        # -- 3. split food waste out --------------------------------------------
        fw = (
            db.query(LawRequirement)
            .filter(
                LawRequirement.cluster_id == TEX_CLUSTER_ID,
                LawRequirement.article.in_(list(FOOD_WASTE_ARTICLES)),
            )
            .all()
        )
        if fw:
            plan.append(f"MOVE {len(fw)} food-waste requirements out of cluster {TEX_CLUSTER_ID}")
            if apply:
                fwc = (
                    db.query(LawCluster)
                    .filter(LawCluster.name == FOOD_WASTE_CLUSTER["name"])
                    .first()
                )
                if not fwc:
                    wfd_id = _law_id(db, WFD_AMEND_CELEX)
                    fwc = LawCluster(primary_law_id=wfd_id, **FOOD_WASTE_CLUSTER)
                    db.add(fwc)
                    db.flush()
                    if wfd_id:
                        db.add(
                            ClusterLaw(
                                cluster_id=fwc.id,
                                law_id=wfd_id,
                                relationship_type="primary",
                            )
                        )
                    print(f"[OK]   created food-waste cluster id={fwc.id}")
                for r in fw:
                    r.cluster_id = fwc.id
                print(f"[OK]   moved {len(fw)} requirements to cluster {fwc.id}")
        else:
            print("[SKIP] no food-waste requirements left in cluster 58")

        # -- 4. rename / rescope the TEX cluster --------------------------------
        if cluster.name != NEW_TEX_NAME:
            plan.append(f"RENAME cluster {TEX_CLUSTER_ID} -> {NEW_TEX_NAME}")
            if apply:
                cluster.name = NEW_TEX_NAME
                cluster.description = NEW_TEX_DESCRIPTION
                cluster.applicability = NEW_TEX_APPLICABILITY
                cluster.primary_law_id = _law_id(db, WFD_AMEND_CELEX)
                print(f"[OK]   rescoped cluster {TEX_CLUSTER_ID}")

        # -- 5. seed requirements -----------------------------------------------
        added = 0
        for celex, reqs in REQUIREMENTS.items():
            lid = law_ids.get(celex)
            if not lid:
                print(f"[WARN] no law_id for {celex}, skipping its {len(reqs)} requirements")
                continue
            for r in reqs:
                dupe = (
                    db.query(LawRequirement)
                    .filter(
                        LawRequirement.law_id == lid,
                        LawRequirement.cluster_id == TEX_CLUSTER_ID,
                        LawRequirement.article == r["article"],
                    )
                    .first()
                )
                if dupe:
                    continue
                added += 1
                if apply:
                    db.add(
                        LawRequirement(
                            law_id=lid,
                            cluster_id=TEX_CLUSTER_ID,
                            article=r["article"],
                            requirement_text=r["requirement_text"],
                            criticality=r["criticality"],
                            applicable_entity=r["applicable_entity"],
                            deadline=r.get("deadline"),
                            extra_metadata={**SEED_TAG, "law_celex": celex},
                        )
                    )
        plan.append(f"INSERT {added} law_requirements")

        print("\n=== PLAN ===")
        for p in plan:
            print("  -", p)

        if apply:
            db.commit()
            n = (
                db.query(LawRequirement)
                .filter(LawRequirement.cluster_id == TEX_CLUSTER_ID)
                .count()
            )
            laws = (
                db.query(ClusterLaw)
                .filter(ClusterLaw.cluster_id == TEX_CLUSTER_ID)
                .count()
            )
            print(f"\n[OK] committed. Cluster {TEX_CLUSTER_ID} now has {laws} laws / {n} requirements")
        else:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[ERROR] {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
