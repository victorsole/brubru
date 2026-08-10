"""
One place that decides what a country code is.

`tenders.buyer_country` is `varchar(2)` and the matcher hard-filters on it, so a
wrong value does not degrade a result, it removes the notice from the user's feed
entirely. Three separate write paths were each guessing:

- `eforms_parser` reads `cac:Country/cbc:IdentificationCode`, which carries the
  ISO alpha-3 ("CZE"). Three characters into a two-character column is a
  DataError, so that path never landed and the caller's fallback won.
- the TED SPARQL loader reads `skos:notation` off the country authority-table
  URI without constraining the notation scheme, so it picked up whichever
  notation came back first. That is where the ten `CS`, and the `DA` and `SV`,
  came from: they are language codes, not countries.
- `tender_service` took `countryCode` from the API response verbatim.

`normalise_country` is the single answer. It accepts alpha-2, alpha-3 or a
country name, and returns a validated alpha-2 or None. None is a real answer:
"we do not know" is safe because the matcher treats a missing country as no
signal, whereas a wrong country is a silent exclusion.

TED covers more than the EU-27 (EEA, candidate countries, Switzerland, the UK
for Northern Ireland notices), so the whitelist is deliberately wider than the
Union.
"""
from __future__ import annotations

from typing import Optional

# Codes Brubru accepts in `tenders.buyer_country`. EU-27 + EEA + candidates +
# CH/UK, which is the practical span of TED notices.
VALID_ALPHA2: frozenset[str] = frozenset({
    # EU-27
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
    # EEA / EFTA
    "IS", "LI", "NO", "CH",
    # United Kingdom (Northern Ireland notices still publish to TED)
    "GB",
    # Candidate and potential-candidate countries that publish to TED
    "AL", "BA", "ME", "MD", "MK", "RS", "TR", "UA", "GE", "XK",
})

ALPHA3_TO_ALPHA2: dict[str, str] = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY",
    "CZE": "CZ", "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR",
    "DEU": "DE", "GRC": "GR", "HUN": "HU", "IRL": "IE", "ITA": "IT",
    "LVA": "LV", "LTU": "LT", "LUX": "LU", "MLT": "MT", "NLD": "NL",
    "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK", "SVN": "SI",
    "ESP": "ES", "SWE": "SE", "ISL": "IS", "LIE": "LI", "NOR": "NO",
    "CHE": "CH", "GBR": "GB", "ALB": "AL", "BIH": "BA", "MNE": "ME",
    "MDA": "MD", "MKD": "MK", "SRB": "RS", "TUR": "TR", "UKR": "UA",
    "GEO": "GE", "XKX": "XK",
}

# Codes the EU institutions use that ISO does not. Both appear in Publications
# Office authority tables and in eForms payloads.
EU_ALIASES: dict[str, str] = {
    "EL": "GR",   # Eurostat / EU code for Greece
    "UK": "GB",   # EU code for the United Kingdom
    "EU": "",     # "European Union" is not a buyer country
    "1A": "MK",   # legacy code for North Macedonia
}

NAME_TO_ALPHA2: dict[str, str] = {
    "austria": "AT", "belgium": "BE", "bulgaria": "BG", "croatia": "HR",
    "cyprus": "CY", "czechia": "CZ", "czech republic": "CZ", "denmark": "DK",
    "estonia": "EE", "finland": "FI", "france": "FR", "germany": "DE",
    "greece": "GR", "hungary": "HU", "ireland": "IE", "italy": "IT",
    "latvia": "LV", "lithuania": "LT", "luxembourg": "LU", "malta": "MT",
    "netherlands": "NL", "the netherlands": "NL", "poland": "PL",
    "portugal": "PT", "romania": "RO", "slovakia": "SK", "slovenia": "SI",
    "spain": "ES", "sweden": "SE", "iceland": "IS", "liechtenstein": "LI",
    "norway": "NO", "switzerland": "CH", "united kingdom": "GB",
    "albania": "AL", "bosnia and herzegovina": "BA", "montenegro": "ME",
    "moldova": "MD", "north macedonia": "MK", "serbia": "RS",
    "turkey": "TR", "türkiye": "TR", "ukraine": "UA", "georgia": "GE",
    "kosovo": "XK",
}

# Two-letter ISO-639 language codes that collide with the shape of a country
# code. These are what the SPARQL notation bug produced. Listing them means a
# future notation mix-up is rejected loudly at the whitelist rather than
# silently stored: `CS`, `DA` and `SV` are not in VALID_ALPHA2, so they would be
# dropped anyway, but naming them documents what went wrong.
KNOWN_LANGUAGE_CODE_COLLISIONS: frozenset[str] = frozenset({
    "CS", "DA", "SV", "ET", "SL", "SK", "PL", "NL", "DE", "FR", "IT", "ES",
})


def normalise_country(value: Optional[str]) -> Optional[str]:
    """Validated ISO alpha-2, or None when the input is not a country.

    Accepts alpha-2 ("CZ"), alpha-3 ("CZE"), an EU alias ("EL") or an English
    country name ("Czechia"). Anything else returns None rather than a guess.

    Note the deliberate asymmetry with `KNOWN_LANGUAGE_CODE_COLLISIONS`: `SK`,
    `PL`, `NL`, `DE`, `FR`, `IT` and `ES` are BOTH language codes and valid
    country codes, so they are accepted. Only codes that are exclusively
    languages (`CS`, `DA`, `SV`, `ET`, `SL`) fall through to None, because they
    are not in VALID_ALPHA2. We cannot recover the intended country from a
    language code without guessing, and guessing is what caused this.
    """
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    upper = raw.upper()

    if upper in EU_ALIASES:
        mapped = EU_ALIASES[upper]
        return mapped or None

    if len(upper) == 2:
        return upper if upper in VALID_ALPHA2 else None

    if len(upper) == 3:
        return ALPHA3_TO_ALPHA2.get(upper)

    return NAME_TO_ALPHA2.get(raw.lower())


def is_valid_country(value: Optional[str]) -> bool:
    """True when `value` is already a country code Brubru will store."""
    return bool(value) and str(value).strip().upper() in VALID_ALPHA2
