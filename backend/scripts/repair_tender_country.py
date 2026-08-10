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

from core.database import SessionLocal  # noqa: E402
from models.tender import Tender  # noqa: E402
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    db = SessionLocal()
    fixed = unresolved = skipped = 0
    try:
        rows = db.query(Tender).order_by(Tender.id).all()
        if args.limit:
            rows = rows[: args.limit]

        for tender in rows:
            current = tender.buyer_country
            if is_valid_country(current):
                skipped += 1
                continue

            resolved = country_from_xml(tender.xml_content)
            if not resolved:
                unresolved += 1
                print(f"  [leave] {tender.publication_number}: "
                      f"{current!r} -> no country in its own XML")
                continue

            print(f"  [fix]   {tender.publication_number}: {current!r} -> {resolved}")
            if args.apply:
                tender.buyer_country = resolved
            fixed += 1

        if args.apply:
            db.commit()

        print(f"\n[repair] fixed={fixed} unresolved={unresolved} "
              f"already_valid={skipped} applied={args.apply}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
