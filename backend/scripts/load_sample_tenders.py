"""
Load Sample Tenders

Creates realistic sample tender data for testing and demonstration.
This populates the database with tenders that have varied deadlines
so the calendar displays properly.

Usage:
    python -m backend.scripts.load_sample_tenders
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.tender import Tender

# Sample tender data with realistic EU procurement notices
SAMPLE_TENDERS = [
    {
        "publication_number": "2025/S 001-000001",
        "title": "IT Infrastructure Modernization for European Commission DG CONNECT",
        "description": "Supply and implementation of modern IT infrastructure including servers, networking equipment, and cloud migration services.",
        "official_name": "European Commission - DG Communications Networks, Content and Technology",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "72260000", "72263000"],
        "estimated_value": 2500000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 75,
        "days_until_deadline": 21
    },
    {
        "publication_number": "2025/S 002-000002",
        "title": "Consulting Services for Digital Transformation Strategy",
        "description": "Professional consulting services to develop and implement a comprehensive digital transformation roadmap for public administration.",
        "official_name": "Ministry of Digital Affairs, Netherlands",
        "buyer_country": "NL",
        "procedure_type": "RS",
        "cpv_main": "79000000",
        "cpv_codes": ["79400000", "79411000"],
        "estimated_value": 850000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 18,
        "sme_suitability_score": 85,
        "days_until_deadline": 14
    },
    {
        "publication_number": "2025/S 003-000003",
        "title": "Cybersecurity Assessment and Penetration Testing Services",
        "description": "Comprehensive cybersecurity audit, vulnerability assessment, and penetration testing for critical infrastructure systems.",
        "official_name": "Federal Ministry of the Interior, Germany",
        "buyer_country": "DE",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72000000", "72611000"],
        "estimated_value": 450000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 12,
        "sme_suitability_score": 90,
        "days_until_deadline": 28
    },
    {
        "publication_number": "2025/S 004-000004",
        "title": "Cloud-Based Document Management System",
        "description": "Design, development, and implementation of a modern cloud-based document management and collaboration platform.",
        "official_name": "Flemish Government - Department of Digitalization",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "48000000",
        "cpv_codes": ["48000000", "48820000"],
        "estimated_value": 1200000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 36,
        "has_lots": True,
        "lot_count": 3,
        "sme_suitability_score": 80,
        "days_until_deadline": 35
    },
    {
        "publication_number": "2025/S 005-000005",
        "title": "Training Services: Data Analytics and AI for Public Sector",
        "description": "Comprehensive training program covering data analytics, machine learning, and AI applications for public sector employees.",
        "official_name": "European Personnel Selection Office (EPSO)",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "80000000",
        "cpv_codes": ["80500000", "80533100"],
        "estimated_value": 380000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 95,
        "days_until_deadline": 42
    },
    {
        "publication_number": "2025/S 006-000006",
        "title": "Environmental Impact Assessment Software Development",
        "description": "Development of custom software for environmental impact assessments, including GIS integration and reporting modules.",
        "official_name": "Ministry of Environment and Climate, Netherlands",
        "buyer_country": "NL",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72212000", "72260000"],
        "estimated_value": 680000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 18,
        "sme_suitability_score": 88,
        "days_until_deadline": 30
    },
    {
        "publication_number": "2025/S 007-000007",
        "title": "Mobile Application Development for Citizen Services",
        "description": "Design and development of mobile applications (iOS and Android) for citizen services including permit applications and status tracking.",
        "official_name": "City of Brussels",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "48000000",
        "cpv_codes": ["48000000", "48900000"],
        "estimated_value": 520000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 12,
        "sme_suitability_score": 92,
        "days_until_deadline": 25
    },
    {
        "publication_number": "2025/S 008-000008",
        "title": "Business Process Optimization and Automation",
        "description": "Analysis and optimization of administrative processes with implementation of RPA (Robotic Process Automation) solutions.",
        "official_name": "Province of Antwerp",
        "buyer_country": "BE",
        "procedure_type": "NG",
        "cpv_main": "79000000",
        "cpv_codes": ["79421000", "72611000"],
        "estimated_value": 420000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 24,
        "sme_suitability_score": 87,
        "days_until_deadline": 18
    },
    {
        "publication_number": "2025/S 009-000009",
        "title": "Website Redesign and Accessibility Compliance",
        "description": "Complete redesign of government portal with focus on accessibility (WCAG 2.1 AA compliance) and multilingual support.",
        "official_name": "Federal Public Service Economy - Belgium",
        "buyer_country": "BE",
        "procedure_type": "OP",
        "cpv_main": "72000000",
        "cpv_codes": ["72212000", "72413000"],
        "estimated_value": 290000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 15,
        "sme_suitability_score": 93,
        "days_until_deadline": 32
    },
    {
        "publication_number": "2025/S 010-000010",
        "title": "Data Center Maintenance and Support Services",
        "description": "Comprehensive maintenance, monitoring, and technical support for government data center infrastructure.",
        "official_name": "Rijkswaterstaat, Ministry of Infrastructure",
        "buyer_country": "NL",
        "procedure_type": "RS",
        "cpv_main": "50000000",
        "cpv_codes": ["50300000", "72000000"],
        "estimated_value": 1800000.0,
        "estimated_value_currency": "EUR",
        "contract_duration_months": 48,
        "has_lots": True,
        "lot_count": 4,
        "sme_suitability_score": 65,
        "days_until_deadline": 45
    }
]


def load_sample_tenders():
    """Load sample tenders into the database."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        print("=" * 60)
        print("LOADING SAMPLE TENDERS")
        print("=" * 60)

        created = 0
        updated = 0

        for tender_data in SAMPLE_TENDERS:
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

    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load_sample_tenders()
