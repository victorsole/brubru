"""The ECB's euro foreign exchange reference rates, for `amount_eur` (funding standard Phase 2 step 6,
29 Oct 2026; standard §6: an item's figure in euros at the ECB reference rate of its own date).

Read from the ECB Data Portal, dataflow EXR, series D.<currency>.EUR.SP00.A: one value per TARGET
working day (about 14:15 CET), units of the currency for one euro. The same dataflow also carries four
indicative rates (ARS, DZD, MAD, TWD, last published 30 Oct 2020), whose title says "Indicative
exchange rate": they are not reference rates and are not read. Which series are reference rates is
read from the ECB's own titles each run, so a currency the ECB adds or drops needs no change here.
Stored in ecb_reference_rates (migration 318) by scripts/sync_ecb_reference_rates.py.
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Iterable, List, Optional

import requests

DATA_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.{currencies}.EUR.SP00.A"
SERIES_URL = "https://data.ecb.europa.eu/data/datasets/EXR/{key}"
REFERENCE_TITLE = "ECB reference exchange rate"
_HEADERS = {"User-Agent": "Brubru/1.0 (+https://brubru.beresol.eu; hello@beresol.eu)"}


def reference_currencies(csv_text: str) -> List[str]:
    """The currencies whose series the ECB titles a reference rate, from a full-detail CSV."""
    out = set()
    for r in csv.DictReader(io.StringIO(csv_text)):
        if (r.get("TITLE_COMPL") or "").startswith(REFERENCE_TITLE) and len(r.get("CURRENCY") or "") == 3:
            out.add(r["CURRENCY"])
    return sorted(out)


def parse_rates(csv_text: str, currencies: Iterable[str]) -> List[dict]:
    """The rows of a data-only CSV for the given currencies: currency, rate_date, rate (> 0)."""
    wanted = set(currencies)
    out = []
    for r in csv.DictReader(io.StringIO(csv_text)):
        cur, day, value = r.get("CURRENCY"), r.get("TIME_PERIOD"), (r.get("OBS_VALUE") or "").strip()
        if cur not in wanted or not day or not value:
            continue
        try:
            rate = float(value)
            rate_date = date.fromisoformat(day)
        except ValueError:
            continue
        if rate > 0:
            key = r.get("KEY") or f"EXR.D.{cur}.EUR.SP00.A"
            out.append({"currency": cur, "rate_date": rate_date, "rate": value, "series_key": key,
                        "source_url": SERIES_URL.format(key=key)})
    return out


def _get(url: str, params: dict, session=None) -> str:
    r = (session or requests).get(url, params=params, headers=_HEADERS, timeout=180)
    r.raise_for_status()
    return r.text


def fetch_rates(start: date, end: Optional[date] = None, session=None) -> List[dict]:
    """Every reference rate from `start` (to `end`), read from the ECB in two requests: the series'
    titles (the last value of each), then the values of the reference series only."""
    titles = _get(DATA_URL.format(currencies=""), {"lastNObservations": 1, "format": "csvdata"}, session)
    currencies = reference_currencies(titles)
    if not currencies:
        return []
    params = {"startPeriod": start.isoformat(), "format": "csvdata", "detail": "dataonly"}
    if end:
        params["endPeriod"] = end.isoformat()
    return parse_rates(_get(DATA_URL.format(currencies="+".join(currencies)), params, session), currencies)
