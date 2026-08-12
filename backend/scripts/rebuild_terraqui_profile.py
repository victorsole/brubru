"""Rebuild the Terraqui profiles around the Digital Product Passport.

Applies to BOTH Joana's real account and the demo clone, so what Victor opens in
the clone is what she sees.

What it does:
  1. language -> ca. She is a Catalan-speaking lawyer at a Catalan firm and her
     interface was in English. user.language drives the whole UI.
  2. ticks the new policy interest "Ecodesign of sustainable products / Digital
     product passport", which is the switch the MEUB filters, the news lens and
     the chat context all read.
  3. tracks the four consultations that govern her project, initiative 16116
     first: it is the ESPR delegated act on apparel textiles and it was not in
     her Bubble at all.

What it deliberately does NOT do: track the six DPP acts. There is no vehicle
for it. user_saved_entries is keyed to RSS entries, user_text_adopted_tracks to
EP adopted texts (P10_TA references, not CELEX), and only two of the six acts
exist as legislative carriages, one of those being a corrigendum rather than the
act. Tracking an adopted law needs a user_law_tracks table that does not exist.
Faking it by attaching her to a corrigendum would be worse than the gap.

Idempotent, and reports what it changed. --dry-run shows the plan.
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

DPP_INTEREST = "Ecodesign of sustainable products / Digital product passport"

# The four Have Your Say initiatives that govern the LIFE DPP-TEX work.
CONSULTATIONS = {
    "16116": "the ESPR delegated act on ecodesign for apparel textiles",
    "17772": "Union-wide end-of-waste criteria for textile waste",
    "17472": "reporting obligations for used textiles and textile waste",
    "17873": "ecodesign requirements on product repairability",
}



def _parse_interests(raw) -> list:
    """users.policy_interests is a TEXT column holding a JSON string, not a
    jsonb array, and some rows are double-encoded ("[\\"Health\\"]").

    Treating the raw value as a list splits the string into single characters,
    so appending would have written ['[', '"', 'E', 'n', ...] and destroyed the
    user's interests. Parse defensively, up to two levels.
    """
    import json as _json

    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    val = raw
    for _ in range(2):
        if isinstance(val, str):
            try:
                val = _json.loads(val)
            except Exception:  # noqa: BLE001
                return []
        else:
            break
    return list(val) if isinstance(val, list) else []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        for email, uid in ACCOUNTS.items():
            row = db.execute(
                text("SELECT email, language, policy_interests FROM users WHERE id = :i"),
                {"i": uid},
            ).fetchone()
            if not row:
                print(f"\n=== {email}: NOT FOUND, skipped ===")
                continue

            print(f"\n=== {email} ===")
            print(f"  language now      : {row.language}")
            interests = _parse_interests(row.policy_interests)
            print(f"  interests now     : {interests}")

            # ---- 1. language --------------------------------------------
            if row.language != "ca":
                print("  [CHANGE] language -> ca")
                if args.apply:
                    db.execute(text("UPDATE users SET language='ca' WHERE id=:i"), {"i": uid})
            else:
                print("  [OK] language already ca")

            # ---- 2. the policy interest that drives everything ----------
            if DPP_INTEREST not in interests:
                new = interests + [DPP_INTEREST]
                print(f"  [CHANGE] tick interest: {DPP_INTEREST}")
                if args.apply:
                    db.execute(
                        # written back as a JSON STRING because the column is text
                        text("UPDATE users SET policy_interests = :p WHERE id=:i"),
                        {"p": __import__("json").dumps(new, ensure_ascii=False), "i": uid},
                    )
            else:
                print("  [OK] interest already ticked")

            # ---- 3. the consultations that govern her project ----------
            for ref, why in CONSULTATIONS.items():
                cid = db.execute(
                    text("SELECT id FROM public_consultations WHERE initiative_id = :r"),
                    {"r": ref},
                ).scalar()
                if not cid:
                    print(f"  [WARN] consultation {ref} not in the database, skipped")
                    rc = 1
                    continue
                already = db.execute(
                    text("SELECT count(*) FROM user_consultation_tracks "
                         "WHERE user_id = :u AND consultation_id = :c"),
                    {"u": uid, "c": cid},
                ).scalar()
                if already:
                    print(f"  [OK] {ref} already tracked")
                    continue
                print(f"  [CHANGE] track {ref}: {why}")
                if args.apply:
                    db.execute(
                        text("INSERT INTO user_consultation_tracks "
                             "(user_id, consultation_id, notify_on_deadline, notify_on_outcome, notes) "
                             "VALUES (:u, :c, true, true, :n)"),
                        {"u": uid, "c": cid, "n": f"LIFE DPP-TEX: {why}"},
                    )

        if args.apply:
            db.commit()
            print("\n=== verification ===")
            for email, uid in ACCOUNTS.items():
                r = db.execute(
                    text("SELECT language, policy_interests FROM users WHERE id=:i"), {"i": uid}
                ).fetchone()
                if not r:
                    continue
                n = db.execute(
                    text("SELECT count(*) FROM user_consultation_tracks t "
                         "JOIN public_consultations p ON p.id = t.consultation_id "
                         "WHERE t.user_id = :u AND p.initiative_id = ANY(:refs)"),
                    {"u": uid, "refs": list(CONSULTATIONS)},
                ).scalar()
                ok_lang = r.language == "ca"
                ok_int = DPP_INTEREST in _parse_interests(r.policy_interests)
                print(f"  {email}")
                print(f"    language ca            : {'OK' if ok_lang else 'FAIL'}")
                print(f"    DPP interest ticked    : {'OK' if ok_int else 'FAIL'}")
                print(f"    DPP consultations      : {n}/{len(CONSULTATIONS)} "
                      f"{'OK' if n == len(CONSULTATIONS) else 'FAIL'}")
                if not (ok_lang and ok_int and n == len(CONSULTATIONS)):
                    rc = 1
        else:
            print("\n[DRY-RUN] nothing written")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
