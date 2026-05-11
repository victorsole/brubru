"""One-off: insert EUHPP Live Webinar - Strengthening Health System Resilience
(Thu 11 June 2026, 15:00-16:30 CEST) into eu_calendar_events. Friday 8 May
DG SANTE press release announced the webinar; today's Phase 3D adds the
calendar entry. Run once, then delete."""
import sys
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.database import SessionLocal


def main():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            INSERT INTO eu_calendar_events
              (id, institution, event_type, title, description,
               start_date, end_date, start_time, end_time, all_day,
               commission_dg, policy_areas, status, source_url, source,
               external_id, scraped_at, first_seen, last_updated)
            VALUES
              (gen_random_uuid(), 'COMMISSION', 'webinar',
               'EUHPP Live Webinar: Strengthening Health System Resilience in the EU',
               'EU Health Policy Platform live webinar on health system resilience in the EU: evidence, measurement and policy levers. Announced via DG SANTE 8 May 2026 (registration open). Cross-link: european_health_data_space implementation dialogue 12 May 2026 with Commissioner Varhelyi.',
               '2026-06-11', '2026-06-11', '15:00', '16:30', false,
               'SANTE', ARRAY['health'], 'scheduled',
               'https://health.ec.europa.eu/eu-health-policy-platform_en',
               'manual_insert', 'euhpp-2026-06-11-resilience',
               NOW(), NOW(), NOW())
            ON CONFLICT DO NOTHING
            RETURNING id, title, start_date
        """))
        row = result.fetchone()
        if row:
            db.commit()
            print(f"[OK] inserted: {row.id} | {row.start_date} | {row.title}")
        else:
            print("[INFO] no row inserted (conflict?)")
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
