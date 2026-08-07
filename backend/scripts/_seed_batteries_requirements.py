"""Seed the canonical headline obligations of Regulation (EU) 2023/1542 (EU
Batteries Regulation) into law_requirements.

Pre-curated from a sequential read of the Regulation (Articles 1-96, 14 Chapters)
- Brubru canon project, 7 August 2026. Annex XII recycling-efficiency and
material-recovery figures cross-verified against EUR-Lex + the Commission
environment news release (the Formex reading copy ended at the Article 96
signature block, annexes living in sibling XML files).

IDs after running create_law_clusters.py --package batteries_regulation:
  SELECT id, celex FROM eu_laws WHERE celex='32023R1542'; -> 23290
  SELECT id, name FROM law_clusters WHERE name LIKE 'EU Batteries%'; -> 61
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from core.database import SessionLocal
from models.eu_law import LawRequirement

BATTERIES_LAW_ID = 23290
BATTERIES_CLUSTER_ID = 61

REQUIREMENTS = [
    {
        "article": "Art 6",
        "requirement_text": (
            "SUBSTANCE RESTRICTIONS: batteries placed on the market must not contain "
            "restricted substances beyond the limits in Annex I (including mercury, "
            "cadmium and lead limits carried over and tightened from Directive "
            "2006/66/EC). The Commission may amend Annex I via the REACH-aligned "
            "restriction procedure (Articles 86 to 88, ECHA dossier)."
        ),
        "deadline": date(2024, 2, 18),
        "criticality": "critical",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 7",
        "requirement_text": (
            "CARBON FOOTPRINT DECLARATION: electric vehicle, rechargeable industrial "
            "(above 2 kWh) and light means of transport (LMT) batteries must carry a "
            "carbon footprint declaration per functional unit. Applies from 18 Feb 2025 "
            "(EV), 18 Feb 2026 (industrial above 2 kWh), 18 Aug 2028 (LMT). A carbon "
            "footprint performance class label follows, then compliance with a maximum "
            "life-cycle carbon footprint threshold (EV from 18 Feb 2028)."
        ),
        "deadline": date(2025, 2, 18),
        "criticality": "high",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 8",
        "requirement_text": (
            "RECYCLED CONTENT: industrial (above 2 kWh), EV, SLI and (from 2036) LMT "
            "batteries containing cobalt, lead, lithium or nickel must first disclose, "
            "then meet minimum recycled-content shares. From 18 Aug 2031: cobalt 16 "
            "percent, lead 85 percent, lithium 6 percent, nickel 6 percent. From 18 Aug "
            "2036 these tighten to cobalt 26 percent, lithium 12 percent, nickel 15 "
            "percent (lead stays 85 percent)."
        ),
        "deadline": date(2031, 8, 18),
        "criticality": "high",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 9",
        "requirement_text": (
            "PERFORMANCE AND DURABILITY (portable general use): portable batteries of "
            "general use (AA, AAA, button cells and other standardised formats) must "
            "meet minimum electrochemical performance and durability values set by "
            "delegated act; the phase-out of non-rechargeable portable general-use "
            "batteries is kept under review."
        ),
        "deadline": date(2024, 2, 18),
        "criticality": "medium",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 10",
        "requirement_text": (
            "PERFORMANCE AND DURABILITY (rechargeable): rechargeable industrial (above "
            "2 kWh), LMT and EV batteries must be accompanied by documentation of "
            "electrochemical performance and durability parameters (Annex IV), and later "
            "meet minimum values set by delegated act."
        ),
        "deadline": date(2024, 2, 18),
        "criticality": "medium",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 11",
        "requirement_text": (
            "REMOVABILITY AND REPLACEABILITY: portable batteries incorporated in "
            "products must be readily removable and replaceable by the end-user; LMT "
            "batteries must be removable and replaceable by an independent professional. "
            "Applies from 18 Feb 2027. This is the Regulation's core right-to-repair "
            "obligation."
        ),
        "deadline": date(2027, 2, 18),
        "criticality": "critical",
        "applicable_entity": "economic operator placing the product on the market",
    },
    {
        "article": "Art 12",
        "requirement_text": (
            "SAFETY OF STATIONARY STORAGE: stationary battery energy storage systems "
            "(BESS) must be accompanied by technical documentation demonstrating they "
            "are safe during normal operation and use, evidenced by successful testing "
            "for the safety parameters in Annex V."
        ),
        "deadline": date(2024, 2, 18),
        "criticality": "high",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 13",
        "requirement_text": (
            "LABELLING, MARKING AND QR CODE: batteries must carry labels with capacity "
            "and other data, the separate-collection symbol (from 18 Aug 2025), heavy-"
            "metal symbols where applicable, and a QR code giving access to required "
            "information and (for LMT, industrial above 2 kWh and EV batteries) the "
            "battery passport. The QR code is mandatory from 18 Feb 2027."
        ),
        "deadline": date(2027, 2, 18),
        "criticality": "critical",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 14",
        "requirement_text": (
            "BATTERY MANAGEMENT SYSTEM DATA: stationary BESS, LMT and EV batteries must "
            "contain a battery management system storing state-of-health and expected "
            "lifetime data, with read-only access for the natural or legal person who "
            "has lawfully purchased the battery (or a third party acting on their "
            "behalf), to support second-life assessment."
        ),
        "deadline": date(2024, 2, 18),
        "criticality": "medium",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 17-18",
        "requirement_text": (
            "CONFORMITY ASSESSMENT AND CE MARKING: before placing a battery on the "
            "market the manufacturer must carry out the applicable conformity assessment "
            "procedure (Annex VIII), draw up an EU declaration of conformity and affix "
            "the CE marking. Applies from 18 Aug 2024."
        ),
        "deadline": date(2024, 8, 18),
        "criticality": "critical",
        "applicable_entity": "manufacturer",
    },
    {
        "article": "Art 48-52",
        "requirement_text": (
            "SUPPLY-CHAIN DUE DILIGENCE: economic operators with net turnover of 40 "
            "million euros or more must adopt, maintain, independently verify and "
            "publicly report a battery due diligence policy covering the raw materials "
            "cobalt, natural graphite, lithium and nickel, addressing social and "
            "environmental risk categories in Annex X. Applies from 18 Aug 2025. Small "
            "and medium-sized enterprises are exempt."
        ),
        "deadline": date(2025, 8, 18),
        "criticality": "critical",
        "applicable_entity": "economic operator (turnover >= 40m euros)",
    },
    {
        "article": "Art 55-56",
        "requirement_text": (
            "PRODUCER REGISTRATION AND EPR: producers must register in the producer "
            "register of every Member State where they first make a battery available, "
            "and bear extended producer responsibility, financing and organising the "
            "collection, treatment and recycling of the batteries they place on the "
            "market. Applies from 18 Aug 2025."
        ),
        "deadline": date(2025, 8, 18),
        "criticality": "critical",
        "applicable_entity": "producer",
    },
    {
        "article": "Art 59-60",
        "requirement_text": (
            "COLLECTION TARGETS: producers (or PROs) must set up free take-back and "
            "collection networks and meet binding collection targets. Portable "
            "batteries: 63 percent by 31 Dec 2027 and 73 percent by 31 Dec 2030. LMT "
            "batteries: 51 percent by 31 Dec 2028 and 61 percent by 31 Dec 2031."
        ),
        "deadline": date(2027, 12, 31),
        "criticality": "high",
        "applicable_entity": "producer / producer responsibility organisation",
    },
    {
        "article": "Art 62",
        "requirement_text": (
            "DISTRIBUTOR TAKE-BACK: distributors must take back waste batteries from "
            "end-users free of charge and with no obligation to buy a new battery, "
            "regardless of chemical composition, origin or brand. Applies from 18 Aug "
            "2025."
        ),
        "deadline": date(2025, 8, 18),
        "criticality": "medium",
        "applicable_entity": "distributor",
    },
    {
        "article": "Art 71",
        "requirement_text": (
            "RECYCLING EFFICIENCY (Annex XII Part B): recycling processes must reach "
            "minimum recycling efficiencies by 31 Dec 2025: lead-acid 75 percent, "
            "lithium-based 65 percent, nickel-cadmium 80 percent, other 50 percent. "
            "Rising by 31 Dec 2030 to lead-acid 80 percent and lithium-based 70 percent."
        ),
        "deadline": date(2025, 12, 31),
        "criticality": "high",
        "applicable_entity": "recycler / waste management operator",
    },
    {
        "article": "Art 71",
        "requirement_text": (
            "MATERIAL RECOVERY (Annex XII Part C): recyclers must recover, from waste "
            "batteries, cobalt, copper, lead and nickel at 90 percent by 31 Dec 2027 "
            "and 95 percent by 31 Dec 2031, and lithium at 50 percent by 31 Dec 2027 "
            "and 80 percent by 31 Dec 2031."
        ),
        "deadline": date(2027, 12, 31),
        "criticality": "high",
        "applicable_entity": "recycler / waste management operator",
    },
    {
        "article": "Art 75-76",
        "requirement_text": (
            "REPORTING: producers, PROs and waste management operators must report "
            "annually to competent authorities on batteries placed on the market, "
            "collected, and treated, and on collection, recycling-efficiency and "
            "recovery rates achieved, for onward reporting to the Commission. Applies "
            "from 18 Aug 2025."
        ),
        "deadline": date(2025, 8, 18),
        "criticality": "medium",
        "applicable_entity": "producer / waste management operator",
    },
    {
        "article": "Art 77-78",
        "requirement_text": (
            "DIGITAL BATTERY PASSPORT: LMT, industrial (above 2 kWh) and EV batteries "
            "placed on the market must have an electronic battery passport, unique per "
            "battery, accessible via the QR code, holding composition, carbon footprint, "
            "supply-chain due diligence, performance, durability and end-of-life data "
            "with public and restricted-access layers. Applies from 18 Feb 2027."
        ),
        "deadline": date(2027, 2, 18),
        "criticality": "critical",
        "applicable_entity": "economic operator placing the battery on the market",
    },
]

db = SessionLocal()
try:
    from sqlalchemy import text as _text
    n_deleted = db.execute(_text("""
        DELETE FROM law_requirements
        WHERE law_id = :lid AND cluster_id = :cid
    """), {"lid": BATTERIES_LAW_ID, "cid": BATTERIES_CLUSTER_ID}).rowcount
    if n_deleted:
        print(f"[purge] removed {n_deleted} prior Batteries requirements")

    for r in REQUIREMENTS:
        req = LawRequirement(
            law_id=BATTERIES_LAW_ID,
            cluster_id=BATTERIES_CLUSTER_ID,
            article=r["article"][:50],
            requirement_text=r["requirement_text"],
            deadline=r.get("deadline"),
            criticality=r["criticality"],
            applicable_entity=r["applicable_entity"][:100],
            extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-07"},
        )
        db.add(req)
    db.commit()
    print(f"[seeded] {len(REQUIREMENTS)} Batteries requirements into law_requirements")
finally:
    db.close()
