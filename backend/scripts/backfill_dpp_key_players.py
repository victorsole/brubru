"""Put the people back on the adopted-law cards: who actually made each act.

A card that says an act is in force but not who steered it is missing the part a
public-affairs reader needs. OEIL carries it: the committee responsible and its
rapporteur with political group and appointment date, the associated and opinion
committees with theirs, and the institutions involved.

Why a new parser. services/scrapers/oeil_scraper.py has a _parse_key_players,
but it is misaligned with the current OEIL layout and returns LABELS as values:
asked for the commissioner it answers "Commission DG", and the rapporteur comes
back None. Rather than silently store that, this reads the rendered page and
takes the committee/rapporteur rows positionally, which is what the layout
actually gives.

Stored on legislative_carriages.oeil_procedure_data, which already exists for
this purpose, plus lead_committee, which the tracked-file card reads directly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

OEIL = "https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={ref}"

# file_id -> OEIL procedure reference, for the acts that have one
FILES = {
    "32024r1781": "2022/0095(COD)",
    "lip-2020-0353-COD": "2020/0353(COD)",
    "32025l1892": "2023/0234(COD)",
    "32025r0040": "2022/0396(COD)",
    "32024r1252": "2023/0079(COD)",
    "lip-2023-0290-COD": "2023/0290(COD)",
    "2023-0124-cod": "2023/0124(COD)",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# "MORETTI Alessandra (S&D)" — surname, forename, political group
_MEP = re.compile(r"^([A-ZÀ-Þ][A-ZÀ-Þ'’\- ]+)\s+([A-Za-zÀ-ÿ'’\-\. ]+)\s+\(([^)]+)\)$")
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
# "ENVI" / "IMCO" / "ITRE" on its own line
_CTTEE = re.compile(r"^[A-Z]{4,6}$")


def parse_key_players(page_text: str) -> dict:
    """Committees and their rapporteurs, read positionally from the block."""
    start = page_text.find("Key players")
    end = page_text.find("Key events", start + 1)
    if start < 0 or end < 0:
        return {}
    block = page_text[start:end]
    lines = [l.strip() for l in block.split("\n")]

    out = {"committee_responsible": None, "rapporteur": None,
           "shadow_rapporteurs": [], "opinion_committees": [], "institutions": []}

    section = "responsible"
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("Shadow rapporteur"):
            section = "shadow"
        elif line.startswith("Committee for opinion"):
            section = "opinion"
        elif _CTTEE.match(line):
            code = line
            full = lines[i + 1] if i + 1 < len(lines) else ""
            associated = "(Associated committee)" in "\n".join(lines[i + 1:i + 4])
            mep = group = appointed = None
            for j in range(i + 1, min(i + 6, len(lines))):
                m = _MEP.match(lines[j])
                if m and not mep:
                    mep = f"{m.group(1).title()} {m.group(2).strip()}"
                    group = m.group(3)
                if _DATE.match(lines[j]) and not appointed:
                    appointed = lines[j]
            entry = {"code": code, "name": full, "associated": associated,
                     "rapporteur": mep, "group": group, "appointed": appointed}
            if section == "responsible" and not out["committee_responsible"]:
                out["committee_responsible"] = entry
                out["rapporteur"] = ({"name": mep, "group": group,
                                      "appointed": appointed, "committee": code}
                                     if mep else None)
            elif section == "shadow" and mep:
                out["shadow_rapporteurs"].append({"name": mep, "group": group})
            else:
                out["opinion_committees"].append(entry)
            i += 1
        elif line in ("Council of the European Union", "European Commission",
                      "European Economic and Social Committee",
                      "European Committee of the Regions"):
            out["institutions"].append(line)
        i += 1
    return out


async def fetch_all(refs):
    from playwright.async_api import async_playwright

    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=UA, locale="en-GB")
        for fid, ref in refs.items():
            pg = await ctx.new_page()
            try:
                await pg.goto(OEIL.format(ref=ref), wait_until="domcontentloaded",
                              timeout=90000)
                await pg.wait_for_timeout(6000)
                t = re.sub(r"\n{3,}", "\n\n",
                           await pg.evaluate("() => document.body.innerText"))
                kp = parse_key_players(t)
                out[fid] = kp
                cr = (kp.get("committee_responsible") or {}).get("code")
                rp = (kp.get("rapporteur") or {}).get("name")
                print(f"  {ref:<16} committee={cr or '-':<6} rapporteur={rp or '-':<24} "
                      f"opinion={len(kp.get('opinion_committees') or [])}")
            except Exception as exc:  # noqa: BLE001
                print(f"  {ref}: FAILED {type(exc).__name__}")
                out[fid] = {}
            finally:
                await pg.close()
        await b.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    print("=== reading OEIL key players ===")
    players = asyncio.run(fetch_all(FILES))

    db = SessionLocal()
    rc = 0
    try:
        print("\n=== writing ===")
        for fid, kp in players.items():
            if not kp or not kp.get("committee_responsible"):
                print(f"  [SKIP] {fid}: nothing parsed")
                continue
            lead = kp["committee_responsible"]["code"]
            if args.apply:
                db.execute(
                    text("UPDATE legislative_carriages SET "
                         "oeil_procedure_data = CAST(:d AS json), "
                         "lead_committee = COALESCE(lead_committee, :lc), "
                         "last_updated = now() WHERE file_id = :f"),
                    {"d": json.dumps(kp, ensure_ascii=False), "lc": lead, "f": fid},
                )
            print(f"  [OK] {fid}: lead={lead}")

        if args.apply:
            db.commit()
            print("\n=== verification ===")
            for fid in FILES:
                r = db.execute(
                    text("SELECT lead_committee, oeil_procedure_data FROM "
                         "legislative_carriages WHERE file_id = :f"), {"f": fid}
                ).fetchone()
                d = r.oeil_procedure_data or {}
                rp = (d.get("rapporteur") or {}).get("name")
                grp = (d.get("rapporteur") or {}).get("group")
                op = len(d.get("opinion_committees") or [])
                ok = bool(rp)
                print(f"  {fid:<20} {str(r.lead_committee):<6} "
                      f"{str(rp) + ' (' + str(grp) + ')' if rp else 'no rapporteur':<34} "
                      f"opinion={op} {'OK' if ok else 'CHECK'}")
                if not ok:
                    rc = 1
        else:
            print("\n[DRY-RUN] nothing written")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
