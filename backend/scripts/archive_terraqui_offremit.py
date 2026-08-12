"""Archive the tracked files that are not Terraqui's remit.

Her Bubble held 26 active carriage tracks, most of them generic: European
defence, the ESMA chairmanship, narco-trafficking, human-rights defenders in
Indonesia. It looked populated and was mostly noise for an environmental lawyer
working on textile digital product passports.

The keep list is deliberately WIDER than "digital product passport". Terraqui's
own practice areas are climate change and energy transition, biodiversity,
water, circular economy and waste, sustainable activities, sustainable
consumption and products, planning, and pollution. A file inside those stays
even if it is not DPP, because she is a practising environmental lawyer and not
only a LIFE project partner.

Archive, never delete: archived_at plus a reason, so anything here can be
restored and she can see why it went.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

ACCOUNTS = {
    "jcastella@terraqui.com": "e6337400-6c0c-4842-9007-26db3f59a3fb",
    "joana-demo@demo.invalid": "96788e72-5890-4b2f-bd35-00bedc98e721",
}

# Title fragment -> why it stays. Matched case-insensitively on the carriage title.
KEEP = {
    "ecodesign": "core: ecodesign and circular economy",
    "critical raw materials": "in the DPP corpus; supply-chain duties the passport draws on",
    "green claims": "sustainable consumption and products, adjacent to passport claims",
    "climate law": "Terraqui practice: climate change and energy transition",
    "corporate sustainability reporting": "sustainability reporting feeds product data",
    "chemicals agency": "Terraqui practice: chemicals, substances of concern in products",
    "industrial accelerator": "industrial decarbonisation and circularity",
    "groundwater": "Terraqui practice: water protection",
    "shipments of waste": "waste, directly relevant to textile waste export",
}

REASON = ("Archived 12 Aug 2026: outside Terraqui's environmental-law remit and the "
          "LIFE DPP-TEX project. Restorable from My Tracked Files.")


def classify(title: str):
    low = (title or "").lower()
    for frag, why in KEEP.items():
        if frag in low:
            return True, why
    return False, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        for email, uid in ACCOUNTS.items():
            rows = db.execute(
                text("SELECT t.id, lc.title FROM user_carriage_tracks t "
                     "JOIN legislative_carriages lc ON lc.id = t.carriage_id "
                     "WHERE t.user_id = :i AND t.archived_at IS NULL "
                     "ORDER BY lc.title"),
                {"i": uid},
            ).fetchall()
            keep, drop = [], []
            for r in rows:
                ok, why = classify(r.title)
                (keep if ok else drop).append((r.id, r.title, why))

            print(f"\n=== {email}: {len(rows)} active ===")
            print(f"  KEEP ({len(keep)}):")
            for _, title, why in keep:
                print(f"    + {title[:60]:<62} {why}")
            print(f"  ARCHIVE ({len(drop)}):")
            for _, title, _w in drop:
                print(f"    - {title[:88]}")

            if args.apply and drop:
                db.execute(
                    text("UPDATE user_carriage_tracks "
                         "SET archived_at = now(), archived_reason = :r "
                         "WHERE id = ANY(:ids)"),
                    {"r": REASON, "ids": [d[0] for d in drop]},
                )

        if args.apply:
            db.commit()
            print("\n=== verification ===")
            for email, uid in ACCOUNTS.items():
                a = db.execute(
                    text("SELECT count(*) FROM user_carriage_tracks "
                         "WHERE user_id = :i AND archived_at IS NULL"), {"i": uid}).scalar()
                z = db.execute(
                    text("SELECT count(*) FROM user_carriage_tracks "
                         "WHERE user_id = :i AND archived_at IS NOT NULL"), {"i": uid}).scalar()
                on_remit = db.execute(
                    text("SELECT count(*) FROM user_carriage_tracks t "
                         "JOIN legislative_carriages lc ON lc.id = t.carriage_id "
                         "WHERE t.user_id = :i AND t.archived_at IS NULL AND ("
                         "lc.title ILIKE '%ecodesign%' OR lc.title ILIKE '%circular%' OR "
                         "lc.title ILIKE '%waste%' OR lc.title ILIKE '%raw material%' OR "
                         "lc.title ILIKE '%climate%' OR lc.title ILIKE '%chemical%' OR "
                         "lc.title ILIKE '%green claims%' OR lc.title ILIKE '%groundwater%' OR "
                         "lc.title ILIKE '%sustainability%' OR lc.title ILIKE '%industrial%')"),
                    {"i": uid}).scalar()
                print(f"  {email}: {a} active, {z} archived, "
                      f"{on_remit}/{a} of the active set on-remit")
        else:
            print("\n[DRY-RUN] nothing written")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
