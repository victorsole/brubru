"""Seed the canonical headline obligations of Regulation (EU) 2023/1114 (MiCA) into
law_requirements. Pre-curated from a full read of the recitals + Title I + final provisions
(data/canon/2023-1114_mica.analysis.md). article and applicable_entity are VARCHAR(50).

ids verified live against prod Supabase on 26 May 2026:
  eu_laws id for 32023R1114 -> 28662 (ingested via canon pipeline)
  law_clusters 'MiCA%' -> 27
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

MICA_LAW_ID = 28662
MICA_CLUSTER_ID = 27

REQUIREMENTS = [
    {"article": "Title II (crypto-asset white paper)",
     "requirement_text": "Offerors and persons seeking admission to trading of crypto-assets other than asset-referenced or e-money tokens must draw up, notify to the competent authority and publish a crypto-asset white paper with mandatory, fair, clear and not-misleading disclosures (issuer, project, offer, rights, technology, risks, and the environmental impact of the consensus mechanism).",
     "criticality": "critical", "applicable_entity": "crypto-asset offerors"},
    {"article": "Title II (white-paper exemptions)",
     "requirement_text": "No white paper is required for offers to fewer than 150 persons per Member State, offers to qualified investors only, or offers with total consideration not exceeding EUR 1 000 000 over 12 months, nor for free crypto-assets, mining rewards or limited-network utility tokens.",
     "criticality": "informational", "applicable_entity": "crypto-asset offerors"},
    {"article": "Title II (right of withdrawal)",
     "requirement_text": "Retail holders acquiring Title II crypto-assets directly from the offeror or a placing CASP have a 14-day right of withdrawal, except where the crypto-assets are already admitted to trading.",
     "criticality": "important", "applicable_entity": "offerors / retail holders"},
    {"article": "Title III (ART authorisation)",
     "requirement_text": "Issuers of asset-referenced tokens must have a registered office in the Union and be authorised by the competent authority (with the white paper approved), after consultation of EBA, ESMA and the ECB (and the relevant national central bank for non-euro currencies, whose opinion can be binding). Not required below EUR 5 000 000 or for qualified-investor-only offers.",
     "criticality": "critical", "applicable_entity": "asset-referenced token issuers"},
    {"article": "Title III (reserve of assets)",
     "requirement_text": "ART issuers must constitute and maintain a reserve of assets that is segregated from own assets, composed of secure low-risk assets, held in custody, and matching the value of tokens in circulation; profits and losses on the reserve are borne by the issuer.",
     "criticality": "critical", "applicable_entity": "asset-referenced token issuers"},
    {"article": "Title III/IV (redemption, no interest)",
     "requirement_text": "Holders of asset-referenced and e-money tokens have a permanent right of redemption at any time (e-money tokens at par value in the referenced currency). Issuers and CASPs must not grant interest to holders related to the holding period.",
     "criticality": "critical", "applicable_entity": "ART / EMT issuers"},
    {"article": "Title IV (EMT issuer status)",
     "requirement_text": "E-money tokens may be issued only by a credit institution authorised under Directive 2013/36/EU or an electronic money institution authorised under Directive 2009/110/EC; the issuer must draw up and notify a crypto-asset white paper.",
     "criticality": "critical", "applicable_entity": "e-money token issuers"},
    {"article": "Significant tokens (EBA supervision)",
     "requirement_text": "Asset-referenced and e-money tokens meeting significance thresholds (large customer base, high market capitalisation or large transaction volumes) face stricter requirements (higher own funds, interoperability, liquidity management) and are supervised directly by EBA, which sets up a college of supervisors.",
     "criticality": "important", "applicable_entity": "significant token issuers"},
    {"article": "ART means of exchange threshold",
     "requirement_text": "An asset-referenced token used widely as a means of exchange (over 1 million transactions and EUR 200 000 000 per day in a single currency area) triggers a duty on the issuer to reduce the level of activity.",
     "criticality": "important", "applicable_entity": "asset-referenced token issuers"},
    {"article": "Title V (CASP authorisation)",
     "requirement_text": "Crypto-asset service providers must be authorised, be legal persons with a registered office and place of effective management in the Union, and have at least one director resident in the Union. One authorisation is valid Union-wide (passporting).",
     "criticality": "critical", "applicable_entity": "crypto-asset service providers"},
    {"article": "Title V (the ten crypto-asset services)",
     "requirement_text": "Authorisation covers ten services: custody and administration; operation of a trading platform; exchange of crypto-assets for funds; exchange for other crypto-assets; execution of orders; placing; reception and transmission of orders; advice; portfolio management; and transfer services.",
     "criticality": "informational", "applicable_entity": "crypto-asset service providers"},
    {"article": "Title V (CASP conduct + prudential)",
     "requirement_text": "CASPs must act honestly, fairly, professionally and in clients' best interests; safeguard client crypto-assets and funds (custodians liable for ICT losses); meet prudential own-funds requirements; have fit-and-proper management; and operate conflict-of-interest and complaints procedures.",
     "criticality": "critical", "applicable_entity": "crypto-asset service providers"},
    {"article": "Title VI (market abuse)",
     "requirement_text": "Insider dealing, unlawful disclosure of inside information and market manipulation are prohibited for crypto-assets admitted to trading; issuers and CASPs must have systems to detect and report suspected market abuse.",
     "criticality": "important", "applicable_entity": "issuers / CASPs"},
    {"article": "Title VII (ESMA register)",
     "requirement_text": "ESMA establishes and maintains a public register of crypto-asset white papers, issuers of asset-referenced tokens, issuers of e-money tokens and crypto-asset service providers.",
     "criticality": "informational", "applicable_entity": "ESMA"},
    {"article": "Article 143 (transitional regime)",
     "requirement_text": "CASPs operating lawfully under national law before 30 December 2024 may continue until 1 July 2026 or until authorised or refused (Member States may shorten or disapply this grandfathering). ART issuers operating before 30 June 2024 may continue if they apply for authorisation before 30 July 2024.",
     "criticality": "important", "applicable_entity": "CASPs / ART issuers"},
    {"article": "Article 149 (application dates)",
     "requirement_text": "MiCA entered into force on 29 June 2023. Titles III and IV (asset-referenced and e-money tokens) apply from 30 June 2024; the remainder, including the CASP regime, applies from 30 December 2024.",
     "criticality": "informational", "applicable_entity": "all crypto market participants"},
]


def main():
    db = SessionLocal()
    try:
        if db.query(LawRequirement).filter(LawRequirement.law_id == MICA_LAW_ID).count():
            print("[INFO] requirements already exist. Skipping."); return
        bad = [r["article"] for r in REQUIREMENTS if len(r["article"]) > 50] + \
              [r["applicable_entity"] for r in REQUIREMENTS if len(r["applicable_entity"]) > 50]
        if bad:
            print("ABORT: >50 chars:", bad); sys.exit(1)
        for r in REQUIREMENTS:
            db.add(LawRequirement(law_id=MICA_LAW_ID, cluster_id=MICA_CLUSTER_ID,
                   article=r["article"], requirement_text=r["requirement_text"],
                   criticality=r["criticality"], applicable_entity=r["applicable_entity"]))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={MICA_LAW_ID}, cluster_id={MICA_CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
