"""Build the EU Law Comply package for the End-of-Life Vehicles Regulation.

Written on 13 August 2026, the day Regulation (EU) 2026/1738 entered into force,
as the `/lawdrop` phase-2 step. There was no cluster for this act at all, so
this creates one rather than deepening an existing one: the check in phase 1
returned nothing for CELEX 32026R1738 and nothing under any vehicle or
automotive name.

Every requirement below is grounded in the article text fetched from EUR-Lex on
that day, not in a summary. The dates come from Article 59 and from the
individual articles, which each carry their own "from <date>" clause; where an
article's clock depends on a methodology the Commission has not yet adopted
(Article 10), the requirement says so instead of asserting a date.

The anchor rule of `/lawdrop` is satisfied by the Article 53 row: at least one
binding company obligation carries the date the act starts to bite, here
13 August 2026.

Idempotent: matched by article label, deletes nothing, safe to re-run.

Usage:
  python3.12 -m scripts.seed_elv_cluster --dry-run
  python3.12 -m scripts.seed_elv_cluster --apply
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

CELEX = "32026R1738"
CLUSTER_NAME = "ELV - End-of-Life Vehicles Regulation"
POLICY_AREA = "Environment"
PRIORITY = "high"

DESCRIPTION = (
    "Regulation (EU) 2026/1738 on circularity requirements for vehicle design and on "
    "management of end-of-life vehicles. It replaces the 2000 ELV Directive and the "
    "2005 3R type-approval Directive with one directly applicable instrument covering "
    "the whole vehicle life cycle, from design and type-approval through extended "
    "producer responsibility, treatment at authorised facilities and export control. "
    "Entered into force 13 August 2026; the body of the Regulation applies from "
    "1 September 2028. Article 53 applies from 13 August 2026 and replaces the "
    "substance-restriction table in Annex I of the Batteries Regulation (EU) 2023/1542 "
    "with the table in Annex XII, extending the mercury, cadmium and lead limits "
    "expressly to batteries incorporated in vehicles; on the same date four heavy-metal "
    "exemptions in Annex II to Directive 2000/53/EC cease to apply. The delegated "
    "empowerments apply from 14 September 2026. Scope is phased by category: cars and "
    "vans first, special purpose M1 and N1 from 1 September 2029, buses, lorries, "
    "trailers and L-category from 1 September 2031. Headline duties: 85 % reusable or "
    "recyclable and 95 % reusable or recoverable by mass at type-approval from "
    "1 September 2032; 15 % recycled plastic from 2032 rising to 25 % from 2036, of "
    "which at least a fifth from end-of-life vehicles; a Digital Circularity Vehicle "
    "Passport from 1 September 2032, interoperable with the battery passport and with "
    "ESPR product passports; extended producer responsibility from 1 September 2029; "
    "reuse and recovery of 95 % and reuse and recycling of 85 % by average weight per "
    "vehicle per year from 1 January 2030; and export of used vehicles only where they "
    "are not end-of-life and are roadworthy, from 1 September 2031."
)

APPLICABILITY = (
    "Vehicle manufacturers and their suppliers placing M1 and N1 vehicles on the Union "
    "market, and from 2029 and 2031 the wider category set; importers and distributors; "
    "producers within the meaning of the extended producer responsibility chapter and "
    "their authorised representatives; producer responsibility organisations; authorised "
    "treatment facilities, dismantlers and shredders; traders in used, remanufactured and "
    "refurbished parts; and exporters of used vehicles to third countries. Directly "
    "applicable in all Member States without transposition."
)

SEED_TAG = {"source": "lawdrop_curated_seed", "seeded_at": "2026-08-13",
            "law_celex": CELEX}

# (article <=50, text, criticality, applicable_entity <=100, deadline, addressee, interpretive)
REQUIREMENTS = [
    ("Art 2 (is your vehicle in scope, and from when?)",
     "Establish scope and the date it begins, because this Regulation phases in by vehicle "
     "category. It applies to M1 and N1 vehicles and their end-of-life vehicles; from "
     "1 September 2029 to special purpose M1 and N1 vehicles; and from 1 September 2031 to "
     "M2, M3, N2, N3 and O category vehicles and to L-category two- and three-wheelers. It "
     "does not apply to small-series vehicles as defined in Regulation (EU) 2018/858, to "
     "L-category small series under Article 42 of Regulation (EU) No 168/2013, to vehicles "
     "for the armed services only, or to vehicles for civil defence, fire services and "
     "forces responsible for public order. Record which category applies and the date the "
     "duties attach, because a fleet can straddle two dates.",
     "critical", "Vehicle manufacturers, importers and distributors", None,
     "economic_operator", False),

    ("Art 53 + Annex XII (battery substances)",
     "From 13 August 2026 the substance-restriction table in Annex I to the Batteries "
     "Regulation (EU) 2023/1542 is replaced by the table in Annex XII to this Regulation. "
     "The mercury limit of 0,0005 % by weight, the cadmium limits of 0,002 % for portable "
     "batteries and 0,01 % in homogeneous material for electric vehicle and SLI batteries "
     "incorporated in M1 and N1 vehicles, and the lead limits apply expressly to batteries "
     "whether or not incorporated in vehicles. On the same date, entries 5(a), 5(b)(i), "
     "5(b)(ii) and 16 of Annex II to Directive 2000/53/EC cease to apply, so the old "
     "exemption route for those applications is closed. Check every battery in every "
     "vehicle placed on the market against the new table, not against the repealed "
     "exemptions.",
     "critical", "Vehicle manufacturers, battery producers and importers", "2026-08-13",
     "economic_operator", False),

    ("Art 4 (85 % recyclable, 95 % recoverable by mass)",
     "Each vehicle of a type type-approved from 1 September 2032 must be constructed so "
     "that it is reusable or recyclable to a minimum of 85 % by mass and reusable or "
     "recoverable to a minimum of 95 % by mass. To hold that position the manufacturer "
     "must collect the nature and mass of all materials through the full supply chain, "
     "keep the vehicle data the calculation needs, establish procedures verifying the "
     "correctness and completeness of supplier information, manage and document the "
     "material breakdown, and calculate the rates under the Commission methodology or, "
     "until that applies, under ISO 22628:2002 combined with Part A of Annex III.",
     "critical", "Vehicle manufacturers", "2032-09-01", "economic_operator", False),

    ("Art 5 (substances of concern minimised)",
     "The presence of substances of concern in vehicles and in their parts and components "
     "must be minimised as far as possible. Parts containing lead, mercury, cadmium or "
     "hexavalent chromium under the Article 5(5) derogation must be identified, and that "
     "information carried into the Digital Circularity Vehicle Passport under Article "
     "13(2), point (b). Treat the Commission's Article 5(2) report, due by 14 February "
     "2028 with ECHA assisting on chemical safety, as the signal for where the restriction "
     "list moves next.",
     "important", "Vehicle manufacturers and their suppliers", "2028-09-01",
     "economic_operator", False),

    ("Art 6 (15 % recycled plastic from 2032)",
     "The plastic in each new vehicle type type-approved from 1 September 2032 must "
     "contain a minimum of 15 % plastic recycled by weight from post-consumer plastic "
     "waste. At least 20 % of that target must be met with plastics recycled from "
     "end-of-life vehicles or from parts and components removed during the use phase. "
     "Elastomers from tyres, and thermosets other than polyurethane foams used for "
     "cushioning, are excluded from both weights. This is a sourcing commitment years "
     "ahead of the date: the recyclate stream has to exist before the type-approval does.",
     "critical", "Vehicle manufacturers", "2032-09-01", "economic_operator", False),

    ("Art 6 (25 % recycled plastic from 2036)",
     "The plastic in each new vehicle type type-approved from 1 September 2036 must "
     "contain a minimum of 25 % plastic recycled by weight from post-consumer plastic "
     "waste, on the same calculation basis and with the same requirement that at least a "
     "fifth of it comes from end-of-life vehicles or from parts removed during the use "
     "phase.",
     "critical", "Vehicle manufacturers", "2036-09-01", "economic_operator", False),

    ("Art 6(4) (third-country recyclate, Annex XIII)",
     "Recycled content counts only where it is recovered from post-consumer waste recycled "
     "in an installation located in the Union or, from 14 August 2030, in an installation "
     "located in a third country that meets the requirements of Annex XIII. Where a "
     "third-country installation is used, the audits verifying the Annex XIII conditions "
     "and the criteria for material recycled outside the Union apply from that date. Plan "
     "supplier qualification and audit evidence against 14 August 2030, not against the "
     "recycled-content target dates.",
     "important", "Vehicle manufacturers and their recyclate suppliers", "2030-08-14",
     "economic_operator", False),

    ("Art 8 (type-approval documentation)",
     "Demonstrate that new vehicle types placed on the market are type-approved in "
     "accordance with Regulation (EU) 2018/858, Regulation (EU) No 168/2013 and this "
     "Regulation. For types to which Articles 4, 5, 6 or 7 apply, provide the documentation "
     "showing compliance, include it in the information folder referred to in Article 24 of "
     "Regulation (EU) 2018/858 or Article 27 of Regulation (EU) No 168/2013, and submit it "
     "to the type-approval authority.",
     "critical", "Vehicle manufacturers", "2028-09-01", "economic_operator", False),

    ("Art 9 (circularity strategy, updated 5-yearly)",
     "From 1 September 2029 each manufacturer must draw up a circularity strategy at "
     "manufacturer level describing the actions it will take to meet the Chapter II "
     "circularity requirements, containing the elements in Part A of Annex V. A copy goes "
     "to the type-approval authorities of the Member States and to the Commission within "
     "30 days of it being drawn up. The strategy must be monitored, followed up and updated "
     "every five years under Part B of Annex V. The Commission publishes these strategies "
     "except for confidential information, so this is a public document.",
     "critical", "Vehicle manufacturers", "2029-09-01", "economic_operator", False),

    ("Art 10 (recycled-content declaration per material)",
     "Declare, for each new vehicle type, the share of recycled content of neodymium, "
     "dysprosium, praseodymium, terbium, samarium, nickel, cobalt and boron in the "
     "permanent magnets of e-drive motors, and of aluminium and its alloys, magnesium and "
     "its alloys, steel and its alloys, and plastics. The declaration states the share per "
     "material and, for plastic components heavier than 100 grams, whether the material is "
     "recycled from pre-consumer or from post-consumer waste. The clock is the first day of "
     "the month following 12 months from the adoption of the respective calculation and "
     "verification methodologies, so the date is not yet fixed; the duty falls away for any "
     "material that has become subject to an Article 6 target.",
     "important", "Vehicle manufacturers", None, "economic_operator", False),

    ("Art 11 (removal and replacement information)",
     "From 1 September 2029, for new type-approved vehicle types, give waste management "
     "operators, publishers of technical information and repair and maintenance operators "
     "unrestricted, standardised and non-discriminatory access to the Annex VI information "
     "enabling safe removal and replacement, covering at least electric vehicle batteries "
     "and their packs, and the parts, components and materials containing fluids, unless "
     "that information is already available under other Union law.",
     "critical", "Vehicle manufacturers", "2029-09-01", "economic_operator", False),

    ("Art 12 (Annex VII coding for parts and materials)",
     "Manufacturers and their suppliers must use the component and material coding "
     "standards listed in points 1, 2 and 3 of Annex VII to label and identify the parts, "
     "components and materials of vehicles, and mark polymer and elastomer parts "
     "accordingly. The Commission may amend Annex VII by delegated act, so the coding "
     "reference is a moving target that needs a watch.",
     "important", "Vehicle manufacturers and their suppliers", "2028-09-01",
     "economic_operator", False),

    ("Art 13 (Digital Circularity Vehicle Passport)",
     "From 1 September 2032 each vehicle placed on the market must have a Digital "
     "Circularity Vehicle Passport, accessible free of charge, aligned and interoperable "
     "with and where possible integrated into the other vehicle-related environmental "
     "passports in Union law, in particular the battery passport under Article 77 of "
     "Regulation (EU) 2023/1542, the passport in Article 3, point (68), of Regulation (EU) "
     "2024/1257 and passports established under the Ecodesign for Sustainable Products "
     "Regulation (EU) 2024/1781. It carries the Article 11 removal and replacement "
     "information, the parts containing lead, mercury, cadmium or hexavalent chromium under "
     "the Article 5(5) derogation, the recycled-content declaration under Article 10(1), "
     "and the official spare-parts catalogue for the vehicle type. Information already "
     "accessible through one of those other passports is not duplicated.",
     "critical", "Vehicle manufacturers", "2032-09-01", "economic_operator", False),

    ("Art 16 (extended producer responsibility)",
     "From 1 September 2029 producers carry extended producer responsibility for vehicles "
     "they make available on the market for the first time in a Member State, including "
     "vehicles previously made available in another Member State. The scheme must be "
     "consistent with Articles 8 and 8a of Directive 2008/98/EC and must ensure that those "
     "vehicles, when they become end-of-life vehicles, are collected under Article 23 and "
     "treated under Article 26, and that the waste management operators treating them meet "
     "the Article 33 targets.",
     "critical", "Producers making vehicles available on a Member State market", "2029-09-01",
     "economic_operator", False),

    ("Art 19 (register in every Member State)",
     "Producers must register in the national register of producers of each Member State "
     "where they make a vehicle available on the market for the first time, applying through "
     "the electronic data-processing system. A producer may only make vehicles available on "
     "that market if it, or its authorised representative where one is appointed, is "
     "registered. Member States establish those registers by 31 August 2029, so the "
     "application window is short before the duty in Article 16 begins.",
     "critical", "Producers and their authorised representatives", "2029-09-01",
     "economic_operator", False),

    ("Art 20 (financial responsibility of producers)",
     "The producer's financial contributions must cover the costs of collecting end-of-life "
     "vehicles as required by Articles 23 to 25 and transporting them efficiently, the costs "
     "of treatment required by Articles 26 to 30, 33 and 35 net of waste operators' revenues "
     "from used parts and secondary raw materials on an average-cost basis, the costs of "
     "awareness-raising campaigns, the cost of establishing the Article 25 notification "
     "system, and the administrative costs of gathering, making available and reporting "
     "data. Vehicles made available before 13 August 2026 sit under a separate derogation "
     "in the same article.",
     "critical", "Producers making vehicles available on a Member State market", "2029-09-01",
     "economic_operator", False),

    ("Art 21 (fee modulation by a PRO)",
     "Where extended producer responsibility is fulfilled collectively, the producer "
     "responsibility organisation must modulate the financial contributions it receives by "
     "reference to at least six criteria: the weight of the vehicle excluding its electric "
     "vehicle battery; the recyclability and reusability rate of the vehicle type as submitted "
     "to the type-approval authority under Article 4; the time needed to dismantle the vehicle "
     "at an authorised treatment facility, especially for parts that must be removed before "
     "shredding under Article 29; the share of materials and substances preventing high-quality "
     "recycling; the percentage of recycled content of the materials listed in Articles 6 and "
     "10; and the presence and amount of the substances referred to in Article 5(4). The "
     "Commission will set detailed application rules by delegated act.",
     "important", "Producer responsibility organisations", "2029-09-01", "pro", False),

    ("Art 25 (certificate of destruction, electronic)",
     "Authorised treatment facilities must issue a certificate of destruction to the last "
     "owner on delivery of the end-of-life vehicle, using the template in Annex X, in "
     "electronic format, and provide it through an electronic notification procedure to the "
     "relevant authorities of the Member State including the competent authority designated "
     "under Article 14. The certificate is what discharges the owner, so the electronic "
     "route has to work on day one, not eventually.",
     "critical", "Authorised treatment facilities", "2028-09-01", "economic_operator", False),

    ("Art 26 (obligations of treatment facilities)",
     "Authorised treatment facilities must ensure that all end-of-life vehicles and their "
     "parts, components and materials, and waste parts from vehicle repairs, are accepted "
     "and treated in compliance with the conditions of their permit and with this "
     "Regulation, including the storage requirements. Treatment may be carried out by one "
     "facility or, except for depollution, in cooperation with other authorised treatment "
     "facilities.",
     "critical", "Authorised treatment facilities", "2028-09-01", "economic_operator", False),

    ("Arts 28-30 (depollution, removal, fitness check)",
     "Depollute every end-of-life vehicle before further treatment, remove the parts and "
     "components listed for removal, and assess each removed part to determine whether it is "
     "fit for reuse under Part D point 1(a) of Annex VIII, for remanufacturing or "
     "refurbishment under Part D point 1(b), for recycling, or for another treatment "
     "operation taking account of the specific treatment requirements in Part F of Annex "
     "VIII. The assessment must consider the technical feasibility of the processes "
     "concerned, and removed parts must be labelled so a downstream buyer can trace them.",
     "critical", "Authorised treatment facilities, dismantlers and shredders", "2028-09-01",
     "economic_operator", False),

    ("Art 31 (selling used or remanufactured parts)",
     "From 1 September 2029 any economic operator selling used, remanufactured or "
     "refurbished spare parts and components must ensure that they carry the labelling "
     "placed by the authorised treatment facility under Article 30(2), point (a). Where the "
     "sale is to a consumer, the operator must also ensure the parts can maintain their "
     "required functions and performance in normal use and meet the other requirements "
     "applicable to such goods.",
     "critical", "Traders in used, remanufactured or refurbished vehicle parts", "2029-09-01",
     "economic_operator", False),

    ("Art 33 (95 % recovery, 85 % recycling per year)",
     "From 1 January 2030 producers or, where appointed under Article 17(1), producer "
     "responsibility organisations must ensure that the waste management operators treating "
     "their end-of-life vehicles achieve reuse and recovery of at least 95 % and reuse and "
     "recycling of at least 85 %, calculated together, by average weight per vehicle per "
     "year, excluding batteries. Contractual arrangements with treatment operators are the "
     "mechanism: the target binds the producer through the operator's performance.",
     "critical", "Producers and producer responsibility organisations", "2030-01-01",
     "economic_operator", False),

    ("Art 33(2) (30 % of ELV plastics recycled)",
     "From 1 January 2032 producers or, where appointed under Article 17(1), producer "
     "responsibility organisations must ensure that waste management operators meet a yearly "
     "target for the recycling of plastics of at least 30 % of the total average weight of the "
     "plastics contained in the end-of-life vehicles. Both weights exclude elastomers, "
     "thermosets other than polyurethane foams used for cushioning, and plastics containing or "
     "contaminated by a substance referred to in Article 7 of Regulation (EU) 2019/1021 above "
     "the Annex IV thresholds. This is a separate duty from the Article 6 recycled-content "
     "target: Article 6 is about what goes into a new vehicle, this is about what comes out of "
     "an old one.",
     "critical", "Producers and producer responsibility organisations", "2032-01-01",
     "economic_operator", False),

    ("Art 34 (no landfilling of shredder fractions)",
     "From 1 September 2029 the shredder heavy and shredder light fractions remaining after "
     "treatment of end-of-life vehicles must not be accepted in a landfill where they contain "
     "non-inert waste exceeding the limit values in Part G, points 2(d) and 2(e), of Annex VIII. "
     "The constraint lands on the treatment chain rather than on the landfill operator alone, "
     "because it forces the fraction to be characterised before it is moved.",
     "critical", "Authorised treatment facilities, shredders and waste operators", "2029-09-01",
     "economic_operator", False),

    ("Art 39 (export only if roadworthy, not an ELV)",
     "From 1 September 2031 used vehicles to be exported are subject to the controls in "
     "Chapter VI. A used vehicle may be exported only if it is not an end-of-life vehicle "
     "and is roadworthy at the date the export declaration is lodged, unless it has been "
     "recognised as a vehicle of special cultural interest. This closes the route by which "
     "end-of-life vehicles left the Union labelled as second-hand goods, and it puts the "
     "evidence burden on the exporter at the customs counter.",
     "critical", "Exporters of used vehicles to third countries", "2031-09-01",
     "economic_operator", False),

    # ---- interpretive: real duties, but they bind an authority, not the company.
    ("Art 14 (Member State competent authority)",
     "Member States designate one or more competent authorities responsible for the "
     "obligations on the management of end-of-life vehicles. This binds the Member State, "
     "not the company, but it is the authority a producer or treatment facility will deal "
     "with, and the one that receives the Article 25 electronic notifications.",
     "recommended", "Member States", "2028-09-01", "member_state", True),

    ("Art 19(1) (Member State producer register)",
     "By 31 August 2029 each Member State establishes or designates a register of producers "
     "to monitor compliance with the extended producer responsibility chapter, linked to the "
     "other national registers, and the Commission establishes a website holding the links "
     "to all of them. A company cannot register before its Member State's register exists, "
     "which is why this authority duty sits one day before the producer duty.",
     "recommended", "Member States and the Commission", "2029-08-31", "member_state", True),

    ("Art 49 (national penalties)",
     "By 1 September 2029 Member States must lay down effective, proportionate and "
     "dissuasive penalties for infringements of Articles 15(1), 16, 18(1), 22(1) and (2), "
     "23, 24, 25(1) and (2), 26 to 31, 33, 34, 36, 37 and 39, and notify them to the "
     "Commission. The exposure is national and will differ between Member States, so a "
     "multi-market operator cannot assume one ceiling.",
     "recommended", "Member States", "2029-09-01", "member_state", True),

    ("Art 57 (repeal and transitional provisions)",
     "Directive 2000/53/EC is repealed with effect from 1 September 2028, but several of its "
     "provisions stay alive on their own clocks: Article 4(2) and Annex II until 31 August "
     "2032, except entries 5(a), 5(b)(i), 5(b)(ii) and 16, which ceased to apply on "
     "13 August 2026; Article 5(4) second subparagraph, Article 6(3) second subparagraph, "
     "Article 7(1) and Article 8(3) and (4) until 31 August 2029; Article 6(3) first "
     "subparagraph and Annex I until 31 August 2029; and Article 7(2), point (b), until "
     "31 December 2030. Read the old Directive alongside the new Regulation until 2032 "
     "rather than treating it as gone.",
     "recommended", "All operators in the vehicle life cycle", "2028-09-01",
     "economic_operator", True),
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
        law_id = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                            {"x": CELEX}).scalar()
        if not law_id:
            print(f"[ERROR] {CELEX} is not in eu_laws. Run "
                  f"scripts._ingest_elv_oneshot --apply first.")
            return 1

        cluster_id = db.execute(text("SELECT id FROM law_clusters WHERE name=:n"),
                                {"n": CLUSTER_NAME}).scalar()
        if cluster_id:
            plan.append(f"cluster already present (id {cluster_id})")
        else:
            cluster_id = db.execute(text("""
                INSERT INTO law_clusters
                    (name, primary_law_id, description, applicability, policy_area,
                     priority_level, is_startup_focused, is_published)
                VALUES (:n, :p, :d, :a, :pa, :pr, false, true)
                RETURNING id"""),
                {"n": CLUSTER_NAME, "p": law_id, "d": DESCRIPTION,
                 "a": APPLICABILITY, "pa": POLICY_AREA, "pr": PRIORITY}).scalar()
            plan.append(f"INSERT law_clusters '{CLUSTER_NAME}' -> id {cluster_id}")

        if not db.execute(text("SELECT 1 FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                          {"c": cluster_id, "l": law_id}).scalar():
            db.execute(text("INSERT INTO cluster_laws (cluster_id, law_id) VALUES (:c,:l)"),
                       {"c": cluster_id, "l": law_id})
            plan.append(f"ATTACH {CELEX} to cluster {cluster_id}")

        added = interp = 0
        for article, body, crit, entity, deadline, addressee, interpretive in REQUIREMENTS:
            if len(article) > 50 or len(entity) > 100:
                print(f"[ERROR] too long: article {len(article)}/50 {article!r}, "
                      f"entity {len(entity)}/100")
                db.rollback()
                return 1
            if db.execute(text("""SELECT 1 FROM law_requirements
                                   WHERE cluster_id=:c AND law_id=:l AND article=:a"""),
                          {"c": cluster_id, "l": law_id, "a": article}).scalar():
                continue
            meta = {**SEED_TAG, "addressee": addressee}
            if interpretive:
                meta["interpretive"] = "true"
                interp += 1
            db.execute(text("""
                INSERT INTO law_requirements
                    (law_id, cluster_id, article, requirement_text, criticality,
                     applicable_entity, deadline, extra_metadata)
                VALUES (:l,:c,:a,:t,:crit,:e,:d, CAST(:m AS jsonb))"""),
                {"l": law_id, "c": cluster_id, "a": article, "t": body,
                 "crit": crit, "e": entity, "d": deadline, "m": json.dumps(meta)})
            added += 1
        plan.append(f"INSERT {added} requirements ({interp} interpretive, "
                    f"{added - interp} binding)")

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        n, binding, anchored = db.execute(text("""
            SELECT count(*),
                   count(*) FILTER (WHERE COALESCE(extra_metadata->>'interpretive','')<>'true'),
                   count(*) FILTER (WHERE deadline = DATE '2026-08-13'
                                      AND COALESCE(extra_metadata->>'interpretive','')<>'true')
              FROM law_requirements WHERE cluster_id=:c"""),
            {"c": cluster_id}).fetchone()
        print(f"\n[OK] committed. Cluster {cluster_id}: {n} requirements, "
              f"{binding} binding, {anchored} anchored on the 13 August 2026 date.")
        if not anchored:
            print("[WARN] no binding obligation carries the drop date - "
                  "that is the point of a lawdrop package.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
