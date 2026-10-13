"""
Repair `tenders.buyer_country` from each row's OWN stored XML.

Incident (10 Aug 2026): 59 of 386 rows carried a country that was not a country.
Ten said `CS`, one `DA`, one `SV` -- ISO-639 language codes, not ISO-3166 -- and
46 were NULL. One said `EL`, which is the EU's code for Greece rather than the
ISO one. They all came from the TED SPARQL loader, which reads `skos:notation`
off the country authority-table URI without constraining the notation scheme and
stored whichever notation came back first.

This matters more than a cosmetic field: `TenderMatcher._calculate_match` hard
-excludes any notice whose `buyer_country` is missing from the user's country
list, so a wrong code silently removes the notice from that user's feed.

The repair reads `cac:Country/cbc:IdentificationCode` from the row's own
`xml_content` -- no network, no cross-row inference, no guessing. A row whose XML
does not state a country is left alone rather than filled from its title
language, which is exactly the inference that created the mess.

It reads the XML of the rows that need it, and only those (13 October 2026). The first
version loaded every notice with its XML to look at each country: 386 rows in August,
49,701 rows and 1.25 GB in October, and the platform killed the job every night (rc=-9,
no output) from 6 October. Measured that day: 260 rows had no valid country, 4 of them
had any XML. So the countries are read first, without the XML, and the XML is fetched
in small batches for the rows whose country is not valid.

Run:
    python3.12 backend/scripts/repair_tender_country.py            # dry run
    python3.12 backend/scripts/repair_tender_country.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.tenders.country_codes import (  # noqa: E402
    normalise_country,
    is_valid_country,
)

# eForms: <cac:Country><cbc:IdentificationCode listName="country">CZE</...>
# Legacy TED R2.0.9: <COUNTRY VALUE="CZ"/>
_EFORMS_COUNTRY = re.compile(
    r"<cbc:IdentificationCode[^>]*listName=[\"']country[\"'][^>]*>\s*([A-Za-z]{2,3})\s*<",
)
_LEGACY_COUNTRY = re.compile(r"<COUNTRY[^>]*VALUE=[\"']([A-Za-z]{2,3})[\"']")


def country_from_xml(xml: str | None) -> str | None:
    """First country code the notice states about itself, normalised."""
    if not xml:
        return None
    for pattern in (_EFORMS_COUNTRY, _LEGACY_COUNTRY):
        match = pattern.search(xml)
        if match:
            resolved = normalise_country(match.group(1))
            if resolved:
                return resolved
    return None


# Never the XML here: this is every row of the table.
_COUNTRIES = text("SELECT id, publication_number, buyer_country FROM tenders ORDER BY id")
_XML = text("SELECT id, xml_content FROM tenders WHERE id = ANY(:ids)")
_SET = text("UPDATE tenders SET buyer_country = :c, updated_at = now() WHERE id = :id")
_BATCH = 100
_LEAVES_LISTED = 20


def repair(db, *, apply: bool, limit: int | None = None) -> tuple[int, int, int]:
    """(fixed, unresolved, already_valid). Reads XML only for rows without a valid country."""
    rows = db.execute(_COUNTRIES).all()
    todo = [r for r in rows if not is_valid_country(r.buyer_country)]
    skipped = len(rows) - len(todo)
    if limit:
        todo = todo[:limit]

    fixed = unresolved = 0
    for start in range(0, len(todo), _BATCH):
        chunk = todo[start:start + _BATCH]
        xml_by_id = {r.id: r.xml_content
                     for r in db.execute(_XML, {"ids": [r.id for r in chunk]}).all()}
        for row in chunk:
            resolved = country_from_xml(xml_by_id.get(row.id))
            if not resolved:
                unresolved += 1
                if unresolved <= _LEAVES_LISTED:
                    print(f"  [leave] {row.publication_number}: "
                          f"{row.buyer_country!r} -> no country in its own XML")
                continue
            print(f"  [fix]   {row.publication_number}: {row.buyer_country!r} -> {resolved}")
            if apply:
                db.execute(_SET, {"c": resolved, "id": row.id})
            fixed += 1
        if apply:
            db.commit()
    if unresolved > _LEAVES_LISTED:
        print(f"  [leave] ...and {unresolved - _LEAVES_LISTED} more")
    return fixed, unresolved, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes")
    ap.add_argument("--limit", type=int, default=None,
                    help="at most this many rows WITHOUT a valid country")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        fixed, unresolved, skipped = repair(db, apply=args.apply, limit=args.limit)
        print(f"\n[repair] fixed={fixed} unresolved={unresolved} "
              f"already_valid={skipped} applied={args.apply}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
