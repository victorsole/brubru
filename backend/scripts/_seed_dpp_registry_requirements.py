"""Seed the headline obligations of Commission Implementing Regulation (EU)
2026/1778 (the DPP registry implementation act) into law_requirements.
DPP-regime act -> hub cluster 65. LAW_ID 28679. Brubru canon, 12 Aug 2026.
"""
import sys
from datetime import date
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv; load_dotenv(project_root / ".env")
from core.database import SessionLocal
from models.eu_law import LawRequirement
LAW_ID, HUB = 28679, 65
R = [
 ("Art 1(1)","critical","economic operator",None,"Register the digital product passport of a covered product (batteries, construction products, toys, detergents and any other product Union law brings within the ESPR Article 13 registry) before placing it on the market or putting it into service."),
 ("Art 4","critical","economic operator",None,"Complete the identity-verification process (an eIDAS-grade electronic signature, seal or attestation of attributes) to obtain verified economic operator status before registering any digital product passport."),
 ("Art 4(4)","high","verified economic operator",None,"Repeat the identity-verification process before verified status lapses (electronic identification means expiry, or 3 years, whichever is first) to keep the ability to register or modify data."),
 ("Art 5","high","value chain actor",None,"Complete the equivalent identity-verification process to obtain verified status before performing any action in the registry."),
 ("Art 6","medium","verified operator or value chain actor",None,"Manage its own electronic verification process and keep the registry profile data, including any change of legal representative, accurate, complete and up to date."),
 ("Art 6a","medium","verified operator or value chain actor",None,"Formally transfer responsibility for registered digital product passports to another verified operator on any change of ownership or organisational status."),
 ("Art 7","high","Member State",date(2027,2,18),"Appoint a single designated national administrator as the Commission's contact point for that Member State's registry access rights by 18 February 2027, and notify the Commission of any change."),
 ("Art 8(6)","critical","verified economic operator",None,"Register each digital product passport, at the correct granularity level, through either the secure user interface or the API."),
 ("Art 9(1)","medium","economic operator",None,"Be able to generate, on request, proof of registration for any digital product passport it is responsible for; the registry keeps it available for 90 days."),
 ("Art 10","high","European Commission",None,"Log every change to registration data (creation, modification, deletion), support time-stamped versioning, and process account-deletion requests. Registration data is retained for 10 years by default."),
 ("Art 13","medium","European Commission",date(2029,2,1),"Provide a year-round helpdesk (08:00 to 20:00 Brussels time), an automated technical support tool by February 2029, and retain written helpdesk exchanges for six months."),
 ("Art 14","medium","European Commission",None,"Maintain a complete, accurate, categorised log of every registry action, retained for the periods set for each category (6 months, 5 years or the duration of registration)."),
 ("Art 15","medium","European Commission",None,"Publish registration guidelines and give advance notice of planned maintenance windows on the registry's public website."),
 ("Art 16","high","European Commission",None,"Take the technical and organisational measures needed to prevent unauthorised access, detect unauthorised activity, prevent data breaches and log security events."),
 ("Art 17","medium","any registry user",None,"Notify the Commission, and where relevant the Member State concerned, immediately of any suspected malicious or fraudulent activity in or against the registry."),
 ("Art 19","high","verified economic operator",None,"Ensure the information submitted at registration is accurate and complete, keep it up to date, and act as controller of the data it submits. The unique registration identifier is not proof of compliance (ESPR Article 13(5))."),
 ("Art 21","high","European Commission",None,"Own and manage the registry's full lifecycle (development, availability, monitoring, updating, maintenance and hosting) and process registry data securely and lawfully."),
 ("Art 22","medium","Member State",None,"Ensure an appropriate level of security for any national components used to access the registry, and inform the Commission without undue delay of changes affecting the registry's functioning."),
]
db = SessionLocal()
try:
    from sqlalchemy import text as _t
    n = db.execute(_t("DELETE FROM law_requirements WHERE law_id=:l AND cluster_id=:c"), {"l":LAW_ID,"c":HUB}).rowcount
    if n: print(f"[purge] {n}")
    for art,crit,ent,dl,txt in R:
        db.add(LawRequirement(law_id=LAW_ID, cluster_id=HUB, article=art[:50], requirement_text=txt,
                              deadline=dl, criticality=crit, applicable_entity=ent[:100],
                              extra_metadata={"source":"canon_curated_seed","seeded_at":"2026-08-12"}))
    db.commit(); print(f"[seeded] {len(R)} DPP registry requirements into hub {HUB}")
finally:
    db.close()
