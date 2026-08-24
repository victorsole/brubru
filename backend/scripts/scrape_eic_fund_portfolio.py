#!/usr/bin/env python3.12
"""Scrape the EIC Fund public investee portfolio.

Source: https://eic.ec.europa.eu/eic-fund/eic-fund-invested-companies_en
(server-rendered Drupal page, paginated + filterable by 12 sector themes).

Iterates each theme filter, walks pages 0..N until the page is empty, parses
the `ecl-content-block` cards into rows, and upserts into
eic_fund_portfolio_companies. Idempotent on (name) — the first theme seen
"wins" attribution for multi-theme companies (we capture FIRST theme only to
keep the row 1-to-1; the EC website itself follows the same convention in
its card view).

Usage:
    python3.12 scripts/scrape_eic_fund_portfolio.py
    python3.12 scripts/scrape_eic_fund_portfolio.py --theme 95   # single theme
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
import psycopg2
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PORTFOLIO_URL = "https://eic.ec.europa.eu/eic-fund/eic-fund-invested-companies_en"
# Theme codes discovered from api_funds.md lines 452-463. Names are filled
# in from the first row's "Sector" definition when scraping that theme.
THEME_CODES = [41, 48, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104]

UA = "Mozilla/5.0 (compatible; BrubruScraper/1.0; +https://brubru.beresol.eu)"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9"}


def _db():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    url = get_database_url()
    return psycopg2.connect(url)


def _fetch(client: httpx.Client, theme: int | None, page: int) -> str:
    params = {"page": page}
    if theme is not None:
        params["f[0]"] = f"theme_theme:{theme}"
    r = client.get(PORTFOLIO_URL, params=params, timeout=25, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _parse_cards(html: str) -> list[dict]:
    """Each card is an `ecl-content-block` with title link + description +
    a definition-list of meta (Country, Sector, etc.)."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for block in soup.select(".ecl-content-block"):
        title_link = block.select_one(".ecl-content-block__title a")
        if not title_link:
            continue
        name = title_link.get_text(strip=True)
        href = title_link.get("href", "")
        if not name:
            continue
        # Skip non-company blocks (some pages embed news/events using the
        # same ECL component — they don't have an /eic-fund-portfolio/ slug).
        if "/eic-fund-portfolio/" not in href:
            continue
        desc_el = block.select_one(".ecl-content-block__description")
        description = desc_el.get_text(" ", strip=True) if desc_el else ""

        # Definition list: dt = label ("Country", "Sector", "Stage", ...),
        # dd = value. Pair them up.
        meta: dict[str, str] = {}
        for dl in block.select(".ecl-description-list"):
            terms = dl.select(".ecl-description-list__term")
            defs = dl.select(".ecl-description-list__definition")
            for t, d in zip(terms, defs):
                meta[t.get_text(" ", strip=True).strip().lower()] = d.get_text(" ", strip=True).strip()
        out.append({
            "name": name,
            "country_name": meta.get("country") or None,
            "sector": meta.get("sector") or None,
            "description": description or None,
            "source_url": f"https://eic.ec.europa.eu{href}" if href.startswith("/") else href,
        })
    return out


# ISO-3166 alpha-2 codes for the EU + Horizon-associated countries that
# show up most often in the EIC Fund portfolio. Anything not mapped stays NULL.
_COUNTRY_TO_ISO = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czechia": "CZ", "Czech Republic": "CZ",
    "Denmark": "DK", "Estonia": "EE", "Finland": "FI", "France": "FR",
    "Germany": "DE", "Greece": "GR", "Hungary": "HU", "Iceland": "IS",
    "Ireland": "IE", "Israel": "IL", "Italy": "IT", "Latvia": "LV",
    "Lithuania": "LT", "Luxembourg": "LU", "Malta": "MT",
    "Netherlands": "NL", "The Netherlands": "NL",
    "Norway": "NO", "Poland": "PL", "Portugal": "PT", "Romania": "RO",
    "Slovakia": "SK", "Slovenia": "SI", "Spain": "ES", "Sweden": "SE",
    "Switzerland": "CH", "Türkiye": "TR", "Turkey": "TR", "United Kingdom": "GB",
    "Ukraine": "UA", "Serbia": "RS", "Albania": "AL",
}


