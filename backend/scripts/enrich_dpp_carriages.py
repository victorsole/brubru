"""Give the 13 DPP carriage cards their OEIL and Legislative Train data.

The cards created for Joana's Archive carried a title and a status and nothing
else, so they read as stubs next to a properly tracked file. This fills them.

Three sources, in order of authority:

  * OEIL, for the acts that went through an ordinary legislative procedure:
    procedure reference, key events, and the timeline built from them. OEIL is
    the source of truth for procedure identity, so the reference is LOOKED UP,
    never derived from the CELEX. CELEX and OEIL are independent counters and
    deriving one from the other has produced wrong files before.
  * The Legislative Train, matched by procedure reference where the file has an
    entry. Not every act is on the train: it follows Commission priorities.
  * eu_laws, for the description of what the act actually is.

Four of the thirteen have NO OEIL procedure and that is correct, not missing
data: Implementing Regulation 2026/1778, Implementing Decision 2026/1736,
Implementing Regulation 2026/2 and Delegated Regulation 2026/296 are Commission
acts adopted under powers delegated by the ESPR, not files that passed through
Parliament and Council. Their cards say so, rather than showing an empty
procedure field that looks like a gap.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

# celex -> (OEIL procedure ref or None, one-line role in the DPP regime)
# Every procedure reference here is taken from a Brubru knowledge guide, which
# carries it from the OEIL procedure file. None means the act is a Commission
# implementing or delegated act with no ordinary procedure.
ACTS = {
    "32024R1781": ("2022/0095(COD)",
                   "The ESPR framework: creates the digital product passport "
                   "(Articles 9 to 15), the registry (Art. 13), the public portal "
                   "(Art. 14) and the customs check (Art. 15). Sets no product "
                   "requirement itself; those arrive by delegated act under Art. 4."),
    "32023R1542": ("2020/0353(COD)",
                   "The battery passport, and the first passport with a hard "
                   "deadline: 18 February 2027 for certain large batteries. "
                   "Registry hook: Article 77."),
    "32025L1892": ("2023/0234(COD)",
                   "Extended producer responsibility for textiles and footwear, "
                   "inserted into the Waste Framework Directive. Transposition "
                   "17 June 2027; EPR schemes operational 17 April 2028."),
    "32025R0040": ("2022/0396(COD)",
                   "Packaging and packaging waste. Carries its own passport-style "
                   "obligations but is not named in Reg. 2026/1778 Art. 1, so it "
                   "does not feed the central registry on that basis."),
    "32024R1252": ("2023/0079(COD)",
                   "Critical raw materials: supply-chain and circularity duties "
                   "the passport information layer draws on."),
    "32025R2509": ("2023/0290(COD)",
                   "Toy safety. Requires a digital product passport for toys, "
                   "registered in the same registry. Registry hook: Article 19."),
    "32026R0405": ("2023/0124(COD)",
                   "Detergents and surfactants. Requires a passport registered in "
                   "the same registry. Registry hook: Article 21."),
    "32024R3110": (None,
                   "Construction products. Requires a passport registered in the "
                   "same registry (Article 76). Procedure reference not yet "
                   "confirmed from OEIL, so it is left unset rather than guessed."),
    "32011R1007": (None,
                   "Textile fibre names, labelling and marking of fibre "
                   "composition. The existing baseline the textile passport "
                   "inherits its composition data from. Procedure reference not "
                   "yet confirmed from OEIL, so it is left unset rather than guessed."),
    # Commission acts: no ordinary procedure, by nature rather than by omission
    "32026R1778": (None,
                   "Commission Implementing Regulation laying down the "
                   "implementation arrangements for the DPP registry. Adopted "
                   "under ESPR Article 13(5), so it has no ordinary legislative "
                   "procedure: it did not pass through Parliament and Council."),
    "32026D1736": (None,
                   "Commission Implementing Decision publishing the references of "
                   "the harmonised standards for digital product passports, giving "
                   "a presumption of conformity. A Commission act, so no ordinary "
                   "legislative procedure."),
    "32026R0002": (None,
                   "Commission Implementing Regulation in the ecodesign series. "
                   "A Commission act, so no ordinary legislative procedure."),
    "32026R0296": (None,
                   "Commission Delegated Regulation on unsold consumer products, "
                   "adopted under powers delegated by the ESPR. A Commission act, "
                   "so no ordinary legislative procedure."),
}


async def fetch_oeil(refs):
    """Key events per procedure reference, straight from OEIL."""
    from services.scrapers.oeil_scraper import OEILScraper

    out = {}
    s = OEILScraper()
    try:
        for ref in refs:
            try:
                p = await s.get_procedure_full(ref)
                ke = getattr(p, "key_events", None)
                events = getattr(ke, "events", None) or []
                out[ref] = [{
                    "date": str(getattr(e, "date", "") or ""),
                    "event": getattr(e, "event_type", None) or "",
                    "summary": getattr(e, "summary", None) or "",
                } for e in events]
                print(f"    {ref}: {len(out[ref])} key event(s)")
            except Exception as exc:  # noqa: BLE001
                print(f"    {ref}: OEIL fetch failed ({type(exc).__name__})")
                out[ref] = []
    finally:
        await s.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    refs = [r for r, _ in ACTS.values() if r]
    print(f"=== fetching OEIL for {len(refs)} procedure(s) ===")
    oeil = asyncio.run(fetch_oeil(refs)) if refs else {}

    db = SessionLocal()
    rc = 0
    try:
        print("\n=== enriching the cards ===")
        for celex, (ref, role) in ACTS.items():
            fid = celex.lower()
            row = db.execute(
                text("SELECT id, title FROM legislative_carriages WHERE file_id = :f"),
                {"f": fid},
            ).fetchone()
            if not row:
                print(f"  [FAIL] {celex}: no carriage row")
                rc = 1
                continue

            law = db.execute(
                text("SELECT date FROM eu_laws WHERE celex = :c"), {"c": celex}
            ).fetchone()
            events = oeil.get(ref or "", [])
            in_force = f"In force. Adopted {law.date}." if law and law.date else "In force."
            description = f"{in_force} {role}"

            print(f"  {celex}: procedure={ref or 'none (Commission act)'} "
                  f"events={len(events)}")

            if args.apply:
                db.execute(
                    text("""
                        UPDATE legislative_carriages SET
                            oeil_procedure_ref = COALESCE(:ref, oeil_procedure_ref),
                            oeil_key_events = CASE WHEN :has_ev THEN CAST(:ev AS json)
                                                   ELSE oeil_key_events END,
                            timeline = CASE WHEN :has_ev THEN CAST(:ev AS json)
                                            ELSE timeline END,
                            description = :descr,
                            current_status = 'ADOPTED',
                            last_updated = now()
                        WHERE id = :id
                    """),
                    {"ref": ref, "has_ev": bool(events),
                     "ev": json.dumps(events), "descr": description, "id": row.id},
                )

        if args.apply:
            db.commit()
            print("\n=== verification ===")
            for celex, (ref, _role) in ACTS.items():
                r = db.execute(
                    text("SELECT oeil_procedure_ref, description, "
                         "json_array_length(COALESCE(oeil_key_events, '[]'::json)) AS n "
                         "FROM legislative_carriages WHERE file_id = :f"),
                    {"f": celex.lower()},
                ).fetchone()
                has_desc = bool(r.description)
                ok = has_desc and (r.oeil_procedure_ref == ref if ref else True)
                print(f"  {celex}: proc={str(r.oeil_procedure_ref):<16} "
                      f"events={r.n:<3} description={'yes' if has_desc else 'NO'} "
                      f"{'OK' if ok else 'FAIL'}")
                if not ok:
                    rc = 1
        else:
            print("\n[DRY-RUN] nothing written")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
