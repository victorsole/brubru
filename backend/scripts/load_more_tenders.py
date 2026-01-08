"""
Load Additional Sample Tenders from More EU Countries

Adds tenders from France, Spain, Italy, Poland, Sweden, Denmark, Austria, and more.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.tender import Tender

# Additional tenders from more EU countries
MORE_SAMPLE_TENDERS = [
    # France
    {
        "publication_number": "2025/S 011-000011",
        "title": "Cloud Infrastructure Services for French Ministry of Education",
        "description": "Implementation of secure cloud infrastructure for national education platform, including data migration and training services.",
        "official_name": "Ministère de l'Éducation Nationale",
        "buyer_country": "FR",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "72260000"],
        "estimated_value": 3200000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 36,
        "sme_suitability_score": 70,
        "days_until_deadline": 38
    },
    {
        "publication_number": "2025/S 012-000012",
        "title": "Digital Marketing and Communication Services",
        "description": "Comprehensive digital marketing campaign for public health awareness including social media, content creation, and analytics.",
        "official_name": "Agence Régionale de Santé Île-de-France",
        "buyer_country": "FR",
        "procedure_type": "OP",
        "cpv_main": "79000000",
        "cpv_codes": ["79340000", "79342000"],
        "estimated_value": 580000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 88,
        "days_until_deadline": 27
    },
    # Spain
    {
        "publication_number": "2025/S 013-000013",
        "title": "ERP System Implementation for Regional Government",
        "description": "Design, implementation and deployment of enterprise resource planning system for administrative management.",
        "official_name": "Generalitat de Catalunya",
        "buyer_country": "ES",
        "procedure_type": "RS",
        "cpv_main": "72000000",
        "cpv_codes": ["72260000", "72263000"],
        "estimated_value": 2800000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 30,
        "has_lots": True,
        "lot_count": 3,
        "sme_suitability_score": 65,
        "days_until_deadline": 44
    },
    {
        "publication_number": "2025/S 014-000014",
        "title": "AI-Powered Customer Service Platform",
        "description": "Development of artificial intelligence chatbot and customer service platform with natural language processing capabilities.",
        "official_name": "Ayuntamiento de Madrid",
        "buyer_country": "ES",
        "procedure_type": "OP",
        "cpv_main": "48000000",
        "cpv_codes": ["48000000", "72000000"],
        "estimated_value": 750000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 18,
        "sme_suitability_score": 82,
        "days_until_deadline": 33
    },
    # Italy
    {
        "publication_number": "2025/S 015-000015",
        "title": "Smart City IoT Infrastructure Deployment",
        "description": "Installation and configuration of IoT sensors and smart city infrastructure for traffic management and environmental monitoring.",
        "official_name": "Comune di Milano",
        "buyer_country": "IT",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "45000000"],
        "estimated_value": 1950000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 75,
        "days_until_deadline": 40
    },
    {
        "publication_number": "2025/S 016-000016",
        "title": "Blockchain-Based Document Management System",
        "description": "Development of blockchain-based system for secure document verification and management for public administration.",
        "official_name": "Regione Lombardia",
        "buyer_country": "IT",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "72212000"],
        "estimated_value": 890000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 20,
        "sme_suitability_score": 78,
        "days_until_deadline": 36
    },
    # Poland
    {
        "publication_number": "2025/S 017-000017",
        "title": "E-Learning Platform Development for Vocational Training",
        "description": "Design and development of comprehensive e-learning platform with video content, assessments, and certification management.",
        "official_name": "Ministerstwo Edukacji i Nauki",
        "buyer_country": "PL",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "80500000"],
        "estimated_value": 620000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 18,
        "sme_suitability_score": 86,
        "days_until_deadline": 29
    },
    {
        "publication_number": "2025/S 018-000018",
        "title": "Data Analytics and Business Intelligence Services",
        "description": "Implementation of advanced analytics platform with dashboards, reporting tools, and predictive analytics capabilities.",
        "official_name": "Urząd Miasta Warszawy",
        "buyer_country": "PL",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "72300000"],
        "estimated_value": 540000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 84,
        "days_until_deadline": 31
    },
    # Sweden
    {
        "publication_number": "2025/S 019-000019",
        "title": "Green IT Infrastructure Modernization",
        "description": "Upgrade of IT infrastructure with focus on energy efficiency, renewable energy integration, and carbon footprint reduction.",
        "official_name": "Stockholms Stad",
        "buyer_country": "SE",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "90000000"],
        "estimated_value": 1450000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 30,
        "sme_suitability_score": 72,
        "days_until_deadline": 43
    },
    {
        "publication_number": "2025/S 020-000020",
        "title": "Open Data Portal Development",
        "description": "Development of open data portal with API access, data visualization tools, and public dataset management.",
        "official_name": "Göteborgs Stad",
        "buyer_country": "SE",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "72413000"],
        "estimated_value": 380000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 15,
        "sme_suitability_score": 91,
        "days_until_deadline": 26
    },
    # Denmark
    {
        "publication_number": "2025/S 021-000021",
        "title": "Digital Health Records Integration Platform",
        "description": "Integration platform for electronic health records across hospitals and clinics with GDPR compliance.",
        "official_name": "Region Hovedstaden",
        "buyer_country": "DK",
        "procedure_type": "RS",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "85000000"],
        "estimated_value": 2100000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 36,
        "has_lots": True,
        "lot_count": 2,
        "sme_suitability_score": 68,
        "days_until_deadline": 41
    },
    # Austria
    {
        "publication_number": "2025/S 022-000022",
        "title": "Quantum-Safe Cryptography Implementation",
        "description": "Implementation of post-quantum cryptographic solutions for secure government communications and data protection.",
        "official_name": "Bundesministerium für Digitalisierung",
        "buyer_country": "AT",
        "procedure_type": "NG",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "72611000"],
        "estimated_value": 980000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 76,
        "days_until_deadline": 37
    },
    # Portugal
    {
        "publication_number": "2025/S 023-000023",
        "title": "Tourism Promotion Digital Platform",
        "description": "Development of comprehensive tourism promotion platform with booking integration, virtual tours, and multilingual support.",
        "official_name": "Turismo de Portugal",
        "buyer_country": "PT",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "79340000"],
        "estimated_value": 720000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 18,
        "sme_suitability_score": 85,
        "days_until_deadline": 34
    },
    # Ireland
    {
        "publication_number": "2025/S 024-000024",
        "title": "Agricultural Data Management System",
        "description": "Cloud-based system for agricultural data collection, analysis, and reporting for farm subsidies and environmental monitoring.",
        "official_name": "Department of Agriculture, Food and the Marine",
        "buyer_country": "IE",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "77000000"],
        "estimated_value": 860000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 79,
        "days_until_deadline": 39
    },
    # Finland
    {
        "publication_number": "2025/S 025-000025",
        "title": "5G Network Infrastructure for Public Transport",
        "description": "Deployment of 5G network infrastructure across public transport network with smart connectivity solutions.",
        "official_name": "Helsingin kaupunki",
        "buyer_country": "FI",
        "procedure_type": "RS",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "64000000"],
        "estimated_value": 1680000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 30,
        "sme_suitability_score": 71,
        "days_until_deadline": 46
    },
]


def load_additional_tenders():
    """Load additional sample tenders into the database."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        print("=" * 60)
        print("LOADING ADDITIONAL SAMPLE TENDERS")
        print("=" * 60)

        created = 0
        updated = 0

        for tender_data in MORE_SAMPLE_TENDERS:
            pub_number = tender_data["publication_number"]

            # Calculate publication date (7 days ago)
            pub_date = now - timedelta(days=7)

            # Calculate submission deadline based on days_until_deadline
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
        print(f"\nCountries added:")
        print("- France (FR): 2 tenders")
        print("- Spain (ES): 2 tenders")
        print("- Italy (IT): 2 tenders")
        print("- Poland (PL): 2 tenders")
        print("- Sweden (SE): 2 tenders")
        print("- Denmark (DK): 1 tender")
        print("- Austria (AT): 1 tender")
        print("- Portugal (PT): 1 tender")
        print("- Ireland (IE): 1 tender")
        print("- Finland (FI): 1 tender")
        print("=" * 60)

    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load_additional_tenders()
