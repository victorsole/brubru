"""Put the 13 in-force DPP acts into My Tracked Files as archived cards.

An adopted law has no live procedure to follow, so it does not belong in the
active list. It does belong in the Archive: it is a completed file, and it is
the regulatory baseline the LIFE DPP-TEX work is built on. This makes her
Archive read as "these are the laws that govern my project", which is what she
would have built herself over months of tracking.

Why carriages. The Archive accepts six entity types (carriage, commission_doc,
consultation, committee_work, text_adopted, vote). `text_adopted` is EP adopted
texts keyed by P10_TA reference, not CELEX, so it is the wrong table. `carriage`
is right: legislative_carriages already holds adopted acts, including Directive
(EU) 2025/1892 with file_id 32025l1892 and status ADOPTED.

Why we create rows rather than reuse what is there. Six of the thirteen already
match a carriage, but five of those six are CORRIGENDA, not the act: attaching
her to "Corrigendum to Regulation ..." would misrepresent what she tracks. Each
act therefore gets a proper row keyed on the lowercase CELEX, which is the
convention EUR-Lex-sourced carriages already use.

Metadata comes from eu_laws, which holds all thirteen after the 11 August
ingest. Nothing here is invented.
"""

from __future__ import annotations

import argparse
import sys
import uuid
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

# celex -> why this act is part of her regulatory baseline
ACTS = {
    "32024R1781": "ESPR: the framework that creates the digital product passport",
    "32026R1778": "the implementing regulation for the DPP registry",
    "32026D1736": "publishes the harmonised standards for digital product passports",
    "32023R1542": "the battery passport, first with a hard deadline (18 Feb 2027)",
    "32024R3110": "construction products, registered in the same DPP registry",
    "32025R2509": "toys, registered in the same DPP registry",
    "32026R0405": "detergents and surfactants, registered in the same DPP registry",
    "32025R0040": "packaging and packaging waste",
    "32024R1252": "critical raw materials, feeding the passport information layer",
    "32025L1892": "textile extended producer responsibility: her core instrument",
    "32011R1007": "textile fibre names and labelling, the baseline the passport inherits",
    "32026R0002": "implementing regulation in the ecodesign series",
    "32026R0296": "delegated regulation on unsold consumer products",
}

EURLEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    created = 0
    try:
        carriage_ids = {}

        print("=== ensuring a proper carriage row per act ===")
        for celex, why in ACTS.items():
            law = db.execute(
                text("SELECT title, date FROM eu_laws WHERE celex = :c"), {"c": celex}
            ).fetchone()
            if not law:
                print(f"  [FAIL] {celex}: not in eu_laws, skipped")
                rc = 1
                continue

            fid = celex.lower()
            existing = db.execute(
                text("SELECT id, title FROM legislative_carriages WHERE file_id = :f"),
                {"f": fid},
            ).fetchone()
            if existing:
                carriage_ids[celex] = existing.id
                # These rows are keyed on the base CELEX but their title and url
                # were populated from whichever EUR-Lex document the feed last
                # saw, which for five of them was a CORRIGENDUM. Four display a
                # raw "CELEX:32025R2509R(02)" string as their title to anyone
                # tracking that file. Repair from eu_laws, which is
                # authoritative, rather than leave her card reading as a
                # corrigendum.
                looks_wrong = (
                    existing.title.startswith("CELEX:")
                    or "Corrigendum" in existing.title
                    or "Berichtigung" in existing.title
                    or existing.title.strip().startswith("Regulation: CELEX:")
                )
                if looks_wrong:
                    print(f"  [FIX]  {celex}: title was {existing.title[:40]!r}")
                    print(f"                -> {law.title[:56]}")
                    if args.apply:
                        db.execute(
                            text("UPDATE legislative_carriages SET title = :t, "
                                 "url = :u, last_updated = now() WHERE id = :i"),
                            {"t": law.title, "u": EURLEX.format(celex=celex),
                             "i": existing.id},
                        )
                else:
                    print(f"  [OK]   {celex}: row exists ({existing.title[:44]})")
                continue

            cid = str(uuid.uuid4())
            carriage_ids[celex] = cid
            created += 1
            print(f"  [NEW]  {celex}: {law.title[:56]}")
            if args.apply:
                db.execute(
                    text("""
                        INSERT INTO legislative_carriages (
                            id, file_id, title, current_status, celex_numbers,
                            text_type, source, url, policy_areas,
                            scraped_at, first_seen, last_updated
                        ) VALUES (
                            :id, :fid, :title, 'ADOPTED', :celex,
                            'LEGISLATIVE', 'EURLEX', :url, :areas,
                            now(), now(), now()
                        )
                    """),
                    {"id": cid, "fid": fid, "title": law.title,
                     "celex": [celex], "url": EURLEX.format(celex=celex),
                     "areas": ["Environment"]},
                )

        print("\n=== archived tracks ===")
        for email, uid in ACCOUNTS.items():
            print(f"  {email}")
            for celex, why in ACTS.items():
                cid = carriage_ids.get(celex)
                if not cid:
                    continue
                law_date = db.execute(
                    text("SELECT date FROM eu_laws WHERE celex = :c"), {"c": celex}
                ).scalar()
                already = db.execute(
                    text("SELECT id, archived_at FROM user_carriage_tracks "
                         "WHERE user_id = :u AND carriage_id = :c"),
                    {"u": uid, "c": cid},
                ).fetchone()
                reason = (f"In force. {why[0].upper()}{why[1:]}. Archived as a completed file: "
                          "the regulatory baseline for LIFE DPP-TEX, kept for reference.")
                if already:
                    print(f"    [OK]  {celex} already tracked")
                    if already.archived_at is None and args.apply:
                        db.execute(
                            text("UPDATE user_carriage_tracks SET archived_at = now(), "
                                 "archived_reason = :r WHERE id = :i"),
                            {"r": reason, "i": already.id},
                        )
                    continue
                print(f"    [ADD] {celex} ({law_date}) -> Archive")
                if args.apply:
                    db.execute(
                        text("INSERT INTO user_carriage_tracks "
                             "(id, user_id, carriage_id, tracked_since, archived_at, archived_reason) "
                             "VALUES (:id, :u, :c, now(), now(), :r)"),
                        {"id": str(uuid.uuid4()), "u": uid, "c": cid, "r": reason},
                    )

        if args.apply:
            db.commit()
            print(f"\n=== verification ===  ({created} carriage row(s) created)")
            for email, uid in ACCOUNTS.items():
                n = db.execute(
                    text("SELECT count(*) FROM user_carriage_tracks t "
                         "JOIN legislative_carriages lc ON lc.id = t.carriage_id "
                         "WHERE t.user_id = :u AND t.archived_at IS NOT NULL "
                         "AND lc.file_id = ANY(:fids)"),
                    {"u": uid, "fids": [c.lower() for c in ACTS]},
                ).scalar()
                act = db.execute(
                    text("SELECT count(*) FROM user_carriage_tracks "
                         "WHERE user_id = :u AND archived_at IS NULL"), {"u": uid}).scalar()
                arch = db.execute(
                    text("SELECT count(*) FROM user_carriage_tracks "
                         "WHERE user_id = :u AND archived_at IS NOT NULL"), {"u": uid}).scalar()
                ok = n == len(ACTS)
                print(f"  {email}: {n}/{len(ACTS)} DPP acts archived {'OK' if ok else 'FAIL'} "
                      f"| {act} active, {arch} archived in total")
                if not ok:
                    rc = 1
        else:
            print("\n[DRY-RUN] nothing written")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