def _iso(country_name: str | None) -> str | None:
    if not country_name:
        return None
    return _COUNTRY_TO_ISO.get(country_name.strip())


def scrape_theme(client: httpx.Client, theme: int | None, stats: dict) -> None:
    """Walk every page until an empty page is returned. Works with theme=None
    (global, un-filtered) or with a theme filter."""
    page = 0
    seen_in_theme = 0
    theme_name: str | None = None
    while True:
        html = _fetch(client, theme, page)
        cards = _parse_cards(html)
        if not cards:
            break
        if theme is not None and theme_name is None:
            for c in cards:
                if c.get("sector"):
                    theme_name = c["sector"]
                    break
        _upsert(theme, theme_name, cards, stats)
        seen_in_theme += len(cards)
        page += 1
        time.sleep(0.4)
    label = f"theme={theme} ({theme_name or '?'})" if theme is not None else "GLOBAL pass"
    print(f"  {label}: {seen_in_theme} cards, running unique total = {stats['unique']}", flush=True)


def _upsert(theme: int | None, theme_name: str | None, cards: list[dict], stats: dict) -> None:
    """Two upsert flavours:
       - GLOBAL pass (theme is None): inserts new rows with theme=NULL;
         on conflict, refreshes only description/country (leaves theme alone).
       - THEME pass: inserts/updates theme_code+theme_name too, so a
         multi-theme company gets the LAST processed theme attributed.
    """
    conn = _db()
    try:
        cur = conn.cursor()
        for c in cards:
            iso = _iso(c.get("country_name"))
            if theme is None:
                cur.execute(
                    """
                    INSERT INTO eic_fund_portfolio_companies
                        (name, country, country_name, theme_code, theme_name, description, source_url)
                    VALUES (%s, %s, %s, NULL, NULL, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        description  = COALESCE(EXCLUDED.description, eic_fund_portfolio_companies.description),
                        country      = COALESCE(EXCLUDED.country, eic_fund_portfolio_companies.country),
                        country_name = COALESCE(EXCLUDED.country_name, eic_fund_portfolio_companies.country_name)
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (c["name"], iso, c.get("country_name"),
                     c.get("description"), c.get("source_url")),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO eic_fund_portfolio_companies
                        (name, country, country_name, theme_code, theme_name, description, source_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        theme_code   = EXCLUDED.theme_code,
                        theme_name   = EXCLUDED.theme_name,
                        description  = COALESCE(EXCLUDED.description, eic_fund_portfolio_companies.description),
                        country      = COALESCE(EXCLUDED.country, eic_fund_portfolio_companies.country),
                        country_name = COALESCE(EXCLUDED.country_name, eic_fund_portfolio_companies.country_name)
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (c["name"], iso, c.get("country_name"), theme, theme_name,
                     c.get("description"), c.get("source_url")),
                )
            inserted = cur.fetchone()[0]
            if inserted:
                stats["unique"] += 1
            else:
                stats["dup"] += 1
        conn.commit()
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", type=int, help="Scrape one theme code only (skips global pass)")
    ap.add_argument("--skip-global", action="store_true",
                    help="Skip the un-filtered global pass (used during incremental theme refresh)")
    args = ap.parse_args()
    stats = {"unique": 0, "dup": 0}
    with httpx.Client(headers=HEADERS) as client:
        if args.theme:
            scrape_theme(client, args.theme, stats)
        else:
            # Two-pass strategy:
            # 1) Global pass — picks up every company (some have no theme tag).
            # 2) Per-theme pass — assigns the theme label (last-theme-wins on
            #    multi-theme companies; deterministic given THEME_CODES order).
            if not args.skip_global:
                scrape_theme(client, None, stats)
            for t in THEME_CODES:
                scrape_theme(client, t, stats)
    print(f"\nDone. {stats['unique']} unique companies, {stats['dup']} duplicates "
          f"(same row revisited across themes — last theme wins).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
