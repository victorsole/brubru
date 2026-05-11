"""
One-off: mark all EUTR orgs whose 11 May 2026 Brubru Brief bounced
as outreach_status='bounced'. Reads list from /tmp/eutr_bounced.txt.

Run once, then delete.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.database import SessionLocal


BOUNCED = [
    "info@team-prrc.com", "info@constellr.com", "info@leaderfrance.fr",
    "info@aub.be", "info@wma.net", "info@aphp.fr",
    "info@bobine-chemistry.com", "info@adele-hydrogen.odoo.com",
    "info@otb.vc", "info@in4climate.nrw", "info@sciencedirect.com",
    "info@eambes.org", "info@e-tlf.com", "info@resultx.ai",
    "info@eiffel-ig.com", "info@hospitality-europe.eu",
    "info@nlrinternational.org", "info@state-capture.org",
    "info@dsgc.nl", "info@engagement.fr", "info@ecf.com",
    "info@eassw.org", "info@haf-eu.org", "info@fhef.org",
    "info@kvk.nl", "info@reliefandreconciliation.org",
    "info@europeanbiosafetynetwork.eu", "info@fondemos.com",
    "info@dare-network.eu", "info@aeggf.de", "info@nextep-health.com",
    "info@gotion.de", "info@adsu.fr", "info@aepi-international.org",
    "info@hs-kehl.de", "info@unirleurope.eu", "info@cassidylevy.com",
    "info@actgroup.com", "info@tilburguniversity.edu",
    "info@rights-matter.org", "info@reju.com", "info@aglgroup.com",
    "info@eurotransplant.org", "info@portboulognecalais.fr",
    "info@ugpvb.fr", "info@esge.com", "info@expertises-chimiques.eu",
    "info@exarc.org", "info@exanter.fr", "info@filiereorkid.com",
    "info@tex-rail-training.be", "info@renauto.es",
]


def main():
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                "UPDATE transparency_register_orgs "
                "SET outreach_status = 'bounced', updated_at = NOW() "
                "WHERE LOWER(contact_email) = ANY(:emails) "
                "RETURNING contact_email, name, country, policy_cluster"
            ),
            {"emails": [e.lower() for e in BOUNCED]},
        )
        rows = result.fetchall()
        db.commit()
        print(f"[OK] Marked {len(rows)} EUTR orgs as bounced (out of {len(BOUNCED)} input)")
        for r in rows:
            print(f"  {r.contact_email}  | {r.country}  | {r.policy_cluster}  | {r.name}")
        missing = set(e.lower() for e in BOUNCED) - {r.contact_email.lower() for r in rows if r.contact_email}
        if missing:
            print(f"\n[INFO] Not found in EUTR table ({len(missing)}):")
            for m in sorted(missing):
                print(f"  {m}")
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
