"""
Load IT and Software Service Tenders

Specific tenders for software development, IT consulting, and tech services
that should match Beresol's profile.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.tender import Tender

# IT and Software specific tenders
IT_SOFTWARE_TENDERS = [
    {
        "publication_number": "2025/S 026-000026",
        "title": "Custom Software Development for Public Administration",
        "description": "Development of custom web-based software solution for administrative processes including user management, workflows, and reporting.",
        "official_name": "Brussels Capital Region",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "72212000",
        "cpv_codes": ["72212000", "72212100", "72253200"],
        "estimated_value": 420000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 12,
        "sme_suitability_score": 95,
        "days_until_deadline": 22
    },
    {
        "publication_number": "2025/S 027-000027",
        "title": "Web Application Development and Maintenance",
        "description": "Development of responsive web application with React/Vue.js frontend and REST API backend, including ongoing maintenance and support.",
        "official_name": "Province of Antwerp",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "72212000",
        "cpv_codes": ["72212000", "72212100", "72212500"],
        "estimated_value": 380000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 18,
        "sme_suitability_score": 92,
        "days_until_deadline": 20
    },
    {
        "publication_number": "2025/S 028-000028",
        "title": "IT Consulting Services for Digital Transformation",
        "description": "Strategic IT consulting for digital transformation roadmap, technology assessment, and implementation planning.",
        "official_name": "City of Ghent",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "72224000",
        "cpv_codes": ["72224000", "72224100"],
        "estimated_value": 290000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 12,
        "sme_suitability_score": 89,
        "days_until_deadline": 24
    },
    {
        "publication_number": "2025/S 029-000029",
        "title": "API Development and Integration Services",
        "description": "Design and development of RESTful APIs for integration with third-party systems, including documentation and testing.",
        "official_name": "Federal Public Service Finance",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "72212000",
        "cpv_codes": ["72212000", "72263000"],
        "estimated_value": 315000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 15,
        "sme_suitability_score": 91,
        "days_until_deadline": 28
    },
    {
        "publication_number": "2025/S 030-000030",
        "title": "Progressive Web App Development",
        "description": "Development of progressive web application (PWA) for citizen services with offline capability and push notifications.",
        "official_name": "City of Bruges",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "48000000",
        "cpv_codes": ["48000000", "72212000"],
        "estimated_value": 265000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 10,
        "sme_suitability_score": 94,
        "days_until_deadline": 19
    },
    {
        "publication_number": "2025/S 031-000031",
        "title": "Software Development for IoT Data Platform",
        "description": "Backend and frontend development for IoT data collection and visualization platform with real-time analytics.",
        "official_name": "Amsterdam Smart City",
        "buyer_country": "NL",
        "procedure_type": "OP",
        "cpv_main": "72212000",
        "cpv_codes": ["72212000", "72263000"],
        "estimated_value": 495000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 18,
        "sme_suitability_score": 87,
        "days_until_deadline": 30
    },
    {
        "publication_number": "2025/S 032-000032",
        "title": "Full-Stack Development for E-Government Portal",
        "description": "Full-stack development services for e-government citizen portal with authentication, digital signatures, and document management.",
        "official_name": "Rotterdam Municipality",
        "buyer_country": "NL",
        "procedure_type": "OP",
        "cpv_main": "72212000",
        "cpv_codes": ["72212000", "72413000"],
        "estimated_value": 580000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 83,
        "days_until_deadline": 35
    },
    {
        "publication_number": "2025/S 033-000033",
        "title": "Microservices Architecture Development",
        "description": "Design and implementation of microservices-based architecture for modular government services platform.",
        "official_name": "The Hague Municipality",
        "buyer_country": "NL",
        "procedure_type": "RS",
        "cpv_main": "72212000",
        "cpv_codes": ["72212000", "72263000"],
        "estimated_value": 720000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 20,
        "has_lots": True,
        "lot_count": 2,
        "sme_suitability_score": 78,
        "days_until_deadline": 42
    },
    {
        "publication_number": "2025/S 034-000034",
        "title": "React Native Mobile App Development",
        "description": "Cross-platform mobile application development using React Native for public transport information and ticketing.",
        "official_name": "STIB-MIVB Brussels",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "48000000",
        "cpv_codes": ["48000000", "72212000"],
        "estimated_value": 340000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 14,
        "sme_suitability_score": 90,
        "days_until_deadline": 23
    },
    {
        "publication_number": "2025/S 035-000035",
        "title": "DevOps and CI/CD Pipeline Implementation",
        "description": "Setup and configuration of DevOps practices, CI/CD pipelines, containerization, and automated testing infrastructure.",
        "official_name": "Flemish Government - IT Department",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "72263000"],
        "estimated_value": 275000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 12,
        "sme_suitability_score": 88,
        "days_until_deadline": 26
    },
]


def load_it_software_tenders():
    """Load IT and software tenders into the database."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        print("=" * 60)
        print("LOADING IT & SOFTWARE TENDERS FOR BERESOL")
        print("=" * 60)

        created = 0
        updated = 0

        for tender_data in IT_SOFTWARE_TENDERS:
            pub_number = tender_data["publication_number"]

            # Calculate publication date (5 days ago for newer tenders)
            pub_date = now - timedelta(days=5)

            # Calculate submission deadline
            deadline = now + timedelta(days=tender_data.pop("days_until_deadline"))

            # Check if tender already exists
            existing = db.query(Tender).filter(
                Tender.publication_number == pub_number
            ).first()

            if existing:
                print(f"Updating: {pub_number}")
                for key, value in tender_data.items():
                    setattr(existing, key, value)
                existing.publication_date = pub_date
                existing.submission_deadline = deadline
                existing.updated_at = now
                updated += 1
            else:
                print(f"Creating: {pub_number} - {tender_data['title'][:50]}...")
                tender = Tender(
                    **tender_data,
                    publication_date=pub_date,
                    submission_deadline=deadline,
                    ted_url=f"https://ted.europa.eu/udl?uri=TED:NOTICE:{pub_number}:TEXT:EN:HTML",
                    status="open",
                    source="sample_data",
                    created_at=now,
                    updated_at=now
                )
                db.add(tender)
                created += 1

        db.commit()

        print("=" * 60)
        print(f"COMPLETE")
        print(f"Created: {created}")
        print(f"Updated: {updated}")
        print(f"Total:   {created + updated}")
        print("=" * 60)
        print("\n🎯 Perfect matches for Beresol:")
        print("  • Custom Software Development (€420K)")
        print("  • Web Application Development (€380K)")
        print("  • IT Consulting Services (€290K)")
        print("  • API Development (€315K)")
        print("  • Progressive Web App (€265K)")
        print("  • IoT Data Platform (€495K)")
        print("  • Full-Stack E-Gov Portal (€580K)")
        print("  • Microservices Architecture (€720K)")
        print("  • React Native App (€340K)")
        print("  • DevOps & CI/CD (€275K)")
        print("=" * 60)

    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load_it_software_tenders()
